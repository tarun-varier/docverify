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


# ---------------------------------------------------------------------------
# Copy-move detection — finds a region duplicated elsewhere on the same page
# (a pasted seal/stamp/signature), via block-matching + shift-vector voting.
# Pure numpy + PIL, same footprint as error_level_analysis above.
# ---------------------------------------------------------------------------

_CM_BLOCK_SIZE = 16
_CM_HAMMING_THRESHOLD = 4
_CM_MIN_SEPARATION = 48
_CM_MIN_CLUSTER_BLOCKS = 4
_CM_MAX_REGIONS = 5
_CM_MAX_DIM = 1600
# Rejects near-blank/background blocks -- whitespace would otherwise "match"
# everywhere. Units: variance of 0-255 grayscale pixel values.
_CM_MIN_BLOCK_VARIANCE = 25.0
# A bucket bigger than this is "too uniform to analyze" -- skip it rather
# than pay O(k^2) on a mostly-blank page that survived the variance filter.
_CM_MAX_BUCKET_SIZE = 256
# Raw-pixel verification threshold (mean absolute difference, 0-255 scale)
# applied to hash-bucketed candidates. The 8x8 average-hash is a coarse
# descriptor -- structurally similar but genuinely different content (e.g.
# two different 4-digit amounts in a table, or two blocks that each contain
# a thin ruling line at a similar relative position) can land within the
# Hamming threshold of each other without being real duplicates. A true
# copy-paste is pixel-identical (mean diff ~0); this rejects coincidental
# hash collisions the coarse hash alone can't distinguish.
_CM_MAX_PIXEL_DIFF = 5.0
# A genuine paste (seal/stamp/signature) is a small, LOCALIZED region -- so a
# shift vector whose total matched-block count exceeds this is treated as
# periodic structural repetition (ruled lines, table grids), not a forgery,
# and its entire candidate set is discarded. This is what a fixed block grid
# needs to survive ruled tables specifically: any perfectly periodic ruled
# line WILL eventually re-align with the block grid at some shift (a beat
# frequency of gcd(line_spacing, block_size)), and that shift alone can
# produce far more matched blocks, aggregated across the page, than any
# realistic single paste would.
_CM_MAX_SHIFT_CANDIDATES = 40


def _average_hash(block: np.ndarray) -> int:
    """8x8 average-hash of a grayscale block (block edge must be a multiple of 8).

    Average-hash, not DCT: numpy has no DCT primitive (only FFT), and the
    target here is near-*exact* duplicate pixels -- a copy-pasted region
    re-rendered through the same CDR flatten -- where DCT's main advantage
    (robustness to smooth intensity/contrast shifts) isn't the dominant
    need. A few numpy ops, no new dependency.
    """
    edge = block.shape[0]
    factor = edge // 8
    pooled = block[: factor * 8, : factor * 8].reshape(8, factor, 8, factor).mean(axis=(1, 3))
    bits = pooled > pooled.mean()
    value = 0
    for bit in bits.flatten():
        value = (value << 1) | int(bit)
    return value


