"""Layer 2 (model side) — image forensics + the deferred backdating check.

The PDF-native tamper detectors (editing-software fingerprints, font outliers,
incremental %%EOF saves) run upstream in the security service, on the original
bytes, and arrive here already computed inside the EvidenceBundle's
``pdf_anomalies``.  What remains for the model — which only ever sees safe
artifacts — is:

  * Error Level Analysis — JPEG recompression differential on the flattened
    page PNGs, returning a heatmap and bounding boxes of suspicious regions.
  * Backdating — compares a file's digital birth date (carried in the bundle's
    metadata) against a registration date claimed in the *extracted fields*
    (a Layer-1 output only available here), so it cannot run in security.
"""

from __future__ import annotations

import base64
import io
import re
from datetime import datetime, timedelta, timezone

import numpy as np
from PIL import Image, ImageChops

from .models import Anomaly, ExtractedFields, Severity

_PDF_DATE_RE = re.compile(r"D:(\d{4})(\d{2})(\d{2})(\d{2})?(\d{2})?(\d{2})?")


def parse_pdf_date(raw: str | None) -> datetime | None:
    if not raw:
        return None
    m = _PDF_DATE_RE.search(raw)
    if not m:
        return None
    parts = [int(p) if p else 0 for p in m.groups()]
    try:
        return datetime(parts[0], parts[1], parts[2], parts[3], parts[4], parts[5],
                        tzinfo=timezone.utc)
    except ValueError:
        return None


def backdating_from_metadata(
    filename: str, meta: dict, fields: ExtractedFields
) -> list[Anomaly]:
    """Reconstruct the backdating check deferred from the security service.

    The security service ran the field-independent metadata forensics but could
    not run this one: it needs the claimed registration date from Layer-1 field
    extraction, which only happens here.  The PDF's ``creationDate`` /
    ``modDate`` travel in the EvidenceBundle so the check can be completed.

    Backdating: file digitally born recently while the text claims an old
    registration date (e.g. claims 2018, file created two days ago).
    """
    anomalies: list[Anomaly] = []
    created = parse_pdf_date(meta.get("creationDate"))
    modified = parse_pdf_date(meta.get("modDate"))
    now = datetime.now(timezone.utc)

    claimed = None
    if fields.registration_date:
        claimed = datetime.fromisoformat(fields.registration_date).replace(tzinfo=timezone.utc)
    elif fields.dates:
        claimed = min(
            datetime.fromisoformat(d).replace(tzinfo=timezone.utc) for d in fields.dates
        )
    file_born = modified or created
    if claimed and file_born and (file_born - claimed) > timedelta(days=365) \
            and (now - file_born) < timedelta(days=30):
        anomalies.append(Anomaly(
            code="META_POSSIBLE_BACKDATING",
            layer="tamper",
            severity=Severity.CRITICAL,
            title="Possible backdating",
            detail=(
                f"File was digitally created on {file_born.date()} — within the last 30 days — "
                f"but the document text claims a date of {claimed.date()}. "
                "A scan of a genuine old record is possible, but combined with other "
                "signals this pattern indicates fabrication."
            ),
            documents=[filename],
            evidence={"file_date": str(file_born), "claimed_date": str(claimed.date())},
        ))
    return anomalies


def error_level_analysis(
    filename: str, payload: bytes, quality: int = 90, scale: int = 18
) -> tuple[str | None, list[dict[str, int]], list[Anomaly]]:
    """Recompress the image and amplify the per-pixel error level.

    Edited/pasted regions recompress differently from the rest of the image
    and light up in the heatmap. Returns (base64 heatmap PNG, bounding boxes,
    anomalies).
    """
    img = Image.open(io.BytesIO(payload)).convert("RGB")

    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=quality)
    buf.seek(0)
    recompressed = Image.open(buf)

    diff = ImageChops.difference(img, recompressed)
    arr = np.asarray(diff, dtype=np.float32).max(axis=2)
    heat = np.clip(arr * scale, 0, 255).astype(np.uint8)

    # Grid-based hotspot detection: cells whose mean error level is far above
    # the image-wide mean are suspicious.
    cell = 32
    h, w = heat.shape
    mean_all = float(heat.mean()) or 1.0
    hot = np.zeros(((h + cell - 1) // cell, (w + cell - 1) // cell), dtype=bool)
    for gy in range(hot.shape[0]):
        for gx in range(hot.shape[1]):
            block = heat[gy * cell:(gy + 1) * cell, gx * cell:(gx + 1) * cell]
            if block.size and float(block.mean()) > max(4.5 * mean_all, 28.0):
                hot[gy, gx] = True

    regions: list[dict[str, int]] = []
    visited = np.zeros_like(hot)
    for gy in range(hot.shape[0]):
        for gx in range(hot.shape[1]):
            if not hot[gy, gx] or visited[gy, gx]:
                continue
            # Flood-fill the connected hot component into one bounding box.
            stack, ys, xs = [(gy, gx)], [], []
            visited[gy, gx] = True
            while stack:
                cy, cx = stack.pop()
                ys.append(cy)
                xs.append(cx)
                for ny, nx in ((cy-1, cx), (cy+1, cx), (cy, cx-1), (cy, cx+1)):
                    if 0 <= ny < hot.shape[0] and 0 <= nx < hot.shape[1] \
                            and hot[ny, nx] and not visited[ny, nx]:
                        visited[ny, nx] = True
                        stack.append((ny, nx))
            regions.append({
                "x": min(xs) * cell, "y": min(ys) * cell,
                "w": (max(xs) - min(xs) + 1) * cell, "h": (max(ys) - min(ys) + 1) * cell,
            })

    # Render heatmap (red channel) blended over a dimmed original.
    overlay = np.asarray(img, dtype=np.float32) * 0.35
    overlay[..., 0] = np.clip(overlay[..., 0] + heat.astype(np.float32), 0, 255)
    heat_img = Image.fromarray(overlay.astype(np.uint8))
    out = io.BytesIO()
    heat_img.save(out, "PNG")
    b64 = base64.b64encode(out.getvalue()).decode()

    anomalies: list[Anomaly] = []
    if regions:
        anomalies.append(Anomaly(
            code="ELA_EDITED_REGIONS",
            layer="tamper",
            severity=Severity.HIGH,
            title="Error Level Analysis found edited regions",
            detail=(
                f"{len(regions)} region(s) of this image recompress at a markedly "
                "different error level than the surrounding area — typical of "
                "content pasted or redrawn over the original (seals, numbers, signatures)."
            ),
            documents=[filename],
            evidence={"regions": regions},
        ))
    return b64, regions, anomalies
