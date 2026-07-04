"""Case analyzer — turns a bundle of security EvidenceBundles into a CaseResult.

This is the model service's counterpart to the in-tree monolith's
``pipeline.analyze_case``.  The crucial difference: it never receives original
PDF bytes.  Each document arrives as an EvidenceBundle of *safe artifacts* the
security service already produced —

    { filename, sha256, page_count, native_text[], pdf_anomalies[],
      pdf_metadata, pages[] (flattened PNGs) }

and the analyzer runs everything that works on safe artifacts:

  L1  native text (or OCR fallback on the PNGs) → classify → field extraction
  L2  rehydrate security's pdf_anomalies · deferred backdating · ELA on PNGs
  L3  cross-document checks       L4  registry correlation
  L5  scoring + recommendations + (optional) LLM narrative
  L7  audit hash-chain entry
"""

from __future__ import annotations

import base64
import time
import uuid
from datetime import datetime, timezone

from pydantic import BaseModel, Field

from . import audit, cross_check, forensics, ingestion, insights, registry
from .llm import generate_underwriting_report
from .models import Anomaly, CaseResult, DocumentReport, DocType, Severity

#: A page whose native text layer has fewer stripped characters than this is
#: treated as scanned/image-only and sent to OCR on its flattened PNG.
NATIVE_TEXT_MIN = 20


# ---------------------------------------------------------------------------
# Inbound contract (mirrors security/evidence.py::EvidenceBundle)
# ---------------------------------------------------------------------------

class PdfAnomalyIn(BaseModel):
    code: str
    layer: str = "tamper"
    severity: str = "medium"
    title: str = ""
    detail: str = ""
    documents: list[str] = Field(default_factory=list)
    evidence: dict = Field(default_factory=dict)


class EvidenceBundleIn(BaseModel):
    filename: str = "document.pdf"
    sha256: str = ""
    page_count: int = 0
    native_text: list[str] = Field(default_factory=list)
    pdf_anomalies: list[PdfAnomalyIn] = Field(default_factory=list)
    pdf_metadata: dict = Field(default_factory=dict)
    pages: list[str] = Field(default_factory=list)  # base64 PNGs (flattened, safe)


# ---------------------------------------------------------------------------
# Per-document analysis
# ---------------------------------------------------------------------------

def _acquire_text(bundle: EvidenceBundleIn) -> tuple[str, bool]:
    """Prefer the exact native text; OCR a flattened page only when it's thin."""
    parts: list[str] = []
    ocr_used = False
    n = max(len(bundle.native_text), len(bundle.pages))
    for i in range(n):
        native_i = bundle.native_text[i] if i < len(bundle.native_text) else ""
        if len(native_i.strip()) >= NATIVE_TEXT_MIN:
            parts.append(native_i)
        elif i < len(bundle.pages) and ingestion.TESSERACT_AVAILABLE:
            try:
                parts.append(ingestion.ocr_png(base64.b64decode(bundle.pages[i])))
                ocr_used = True
            except Exception:
                parts.append(native_i)
        else:
            parts.append(native_i)
    return "\n".join(parts), ocr_used


def _rehydrate(bundle: EvidenceBundleIn) -> list[Anomaly]:
    """Turn the security service's forensic dicts back into Anomaly objects."""
    out: list[Anomaly] = []
    for a in bundle.pdf_anomalies:
        out.append(Anomaly(
            code=a.code,
            layer=a.layer,
            severity=Severity(a.severity),
            title=a.title,
            detail=a.detail,
            documents=a.documents or [bundle.filename],
            evidence=a.evidence,
        ))
    return out


