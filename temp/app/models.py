"""Shared data models for the DocVerify pipeline."""

from __future__ import annotations

from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


class DocType(str, Enum):
    SALARY_SLIP = "salary_slip"
    BANK_STATEMENT = "bank_statement"
    LAND_RECORD = "land_record"
    ID_PROOF = "id_proof"
    LEGAL = "legal"
    UNKNOWN = "unknown"


class Severity(str, Enum):
    INFO = "info"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


SEVERITY_WEIGHTS: dict[Severity, int] = {
    Severity.INFO: 0,
    Severity.LOW: 6,
    Severity.MEDIUM: 14,
    Severity.HIGH: 26,
    Severity.CRITICAL: 40,
}


class Anomaly(BaseModel):
    """A single detected anomaly, attributable to a layer and document(s)."""

    code: str
    layer: str  # ingestion | tamper | cross_document | registry
    severity: Severity
    title: str
    detail: str
    documents: list[str] = Field(default_factory=list)  # filenames involved
    evidence: dict[str, Any] = Field(default_factory=dict)


class ExtractionMethod(str, Enum):
    """How a particular field value was obtained."""

    REGEX = "regex"            # Direct label-value regex match
    SEMANTIC = "semantic"      # BGE-small semantic matcher fallback
    MANUAL_REVIEW = "manual"   # Confidence below threshold; needs human review


class ExtractionStatus(str, Enum):
    """Outcome of the extraction + validation pipeline for one field."""

    OK = "ok"                          # Extracted and validated successfully
    VALIDATION_FAILED = "validation_failed"  # Value found but failed post-extraction checks
    LOW_CONFIDENCE = "low_confidence"  # Semantic score below threshold
    NOT_FOUND = "not_found"            # No candidate found by either method


class FieldMeta(BaseModel):
    """Provenance metadata for a single extracted field.

    Stored alongside the value in ExtractedFields.extraction_meta so that
    downstream reviewers and audit systems know *how confident* we are in
    each extracted value — without changing any field's type or semantics.

    ``manual_review`` is the single authoritative flag that tells downstream
    consumers (UI queues, audit logs, cross-check layer) whether a human must
    inspect this field before the value can be trusted.  It is set to True
    whenever:

      * the semantic confidence score is below HYBRID_CONFIDENCE_THRESHOLD, OR
      * post-extraction validation fails for any extraction method.

    It is intentionally separate from ``status`` so that callers can query it
    with a simple boolean check without pattern-matching on the enum.
    """

    method: ExtractionMethod
    # FIX (validation bug): confidence must be in [0.0, 1.0].
    # Previously an unconstrained float; a buggy caller could silently store
    # confidence=1.5 and corrupt manual_review logic downstream.
    confidence: float = Field(ge=0.0, le=1.0)
    validated: bool            # True if post-extraction validation passed
    status: ExtractionStatus
    matched_label: Optional[str] = None  # The label token that triggered the match
    # --- NEW: per-field manual review flag ---
    manual_review: bool = False  # True  → a human must verify this field's value


class ExtractedFields(BaseModel):
    """Structured fields pulled out of a document by Layer 1.

    The value fields (pan, applicant_name, …) are unchanged so that all
    downstream layers (cross_check, registry, forensics) continue to work
    without modification.

    extraction_meta carries per-field provenance.  Keys mirror field names.
    It is intentionally a plain dict so serialisation stays flat JSON and
    existing consumers that don't know about it are unaffected.
    """

    applicant_name: Optional[str] = None
    pan: Optional[str] = None
    cin: Optional[str] = None
    survey_number: Optional[str] = None
    monthly_income: Optional[float] = None
    # FIX (validation bug): salary_credits elements must be non-negative;
    # a negative credit value is nonsensical and would corrupt fraud-score
    # arithmetic in the cross-document layer without an explicit guard here.
    salary_credits: list[float] = Field(default_factory=list)
    registration_date: Optional[str] = None  # ISO date as claimed in text
    address: Optional[str] = None
    dates: list[str] = Field(default_factory=list)

    # --- NEW: additive, ignored by all existing downstream consumers ---
    extraction_meta: dict[str, FieldMeta] = Field(
        default_factory=dict,
        description="Per-field extraction provenance.  Keys are field names above.",
    )


class DocumentReport(BaseModel):
    """Per-document analysis result."""

    filename: str
    sha256: str
    doc_type: DocType
    page_count: int = 0
    text_chars: int = 0
    ocr_used: bool = False
    fields: ExtractedFields = Field(default_factory=ExtractedFields)
    metadata: dict[str, Any] = Field(default_factory=dict)
    anomalies: list[Anomaly] = Field(default_factory=list)
    # NOTE: ela_image comment previously said "images only" but OCR is also
    # applied to scanned PDF pages, so the heatmap can arise from PDFs too.
    # Updated comment only; field type and behaviour are unchanged.
    ela_image: Optional[str] = None  # base64 PNG heatmap (images and scanned PDFs)
    suspicious_regions: list[dict[str, int]] = Field(default_factory=list)


class CaseResult(BaseModel):
    """Full result for one loan-application case (a bundle of documents)."""

    case_id: str
    analyzed_at: str
    elapsed_seconds: float
    # FIX (validation bug): fraud_score must be in [0, 100].
    # Previously a plain int; Pydantic would silently accept 150 or -5,
    # which would break every UI band calculation and audit comparison.
    fraud_score: int = Field(ge=0, le=100)  # 0 (clean) .. 100 (almost certainly fraudulent)
    risk_band: str  # LOW | MEDIUM | HIGH | CRITICAL
    recommended_action: str
    recommendations: list[str]
    documents: list[DocumentReport]
    cross_document_anomalies: list[Anomaly]
    registry_anomalies: list[Anomaly]
    audit_entry: dict[str, Any]
