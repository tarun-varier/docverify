"""DocVerify canonical schema — the single source of truth for all four areas.

Authoring: Pydantic models in :mod:`schema.models` (snake_case attributes,
camelCase wire/JSON/TypeScript via :class:`schema._base.CanonicalModel`).

Generate the downstream artifacts (JSON Schema + ``frontend/src/lib/schema.ts``)
with::

    uv run python -m schema.generate

Each area works against the slice it needs (see SCHEMA.md):

* ``ML_MODELS``  — what the ingestion/forensic/registry detectors fill.
* ``BLOCKCHAIN`` — the audit-ledger record.
* ``BACKEND``    — the analysis result + orchestration shapes.
* ``FRONTEND``   — the full read model the UI renders.
"""

from __future__ import annotations

from . import enums
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
    Severity,
    SEVERITY_WEIGHTS,
    UserRole,
    UserStatus,
    anomaly_category,
    coerce_severity,
    doc_category,
    risk_band,
)
from .models import (
    Anomaly,
    AnomalyRegion,
    Applicant,
    AuditEntry,
    BoundingBox,
    Case,
    CaseResult,
    Conflict,
    Decision,
    Document,
    DocumentMetadata,
    ExternalCheck,
    ExtractedFields,
    Integration,
    Loan,
    User,
    build_case,
)

# Per-area abstraction: the models each team primarily works with. The schema is
# shared; these tuples document the natural slice (and feed the codegen).
ML_MODELS = (ExtractedFields, Anomaly, AnomalyRegion, BoundingBox, Document)
BLOCKCHAIN = (AuditEntry,)
BACKEND = (CaseResult, Document, Anomaly, ExternalCheck, Conflict, AuditEntry)
FRONTEND = (
    Case, Document, Anomaly, Conflict, ExternalCheck, Decision,
    AnomalyRegion, BoundingBox, DocumentMetadata, ExtractedFields,
    User, Integration, Applicant, Loan, AuditEntry,
)

# Every top-level model that gets a generated TypeScript type.
ALL_MODELS = (
    BoundingBox, AnomalyRegion, DocumentMetadata, ExtractedFields,
    Anomaly, Document, ExternalCheck, Conflict, AuditEntry, CaseResult,
    Applicant, Loan, Decision, Case, User, Integration,
)

__all__ = [
    "enums",
    # enums
    "AnomalyCategory", "AnomalyLayer", "CaseStatus", "DecisionType",
    "DocCategory", "DocType", "ExternalCheckStatus", "IntegrationStatus",
    "LoanType", "RiskBand", "Severity", "SEVERITY_WEIGHTS", "UserRole",
    "UserStatus", "anomaly_category", "coerce_severity", "doc_category",
    "risk_band",
    # models
    "Anomaly", "AnomalyRegion", "Applicant", "AuditEntry", "BoundingBox",
    "Case", "CaseResult", "Conflict", "Decision", "Document",
    "DocumentMetadata", "ExternalCheck", "ExtractedFields", "Integration",
    "Loan", "User", "build_case",
    # groupings
    "ML_MODELS", "BLOCKCHAIN", "BACKEND", "FRONTEND", "ALL_MODELS",
]
