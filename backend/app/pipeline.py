"""Orchestrates Layers 1-7 over a bundle of uploaded documents."""

from __future__ import annotations

import hashlib
import time
import uuid
from datetime import datetime, timezone

from . import audit, cross_check, forensics, ingestion, insights, registry
from .models import Anomaly, CaseResult, DocumentReport, DocType, Severity
from .llm import generate_underwriting_report


def _analyze_document(filename: str, payload: bytes) -> DocumentReport:
    report = DocumentReport(
        filename=filename,
        sha256=hashlib.sha256(payload).hexdigest(),
        doc_type=DocType.UNKNOWN,
    )

    # Layer 1 — ingestion, OCR, classification, field extraction.
    try:
        text, pages, ocr_used = ingestion.extract_text(filename, payload)
    except Exception as exc:
        report.anomalies.append(Anomaly(
            code="INGESTION_FAILED",
            layer="ingestion",
            severity=Severity.MEDIUM,
            title="Document could not be parsed",
            detail=f"{filename}: {exc}. Treat as unverifiable until a readable copy is provided.",
            documents=[filename],
        ))
        return report

    report.page_count = pages
    report.text_chars = len(text)
    report.ocr_used = ocr_used
    report.doc_type = ingestion.classify(text, filename)
    report.fields = ingestion.extract_fields(text, report.doc_type)

    # Layer 2 — tamper & forgery detection.
    is_image = any(filename.lower().endswith(ext) for ext in ingestion.IMAGE_EXTENSIONS)
    if is_image:
        ela_b64, regions, ela_anomalies = forensics.error_level_analysis(filename, payload)
        report.ela_image = ela_b64
        report.suspicious_regions = regions
        report.anomalies.extend(ela_anomalies)
    else:
        meta, meta_anomalies = forensics.analyze_pdf_metadata(filename, payload, report.fields)
        report.metadata = {k: v for k, v in meta.items() if v}
        report.anomalies.extend(meta_anomalies)
        report.anomalies.extend(forensics.analyze_fonts(filename, payload))

    return report


def analyze_case(files: list[tuple[str, bytes]]) -> CaseResult:
    started = time.monotonic()
    case_id = uuid.uuid4().hex[:12]

    documents = [_analyze_document(name, payload) for name, payload in files]

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
            {
                "code": a.code,
                "severity": a.severity.value,
                "detail": a.detail,
            }
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

    # Layer 7 — audit trail.
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
        llm_summary=llm_summary
    )
