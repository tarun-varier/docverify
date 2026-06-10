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


class ExtractedFields(BaseModel):
    """Structured fields pulled out of a document by Layer 1."""

    applicant_name: Optional[str] = None
    pan: Optional[str] = None
    cin: Optional[str] = None
    survey_number: Optional[str] = None
    monthly_income: Optional[float] = None
    salary_credits: list[float] = Field(default_factory=list)
    registration_date: Optional[str] = None  # ISO date as claimed in text
    address: Optional[str] = None
    dates: list[str] = Field(default_factory=list)


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
    ela_image: Optional[str] = None  # base64 PNG heatmap, images only
    suspicious_regions: list[dict[str, int]] = Field(default_factory=list)


class CaseResult(BaseModel):
    """Full result for one loan-application case (a bundle of documents)."""

    case_id: str
    analyzed_at: str
    elapsed_seconds: float
    fraud_score: int  # 0 (clean) .. 100 (almost certainly fraudulent)
    risk_band: str  # LOW | MEDIUM | HIGH | CRITICAL
    recommended_action: str
    recommendations: list[str]
    documents: list[DocumentReport]
    cross_document_anomalies: list[Anomaly]
    registry_anomalies: list[Anomaly]
    audit_entry: dict[str, Any]
