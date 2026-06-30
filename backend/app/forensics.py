"""Layer 2 — Tamper & forgery detection.

Three sub-detectors:
  * Metadata forensics  — editing software, creation/modification gaps,
    backdating vs dates claimed in the document text, incremental updates.
  * Visual forgery      — font/size outliers inside a PDF text layer.
  * Error Level Analysis — JPEG recompression differential for images,
    returning a heatmap and bounding boxes of suspicious regions.
"""

from __future__ import annotations

import base64
import io
import re
from datetime import datetime, timedelta, timezone

import fitz
import numpy as np
from PIL import Image, ImageChops

from .models import Anomaly, ExtractedFields, Severity

# Software whose presence in PDF metadata suggests post-issuance editing.
_EDITING_SOFTWARE = [
    "photoshop", "canva", "gimp", "illustrator", "inkscape", "sejda",
    "ilovepdf", "smallpdf", "pdfescape", "foxit phantompdf", "pdf-xchange editor",
]

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


def analyze_pdf_metadata(
    filename: str, payload: bytes, fields: ExtractedFields
) -> tuple[dict, list[Anomaly]]:
    anomalies: list[Anomaly] = []
    doc = fitz.open(stream=payload, filetype="pdf")
    meta = dict(doc.metadata or {})
    doc.close()

    producer = (meta.get("producer") or "").lower()
    creator = (meta.get("creator") or "").lower()
    created = parse_pdf_date(meta.get("creationDate"))
    modified = parse_pdf_date(meta.get("modDate"))
    now = datetime.now(timezone.utc)

    for software in _EDITING_SOFTWARE:
        if software in producer or software in creator:
            anomalies.append(Anomaly(
                code="META_EDITING_SOFTWARE",
                layer="tamper",
                severity=Severity.HIGH,
                title="Document touched by an image/PDF editor",
                detail=(
                    f"PDF metadata names '{software.title()}' as producer/creator. "
                    "Official records are not normally re-exported through design tools."
                ),
                documents=[filename],
                evidence={"producer": meta.get("producer"), "creator": meta.get("creator")},
            ))
            break

    if created and modified and (modified - created) > timedelta(days=1):
        anomalies.append(Anomaly(
            code="META_MODIFIED_AFTER_CREATION",
            layer="tamper",
            severity=Severity.MEDIUM,
            title="PDF modified long after creation",
            detail=(
                f"Created {created.date()} but last modified {modified.date()} "
                f"({(modified - created).days} days later) — content was changed after issuance."
            ),
            documents=[filename],
            evidence={"created": str(created), "modified": str(modified)},
        ))

    # Backdating: file digitally created recently while the text claims an old
    # registration date (e.g. claims 2019, file created two days ago).
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

    # Incremental updates: each save-in-place appends a new %%EOF.
    eof_count = payload.count(b"%%EOF")
    if eof_count > 2:
        anomalies.append(Anomaly(
            code="META_INCREMENTAL_UPDATES",
            layer="tamper",
            severity=Severity.LOW,
            title="Multiple incremental saves detected",
            detail=f"PDF contains {eof_count} end-of-file markers, i.e. it was re-saved "
                   f"{eof_count - 1} times after original generation.",
            documents=[filename],
            evidence={"eof_markers": eof_count},
        ))

    return meta, anomalies


def analyze_fonts(filename: str, payload: bytes) -> list[Anomaly]:
    """Flag outlier fonts: a font used for a tiny fraction of characters on a
    page that otherwise uses a single consistent font — typical of pasted-in
    or overwritten text."""
    anomalies: list[Anomaly] = []
    doc = fitz.open(stream=payload, filetype="pdf")
    try:
        for page_no, page in enumerate(doc, start=1):
            usage: dict[str, int] = {}
            samples: dict[str, str] = {}
            for block in page.get_text("dict")["blocks"]:
                for line in block.get("lines", []):
                    for span in line.get("spans", []):
                        key = f"{span['font']}@{round(span['size'], 1)}"
                        usage[key] = usage.get(key, 0) + len(span["text"])
                        samples.setdefault(key, span["text"].strip()[:40])
            total = sum(usage.values())
            if total < 100 or len(usage) < 2:
                continue
            dominant_key = max(usage, key=lambda k: usage[k])
            if usage[dominant_key] / total < 0.6:
                continue  # genuinely multi-font layout, not an outlier pattern

            def family(key: str) -> str:
                # "Helvetica-Bold@10.0" -> "helvetica": bold/italic variants of
                # the dominant face are normal layout, not tampering.
                return key.split("@")[0].split("-")[0].split("+")[-1].lower()

            for key, count in usage.items():
                if family(key) == family(dominant_key):
                    continue
                if count / total < 0.2 and count <= 60:
                    anomalies.append(Anomaly(
                        code="FONT_OUTLIER",
                        layer="tamper",
                        severity=Severity.MEDIUM,
                        title="Inconsistent font detected",
                        detail=(
                            f"Page {page_no}: text \"{samples[key]}\" uses font {key}, "
                            f"unlike the rest of the page — consistent with text being "
                            "overwritten or pasted in after generation."
                        ),
                        documents=[filename],
                        evidence={"page": page_no, "font": key, "chars": count,
                                  "sample": samples[key]},
                    ))
    finally:
        doc.close()
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
