"""PDF-native forensics (Layer 2) — runs *inside* the security service.

These detectors read the PDF's internal structure (metadata dates, producer/
creator strings, per-span fonts, incremental-save markers) and the native text
layer.  They must run on the **original bytes, before CDR flattens each page to
a PNG** — the flatten rasterizes the document and destroys exactly the structure
these checks depend on.

Only *field-independent* detectors live here.  The backdating check compares a
file's digital birth date against a registration date claimed *in the extracted
fields* (a Layer-1 output produced by the model service), so it cannot run here.
The raw metadata dates are carried in the EvidenceBundle instead, so the model
service can reconstruct that check downstream.

Ported from ``backend/pipeline/forensics.py`` (the in-tree monolith).  Anomalies
are emitted as plain dicts matching that module's ``Anomaly`` shape so the model
service can rehydrate them into canonical ``Anomaly`` objects without a shared
import (the services build from isolated Docker contexts).
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from typing import Any

import fitz  # PyMuPDF

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


def _anomaly(
    *, code: str, severity: str, title: str, detail: str,
    filename: str, evidence: dict[str, Any],
) -> dict[str, Any]:
    """Build one anomaly dict in the pipeline's ``Anomaly`` shape."""
    return {
        "code": code,
        "layer": "tamper",
        "severity": severity,
        "title": title,
        "detail": detail,
        "documents": [filename],
        "evidence": evidence,
    }


def _metadata_anomalies(
    filename: str, payload: bytes, meta: dict[str, Any]
) -> list[dict[str, Any]]:
    """Field-independent metadata forensics.

    Covers editing-software fingerprints, a modified-long-after-created gap, and
    incremental-save ``%%EOF`` counting.  The backdating check is intentionally
    omitted here (it needs Layer-1 extracted fields) — the ``creationDate`` /
    ``modDate`` values needed to reproduce it travel in the bundle's metadata.
    """
    anomalies: list[dict[str, Any]] = []

    producer = (meta.get("producer") or "").lower()
    creator = (meta.get("creator") or "").lower()
    created = parse_pdf_date(meta.get("creationDate"))
    modified = parse_pdf_date(meta.get("modDate"))

    for software in _EDITING_SOFTWARE:
        if software in producer or software in creator:
            anomalies.append(_anomaly(
                code="META_EDITING_SOFTWARE",
                severity="high",
                title="Document touched by an image/PDF editor",
                detail=(
                    f"PDF metadata names '{software.title()}' as producer/creator. "
                    "Official records are not normally re-exported through design tools."
                ),
                filename=filename,
                evidence={"producer": meta.get("producer"), "creator": meta.get("creator")},
            ))
            break

    if created and modified and (modified - created) > timedelta(days=1):
        anomalies.append(_anomaly(
            code="META_MODIFIED_AFTER_CREATION",
            severity="medium",
            title="PDF modified long after creation",
            detail=(
                f"Created {created.date()} but last modified {modified.date()} "
                f"({(modified - created).days} days later) — content was changed after issuance."
            ),
            filename=filename,
            evidence={"created": str(created), "modified": str(modified)},
        ))

    # Incremental updates: each save-in-place appends a new %%EOF.
    eof_count = payload.count(b"%%EOF")
    if eof_count > 2:
        anomalies.append(_anomaly(
            code="META_INCREMENTAL_UPDATES",
            severity="low",
            title="Multiple incremental saves detected",
            detail=f"PDF contains {eof_count} end-of-file markers, i.e. it was re-saved "
                   f"{eof_count - 1} times after original generation.",
            filename=filename,
            evidence={"eof_markers": eof_count},
        ))

    return anomalies


def _font_anomalies_for_page(
    filename: str, page_no: int, page: "fitz.Page"
) -> list[dict[str, Any]]:
    """Flag outlier fonts on one page: a font used for a tiny fraction of
    characters on a page that otherwise uses a single consistent font — typical
    of pasted-in or overwritten text."""
    anomalies: list[dict[str, Any]] = []
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
        return anomalies
    dominant_key = max(usage, key=lambda k: usage[k])
    if usage[dominant_key] / total < 0.6:
        return anomalies  # genuinely multi-font layout, not an outlier pattern

    def family(key: str) -> str:
        # "Helvetica-Bold@10.0" -> "helvetica": bold/italic variants of the
        # dominant face are normal layout, not tampering.
        return key.split("@")[0].split("-")[0].split("+")[-1].lower()

    for key, count in usage.items():
        if family(key) == family(dominant_key):
            continue
        if count / total < 0.2 and count <= 60:
            anomalies.append(_anomaly(
                code="FONT_OUTLIER",
                severity="medium",
                title="Inconsistent font detected",
                detail=(
                    f"Page {page_no}: text \"{samples[key]}\" uses font {key}, "
                    f"unlike the rest of the page — consistent with text being "
                    "overwritten or pasted in after generation."
                ),
                filename=filename,
                evidence={"page": page_no, "font": key, "chars": count,
                          "sample": samples[key]},
            ))
    return anomalies


def build_evidence(
    filename: str, payload: bytes
) -> tuple[dict[str, Any], list[str], list[dict[str, Any]]]:
    """Run PDF-native forensics + native-text extraction on the original bytes.

    Returns ``(metadata, native_text_per_page, pdf_anomalies)``.  Callers should
    treat this as best-effort: a forensics failure must never regress the
    security guarantee (static-analysis rejection + CDR flatten).
    """
    doc = fitz.open(stream=payload, filetype="pdf")
    try:
        meta = dict(doc.metadata or {})
        native_text: list[str] = []
        font_anomalies: list[dict[str, Any]] = []
        for page_no, page in enumerate(doc, start=1):
            native_text.append(page.get_text())
            font_anomalies.extend(_font_anomalies_for_page(filename, page_no, page))
    finally:
        doc.close()

    anomalies = _metadata_anomalies(filename, payload, meta) + font_anomalies
    return meta, native_text, anomalies
