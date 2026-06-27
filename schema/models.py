"""Canonical DocVerify domain models — the single contract shared by the ML,
blockchain, backend and frontend areas.

Authored Pydantic-first (snake_case attributes); the wire/JSON/TypeScript
contract is camelCase via :class:`~schema._base.CanonicalModel`. A handful of
fields carry an explicit alias where the established frontend name differs from
the mechanical camelCase (``filename`` → ``name``).

Grouping (each area imports the slice it needs — see SCHEMA.md):
  * Value objects      BoundingBox, AnomalyRegion, DocumentMetadata, ExtractedFields
  * ML / forensics     Anomaly, Document, ExternalCheck
  * Analysis           Conflict, CaseResult
  * Blockchain         AuditEntry
  * Case management    Applicant, Loan, Decision, Case
  * Admin              User, Integration
"""

from __future__ import annotations

from typing import Any, Optional

from pydantic import Field

from ._base import CanonicalModel
from .enums import (
    AnomalyCategory,
    AnomalyLayer,
    CaseStatus,
    DecisionType,
    DocCategory,
    DocType,
    ExternalCheckStatus,
    IntegrationStatus,
    LoanType,
    RiskBand,
    UserRole,
    UserStatus,
)


# --------------------------------------------------------------------------- #
# Value objects                                                               #
# --------------------------------------------------------------------------- #

class BoundingBox(CanonicalModel):
    """A rectangle over a document page.

    ``units`` distinguishes UI coordinates (``pct`` — 0..100 of page width/height,
    what the Document Viewer renders) from raw forensic pixels (``px``).
    """

    x: float
    y: float
    w: float
    h: float
    units: str = "pct"  # "pct" | "px"


class AnomalyRegion(CanonicalModel):
    """A flagged region drawn on a document page and linked to a finding."""

    id: str
    doc_id: str = ""
    page: int = 1
    label: str = ""
    box: BoundingBox
    source: Optional[str] = None  # ela | font | metadata | manual


class DocumentMetadata(CanonicalModel):
    """Document provenance shown in the viewer. ``raw`` keeps the full,
    detector-specific metadata dict the forensic layer extracted."""

    created: Optional[str] = None
    modified: Optional[str] = None
    software: Optional[str] = None
    pdf_version: Optional[str] = None
    raw: dict[str, Any] = Field(default_factory=dict)


class ExtractedFields(CanonicalModel):
    """Structured fields the ML ingestion layer pulls out of a document."""

    applicant_name: Optional[str] = None
    pan: Optional[str] = None
    cin: Optional[str] = None
    survey_number: Optional[str] = None
    monthly_income: Optional[float] = None
    salary_credits: list[float] = Field(default_factory=list)
    registration_date: Optional[str] = None  # ISO date as claimed in the text
    address: Optional[str] = None
    dates: list[str] = Field(default_factory=list)


# --------------------------------------------------------------------------- #
# ML / forensic findings                                                      #
# --------------------------------------------------------------------------- #

class Anomaly(CanonicalModel):
    """A single detected anomaly.

    ``code`` is the stable machine identifier the ML/registry layers emit;
    ``layer`` is which engine found it (provenance); ``category`` is how it is
    grouped for the underwriter (derive both from :mod:`schema.enums`).
    """

    id: str
    code: str = ""
    layer: AnomalyLayer
    category: AnomalyCategory
    severity: RiskBand
    title: str
    detail: str
    document_ids: list[str] = Field(default_factory=list)  # Document.id values
    evidence: dict[str, Any] = Field(default_factory=dict)


class Document(CanonicalModel):
    """Per-document report: the uploaded file plus everything found in it."""

    id: str  # stable within a case, e.g. "d1"
    filename: str = Field(alias="name")  # wire/UI name; populate_by_name keeps .filename
    sha256: str = ""
    doc_type: DocType = DocType.UNKNOWN
    category: DocCategory = DocCategory.LEGAL
    sub_score: int = 0  # per-document fraud sub-score, 0..100
    summary: str = ""
    size: str = ""  # human-readable, e.g. "1.8 MB"
    page_count: int = 0
    text_chars: int = 0
    ocr_used: bool = False
    fields: ExtractedFields = Field(default_factory=ExtractedFields)
    metadata: DocumentMetadata = Field(default_factory=DocumentMetadata)
    anomalies: list[Anomaly] = Field(default_factory=list)
    anomaly_regions: list[AnomalyRegion] = Field(default_factory=list)
    suspicious_regions: list[BoundingBox] = Field(default_factory=list)  # raw px (ELA)
    ela_image: Optional[str] = None  # base64 PNG heatmap, images only


class ExternalCheck(CanonicalModel):
    """Result of one external-registry correlation (PAN / CIN / land registry)."""

    check: str
    status: ExternalCheckStatus
    detail: str = ""


class Conflict(CanonicalModel):
    """A distilled cross-document contradiction for the report's conflict panel."""

    id: str
    description: str
    document_ids: list[str] = Field(default_factory=list)


# --------------------------------------------------------------------------- #
# Blockchain / audit                                                          #
# --------------------------------------------------------------------------- #

class AuditEntry(CanonicalModel):
    """One tamper-evident ledger record (hash-chained). The blockchain area owns
    this shape; the chain is computed over the snake_case JSON in app/audit.py."""

    case_id: str
    timestamp: str
    document_hashes: dict[str, str] = Field(default_factory=dict)
    fraud_score: int
    risk_band: RiskBand
    prev_hash: str
    entry_hash: str


