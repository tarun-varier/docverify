"""The EvidenceBundle contract returned by the security service's ``/scan``.

This is the wire boundary of the core architectural principle: **only the
security service ever touches original (possibly hostile) PDF bytes.**
Everything downstream (the model analyzer) works exclusively on the *safe
artifacts* in this bundle — flattened page PNGs, the extracted native text, the
forensic findings, and the raw metadata — and never receives the original file.

It is defined here as a service-local Pydantic model rather than imported from
the canonical ``schema/`` package because the services build from isolated
Docker contexts and cannot share a root-level Python package without
restructuring those contexts.  The contract therefore travels as JSON over HTTP,
which is the natural boundary between microservices.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class PdfAnomaly(BaseModel):
    """One forensic finding, in the in-tree pipeline's ``Anomaly`` shape.

    Kept structurally identical to ``backend/pipeline/models.py::Anomaly`` (minus
    the enum types, which serialise to their string values anyway) so the model
    service can rehydrate these dicts into canonical ``Anomaly`` objects.
    """

    code: str
    layer: str = "tamper"
    severity: str  # info | low | medium | high | critical
    title: str
    detail: str
    documents: list[str] = Field(default_factory=list)
    evidence: dict[str, Any] = Field(default_factory=dict)


class EvidenceBundle(BaseModel):
    """Safe-artifact contract emitted after static-analysis + CDR.

    ``pdf_anomalies`` and ``pdf_metadata`` are produced on the *original* PDF,
    before CDR flattened it into ``pages``.  ``native_text`` is the PDF's text
    layer, per page — exact where present, thin/empty for scanned PDFs (a signal
    for the model service to fall back to OCR on ``pages``).
    """

    status: str = "CLEAN_AND_SANITIZED"
    sha256: str
    page_count: int
    native_text: list[str] = Field(default_factory=list)
    pdf_anomalies: list[PdfAnomaly] = Field(default_factory=list)
    pdf_metadata: dict[str, Any] = Field(default_factory=dict)
    pages: list[str] = Field(default_factory=list)  # page_pngs_b64 (flattened, safe)