def _run_ela(report: DocumentReport, bundle: EvidenceBundleIn) -> None:
    """Error Level Analysis on the flattened page PNGs (image-only forgery).

    Runs *only* on pages whose native text layer is thin — i.e. scanned or
    photographed pages, where JPEG-recompression splicing is what ELA detects.
    A page with a real text layer is vector content that CDR just rasterized;
    running ELA on it merely lights up text edges (false positives), and any
    tampering of vector text was already caught upstream by security's
    metadata/font forensics.  Native-text thinness is the same signal that
    gates the OCR fallback, so ELA and OCR fire on exactly the scanned pages.
    """
    all_regions: list[dict[str, int]] = []
    for idx, png_b64 in enumerate(bundle.pages, start=1):
        native_i = bundle.native_text[idx - 1] if idx - 1 < len(bundle.native_text) else ""
        if len(native_i.strip()) >= NATIVE_TEXT_MIN:
            continue  # vector-text page — ELA would false-positive on text edges
        try:
            heat, regions, anomalies = forensics.error_level_analysis(
                bundle.filename, base64.b64decode(png_b64)
            )
        except Exception:
            continue
        if report.ela_image is None:
            report.ela_image = heat
        if regions:
            all_regions.extend(regions)
            for a in anomalies:
                a.evidence = {**a.evidence, "page": idx}
                report.anomalies.append(a)
    report.suspicious_regions = all_regions


def _analyze_document(bundle: EvidenceBundleIn) -> DocumentReport:
    report = DocumentReport(
        filename=bundle.filename,
        sha256=bundle.sha256,
        doc_type=DocType.UNKNOWN,
    )

    # Layer 1 — text acquisition, classification, field extraction.
    text, ocr_used = _acquire_text(bundle)
    report.page_count = bundle.page_count or len(bundle.pages)
    report.text_chars = len(text)
    report.ocr_used = ocr_used
    report.doc_type = ingestion.classify(text, bundle.filename)
    report.fields = ingestion.extract_fields(text, report.doc_type)
    report.metadata = {k: v for k, v in bundle.pdf_metadata.items() if v}

    # Layer 2 — forensics: upstream PDF-native findings + deferred backdating + ELA.
    report.anomalies.extend(_rehydrate(bundle))
    report.anomalies.extend(
        forensics.backdating_from_metadata(bundle.filename, bundle.pdf_metadata, report.fields)
    )
    _run_ela(report, bundle)

    return report


# ---------------------------------------------------------------------------
# Case-level analysis
# ---------------------------------------------------------------------------

def analyze_bundles(bundles: list[EvidenceBundleIn], case_id: str | None = None) -> CaseResult:
    started = time.monotonic()
    case_id = case_id or uuid.uuid4().hex[:12]

    documents = [_analyze_document(b) for b in bundles]

    # Layers 3 & 4 — bundle-level checks.
    cross_anomalies = cross_check.run(documents)
    registry_anomalies = registry.run(documents)

    everything = (
        [a for d in documents for a in d.anomalies]
        + cross_anomalies
        + registry_anomalies
    )

    # Layer 5 — scoring and insights.
    score = insights.fraud_score(everything)
    band = insights.risk_band(score)

    llm_input = {
        "fraud_score": score,
        "risk_band": band,
        "documents": [
            {
                "filename": d.filename,
                "doc_type": d.doc_type.value,
                "fields": d.fields.model_dump(),
            }
            for d in documents
        ],
        "anomalies": [
            {"code": a.code, "severity": a.severity.value, "detail": a.detail}
            for a in everything
        ],
        "recommended_actions": insights.recommendations(everything),
    }

    try:
        llm_summary = generate_underwriting_report(llm_input)
    except Exception as exc:
        llm_summary = {
            "executive_summary": "AI underwriting summary unavailable.",
            "key_findings": [],
            "risk_analysis": "",
            "recommended_actions": [],
            "manual_review_required": True,
            "underwriter_notes": f"LLM generation failed: {exc}",
        }

    # Layer 7 — audit trail (stays in the model service for now; moves to the
    # backend, alongside Postgres, in Step 5).
    entry = audit.record(
        case_id,
        {d.filename: d.sha256 for d in documents},
        score,
        band,
    )

    return CaseResult(
        case_id=case_id,
        analyzed_at=datetime.now(timezone.utc).isoformat(),
        elapsed_seconds=round(time.monotonic() - started, 2),
        fraud_score=score,
        risk_band=band,
        recommended_action=insights.recommended_action(score),
        recommendations=insights.recommendations(everything),
        documents=documents,
        cross_document_anomalies=cross_anomalies,
        registry_anomalies=registry_anomalies,
        audit_entry=entry,
        llm_summary=llm_summary,
    )