# --------------------------------------------------------------------------- #
# Analysis output (backend pipeline)                                          #
# --------------------------------------------------------------------------- #

class CaseResult(CanonicalModel):
    """Full analysis result the pipeline produces for one bundle of documents.

    This is the analysis *slice* — it knows only what the documents reveal. The
    applicant/loan context and the decision are merged in at the :class:`Case`
    level by the case service (see :func:`build_case`).
    """

    case_id: str
    analyzed_at: str
    elapsed_seconds: float
    fraud_score: int  # 0 (clean) .. 100 (almost certainly fraudulent)
    risk_band: RiskBand
    recommended_action: str
    recommendations: list[str] = Field(default_factory=list)
    documents: list[Document] = Field(default_factory=list)
    cross_document_anomalies: list[Anomaly] = Field(default_factory=list)
    registry_anomalies: list[Anomaly] = Field(default_factory=list)
    external_checks: list[ExternalCheck] = Field(default_factory=list)
    audit_entry: AuditEntry

    def all_anomalies(self) -> list[Anomaly]:
        """Every finding across documents and bundle-level layers, flattened."""
        out: list[Anomaly] = []
        for d in self.documents:
            out.extend(d.anomalies)
        out.extend(self.cross_document_anomalies)
        out.extend(self.registry_anomalies)
        return out


# --------------------------------------------------------------------------- #
# Case management                                                             #
# --------------------------------------------------------------------------- #

class Applicant(CanonicalModel):
    """Applicant details captured at case creation (Screen 3)."""

    name: str
    pan: str
    aadhaar_masked: Optional[str] = None
    dob: Optional[str] = None
    contact: Optional[str] = None
    address: Optional[str] = None


class Loan(CanonicalModel):
    """Loan request details captured at case creation (Screen 3)."""

    loan_type: LoanType
    amount: float
    branch: Optional[str] = None
    officer: Optional[str] = None


class Decision(CanonicalModel):
    """The underwriter's recorded decision (Screen 8)."""

    type: DecisionType
    notes: str = ""
    by: str
    at: str


class Case(CanonicalModel):
    """The full case record — the primary read model for the frontend.

    Deliberately flat: applicant/loan context, the analysis projection and the
    decision live side by side so the dashboard and report screens read one
    object. Structured creation input uses :class:`Applicant` / :class:`Loan`.
    """

    id: str
    # Applicant + loan context (flat projection of Applicant/Loan)
    applicant: str  # applicant name
    pan: str = ""
    loan_type: str = ""  # display string; constrained set in LoanType
    loan_amount: float = 0
    branch: str = ""
    officer: str = ""
    submitted_at: str = ""
    # Lifecycle
    status: CaseStatus = CaseStatus.UPLOADING
    # Analysis projection
    score: int = 0
    risk: RiskBand = RiskBand.LOW
    docs: list[Document] = Field(default_factory=list)
    anomalies: list[Anomaly] = Field(default_factory=list)
    conflicts: list[Conflict] = Field(default_factory=list)
    external: list[ExternalCheck] = Field(default_factory=list)
    recommended_action: str = ""
    recommendations: list[str] = Field(default_factory=list)
    analyzed_at: Optional[str] = None
    elapsed_seconds: Optional[float] = None
    # Decision + audit
    decision: Optional[Decision] = None
    hash: str = ""
    audit_id: str = ""
    audit_entry: Optional[AuditEntry] = None


# --------------------------------------------------------------------------- #
# Admin                                                                       #
# --------------------------------------------------------------------------- #

class User(CanonicalModel):
    """A provisioned bank user (Admin panel, Screen 11)."""

    id: str
    name: str
    employee_id: str
    email: str
    role: UserRole
    branch: str = ""
    status: UserStatus = UserStatus.ACTIVE
    last_login: Optional[str] = None


class Integration(CanonicalModel):
    """External-registry integration status (Settings, Screen 12)."""

    name: str
    status: IntegrationStatus
    updated: Optional[str] = None


# --------------------------------------------------------------------------- #
# Assembly helper                                                             #
# --------------------------------------------------------------------------- #

def build_case(
    result: CaseResult,
    *,
    applicant: str,
    pan: str = "",
    loan_type: str = "",
    loan_amount: float = 0,
    branch: str = "",
    officer: str = "",
    submitted_at: str = "",
    status: CaseStatus = CaseStatus.READY_FOR_REVIEW,
    decision: Optional[Decision] = None,
) -> Case:
    """Merge an analysis :class:`CaseResult` with case-creation context into the
    flat :class:`Case` read model the frontend consumes."""
    conflicts = [
        Conflict(id=a.id, description=a.detail, document_ids=a.document_ids)
        for a in result.cross_document_anomalies
    ]
    return Case(
        id=result.case_id,
        applicant=applicant,
        pan=pan,
        loan_type=loan_type,
        loan_amount=loan_amount,
        branch=branch,
        officer=officer,
        submitted_at=submitted_at or result.analyzed_at,
        status=status,
        score=result.fraud_score,
        risk=result.risk_band,
        docs=result.documents,
        anomalies=result.all_anomalies(),
        conflicts=conflicts,
        external=result.external_checks,
        recommended_action=result.recommended_action,
        recommendations=result.recommendations,
        analyzed_at=result.analyzed_at,
        elapsed_seconds=result.elapsed_seconds,
        decision=decision,
        hash=result.audit_entry.entry_hash,
        audit_id=result.audit_entry.entry_hash[:12],
        audit_entry=result.audit_entry,
    )