def detect_copy_move(
    filename: str,
    payload: bytes,
    block_size: int = _CM_BLOCK_SIZE,
    hamming_threshold: int = _CM_HAMMING_THRESHOLD,
    min_separation: int = _CM_MIN_SEPARATION,
    min_cluster_blocks: int = _CM_MIN_CLUSTER_BLOCKS,
    max_regions: int = _CM_MAX_REGIONS,
    max_shift_candidates: int = _CM_MAX_SHIFT_CANDIDATES,
) -> tuple[list[dict], list[Anomaly]]:
    """Detects a region duplicated elsewhere on the page (pasted seal/stamp).

    Runs on every page unconditionally (unlike error_level_analysis, which
    only matters on scanned/photographed pages) -- a pasted image region can
    appear on a vector-text PDF too.

    Algorithm: tile into non-overlapping blocks, hash each with an 8x8
    average-hash, find near-duplicate pairs via hash-bucketed comparison
    (avoids O(n^2) over the whole page), then cluster matched pairs by their
    shared shift vector using the same 4-neighbor flood-fill technique
    error_level_analysis already uses for its own hotspot clustering.

    False-positive controls, in the order they run:
      1. Reject low-variance/near-blank blocks before any matching.
      2. Verify raw-pixel similarity on hash-bucketed candidates, not just
         hash proximity -- the coarse 8x8 hash alone can't distinguish two
         genuinely different but structurally-similar blocks (e.g. two
         different amounts in a table) from a real duplicate.
      3. Minimum spatial separation between a matched pair's block centers
         (rejects blocks trivially matching their own near neighbors).
      4. Minimum cluster size before a shift-group's connected component
         counts as a finding (an isolated single-block match is noise).
      5. Maximum total matched blocks per shift vector -- see
         _CM_MAX_SHIFT_CANDIDATES. A ruled table's grid lines are perfectly
         periodic, so a fixed block grid inevitably finds *some* shift where
         they re-align (a beat frequency of gcd(line_spacing, block_size));
         that shift alone then produces far more matched blocks across the
         page than any realistic single paste would, and the whole shift is
         discarded rather than tuning around one specific line spacing.
      6. Cap on reported regions per page, largest cluster first.

    Why shift-vector clustering, combined with control 5 above, survives
    forms/letterheads/repeated logos: a genuine copy-paste produces a
    *handful* of *adjacent* blocks sharing the *same* shift -- a small solid
    region in shift-space. A repeating table/grid instead either scatters
    matches across many different shift magnitudes (column-width vs.
    row-height vs. diagonal intersections) that never cluster, or -- when
    the grid's periodicity happens to beat-align with the block grid at one
    particular shift -- produces a MUCH larger match volume at that shift
    than a targeted paste ever would, which control 5 catches. Even without
    control 5, isolated grid intersections are a full cell-width apart (with
    blank, already-excluded blocks between them) -- not 4-neighbor-adjacent,
    so they don't form a qualifying
    cluster. See model/tests/test_copy_move.py for the regression test.
    """
    img = Image.open(io.BytesIO(payload)).convert("L")
    w0, h0 = img.size
    scale = 1.0
    if max(w0, h0) > _CM_MAX_DIM:
        scale = _CM_MAX_DIM / max(w0, h0)
        img = img.resize((max(1, round(w0 * scale)), max(1, round(h0 * scale))),
                          Image.Resampling.BILINEAR)
    arr = np.asarray(img, dtype=np.float32)
    h, w = arr.shape

    n_by, n_bx = h // block_size, w // block_size
    if n_by < 1 or n_bx < 1:
        return [], []

    block_hash: dict[tuple[int, int], int] = {}
    block_pixels: dict[tuple[int, int], np.ndarray] = {}
    for by in range(n_by):
        for bx in range(n_bx):
            block = arr[by * block_size:(by + 1) * block_size, bx * block_size:(bx + 1) * block_size]
            if block.var() < _CM_MIN_BLOCK_VARIANCE:
                continue
            block_hash[(by, bx)] = _average_hash(block)
            block_pixels[(by, bx)] = block

    # Bucket by a coarse key (top bits of the hash) so near-duplicate hashes
    # -- not just bit-identical ones -- land together for comparison, while
    # still avoiding a full O(n^2) scan over every surviving block.
    buckets: dict[int, list[tuple[int, int]]] = {}
    for pos, hval in block_hash.items():
        buckets.setdefault(hval >> 48, []).append(pos)

    def _center(pos: tuple[int, int]) -> tuple[float, float]:
        by, bx = pos
        return (by * block_size + block_size / 2, bx * block_size + block_size / 2)

    # Group accepted pairs by their shared block-grid shift vector. Only
    # ordered pairs (pos_a < pos_b) are considered so each unordered pair is
    # counted once, with pos_a canonically the "source" side.
    shift_groups: dict[tuple[int, int], set[tuple[int, int]]] = {}
    for positions in buckets.values():
        if len(positions) > _CM_MAX_BUCKET_SIZE:
            continue  # too uniform to analyze
        ordered = sorted(positions)
        for i in range(len(ordered)):
            for j in range(i + 1, len(ordered)):
                pos_a, pos_b = ordered[i], ordered[j]
                if bin(block_hash[pos_a] ^ block_hash[pos_b]).count("1") > hamming_threshold:
                    continue
                # The hash is a candidate filter, not proof: verify the raw
                # pixels are actually near-identical before accepting, so
                # structurally-similar-but-different content (two different
                # amounts in a table, two blocks each containing a thin
                # ruling line) doesn't pass just because it hashes close.
                if np.mean(np.abs(block_pixels[pos_a] - block_pixels[pos_b])) > _CM_MAX_PIXEL_DIFF:
                    continue
                ca, cb = _center(pos_a), _center(pos_b)
                if ((ca[0] - cb[0]) ** 2 + (ca[1] - cb[1]) ** 2) ** 0.5 < min_separation:
                    continue
                shift = (pos_b[0] - pos_a[0], pos_b[1] - pos_a[1])
                shift_groups.setdefault(shift, set()).add(pos_a)

    clusters: list[tuple[tuple[int, int], list[tuple[int, int]]]] = []
    for shift, positions in shift_groups.items():
        if len(positions) > max_shift_candidates:
            continue  # periodic structural repetition, not a targeted paste
        remaining = set(positions)
        while remaining:
            start = next(iter(remaining))
            remaining.discard(start)
            stack, component = [start], [start]
            while stack:
                cy, cx = stack.pop()
                for neighbor in ((cy - 1, cx), (cy + 1, cx), (cy, cx - 1), (cy, cx + 1)):
                    if neighbor in remaining:
                        remaining.discard(neighbor)
                        stack.append(neighbor)
                        component.append(neighbor)
            if len(component) >= min_cluster_blocks:
                clusters.append((shift, component))

    clusters.sort(key=lambda c: -len(c[1]))
    clusters = clusters[:max_regions]

    inv_scale = 1.0 / scale
    regions: list[dict] = []
    for (dy, dx), component in clusters:
        ys = [p[0] for p in component]
        xs = [p[1] for p in component]
        src_x, src_y = min(xs) * block_size, min(ys) * block_size
        src_w = (max(xs) - min(xs) + 1) * block_size
        src_h = (max(ys) - min(ys) + 1) * block_size
        dst_x, dst_y = src_x + dx * block_size, src_y + dy * block_size
        regions.append({
            "source": {"x": round(src_x * inv_scale), "y": round(src_y * inv_scale),
                       "w": round(src_w * inv_scale), "h": round(src_h * inv_scale)},
            "destination": {"x": round(dst_x * inv_scale), "y": round(dst_y * inv_scale),
                            "w": round(src_w * inv_scale), "h": round(src_h * inv_scale)},
            "shift": {"dx": round(dx * block_size * inv_scale), "dy": round(dy * block_size * inv_scale)},
            "block_count": len(component),
        })

    anomalies: list[Anomaly] = []
    if regions:
        anomalies.append(Anomaly(
            code="COPY_MOVE_REGION",
            layer="tamper",
            severity=Severity.HIGH,
            title="Possible copy-move (pasted/duplicated) region detected",
            detail=(
                f"{len(regions)} region(s) of this page appear to be near-identical "
                "copies of another region shifted to a different position — typical "
                "of a pasted seal, stamp, or signature."
            ),
            documents=[filename],
            evidence={"regions": regions},
        ))
    return regions, anomalies
