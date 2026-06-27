"""Canonical enumerations, severity weights, score banding and the small lookup
tables that keep the four areas speaking the same vocabulary.

Every value here is the literal string that appears on the wire and in the
generated TypeScript, so changing one is a cross-team contract change.
"""

from __future__ import annotations

from enum import Enum


# --------------------------------------------------------------------------- #
# Risk vocabulary                                                             #
# --------------------------------------------------------------------------- #

class RiskBand(str, Enum):
    """Case-level risk and per-anomaly severity as shown to the underwriter.

    This is the frontend's ``RiskLevel``. Four levels, lower-case, so the UI can
    look up ``var(--risk-<value>)`` directly.
    """

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class Severity(str, Enum):
    """Internal scoring scale. Adds ``info`` (weight 0) over :class:`RiskBand`.

    Detectors only ever emit ``low``..``critical``; ``info`` exists so a future
    non-scoring note has a home. Not part of the wire contract — anomalies are
    published with a :class:`RiskBand` severity.
    """

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


# Canonical score -> band thresholds. The ML scoring engine, the backend and the
# frontend MUST all use these exact cut-offs (see fraud_score / risk_band).
RISK_BAND_THRESHOLDS: list[tuple[int, RiskBand]] = [
    (70, RiskBand.CRITICAL),
    (40, RiskBand.HIGH),
    (15, RiskBand.MEDIUM),
    (0, RiskBand.LOW),
]


def risk_band(score: int) -> RiskBand:
    """Map a 0–100 fraud score to its canonical band."""
    for floor, band in RISK_BAND_THRESHOLDS:
        if score >= floor:
            return band
    return RiskBand.LOW


def coerce_severity(severity: Severity | str) -> RiskBand:
    """Project an internal :class:`Severity` onto the published :class:`RiskBand`.

    ``info`` (which no detector emits today) folds into ``low``.
    """
    value = severity.value if isinstance(severity, Severity) else str(severity)
    return RiskBand.LOW if value == Severity.INFO.value else RiskBand(value)


# --------------------------------------------------------------------------- #
# Documents                                                                   #
# --------------------------------------------------------------------------- #

class DocType(str, Enum):
    """Fine-grained classification produced by the ML ingestion layer."""

    SALARY_SLIP = "salary_slip"
    BANK_STATEMENT = "bank_statement"
    LAND_RECORD = "land_record"
    ID_PROOF = "id_proof"
    LEGAL = "legal"
    UNKNOWN = "unknown"


class DocCategory(str, Enum):
    """Coarse upload bucket the officer files a document under (UI grouping)."""

    LAND = "land"
    LEGAL = "legal"
    FINANCIAL = "financial"


DOC_TYPE_CATEGORY: dict[DocType, DocCategory] = {
    DocType.SALARY_SLIP: DocCategory.FINANCIAL,
    DocType.BANK_STATEMENT: DocCategory.FINANCIAL,
    DocType.LAND_RECORD: DocCategory.LAND,
    DocType.ID_PROOF: DocCategory.LEGAL,
    DocType.LEGAL: DocCategory.LEGAL,
    DocType.UNKNOWN: DocCategory.LEGAL,
}


def doc_category(doc_type: DocType | str) -> DocCategory:
    key = DocType(doc_type) if not isinstance(doc_type, DocType) else doc_type
    return DOC_TYPE_CATEGORY.get(key, DocCategory.LEGAL)


# --------------------------------------------------------------------------- #
# Anomalies                                                                   #
# --------------------------------------------------------------------------- #

class AnomalyLayer(str, Enum):
    """Which detection layer/engine produced a finding (provenance, ML-facing)."""

    INGESTION = "ingestion"
    TAMPER = "tamper"
    CROSS_DOCUMENT = "cross_document"
    REGISTRY = "registry"


class AnomalyCategory(str, Enum):
    """How a finding is grouped for the underwriter (display-facing)."""

    TAMPER = "Tamper Detection"
    CROSS_DOCUMENT = "Cross-Document Conflict"
    METADATA = "Metadata Anomaly"
    REGISTRY = "Registry Mismatch"


_LAYER_CATEGORY: dict[AnomalyLayer, AnomalyCategory] = {
    AnomalyLayer.INGESTION: AnomalyCategory.TAMPER,
    AnomalyLayer.TAMPER: AnomalyCategory.TAMPER,
    AnomalyLayer.CROSS_DOCUMENT: AnomalyCategory.CROSS_DOCUMENT,
    AnomalyLayer.REGISTRY: AnomalyCategory.REGISTRY,
}

# Codes whose display category differs from their layer's default.
_CODE_CATEGORY: dict[str, AnomalyCategory] = {
    "META_EDITING_SOFTWARE": AnomalyCategory.METADATA,
    "META_POSSIBLE_BACKDATING": AnomalyCategory.METADATA,
    "META_MODIFIED_AFTER_CREATION": AnomalyCategory.METADATA,
}


def anomaly_category(code: str, layer: AnomalyLayer | str) -> AnomalyCategory:
    """Derive the display category from the machine code, falling back to layer."""
    if code in _CODE_CATEGORY:
        return _CODE_CATEGORY[code]
    key = AnomalyLayer(layer) if not isinstance(layer, AnomalyLayer) else layer
    return _LAYER_CATEGORY.get(key, AnomalyCategory.TAMPER)


# --------------------------------------------------------------------------- #
# Case lifecycle, decisions, external checks                                  #
# --------------------------------------------------------------------------- #

class CaseStatus(str, Enum):
    UPLOADING = "Uploading"
    PROCESSING = "Processing"
    READY_FOR_REVIEW = "Ready for Review"
    DECISION_RECORDED = "Decision Recorded"


class DecisionType(str, Enum):
    APPROVED = "Approved"
    APPROVED_WITH_CONDITIONS = "Approved with Conditions"
    ESCALATED = "Escalated"
    REJECTED = "Rejected"
    RESUBMISSION_REQUESTED = "Resubmission Requested"


class ExternalCheckStatus(str, Enum):
    PASSED = "passed"
    FAILED = "failed"
    INCONCLUSIVE = "inconclusive"


class LoanType(str, Enum):
    HOME = "Home Loan"
    BUSINESS = "Business Loan"
    PERSONAL = "Personal Loan"
    AUTO = "Auto Loan"


# --------------------------------------------------------------------------- #
# People & integrations                                                       #
# --------------------------------------------------------------------------- #

class UserRole(str, Enum):
    UNDERWRITER = "Underwriter"
    SENIOR_UNDERWRITER = "Senior Underwriter"
    ADMIN = "Admin"


class UserStatus(str, Enum):
    ACTIVE = "Active"
    INACTIVE = "Inactive"


class IntegrationStatus(str, Enum):
    CONNECTED_TEST = "Connected (Test)"
    PENDING = "Pending"
    DISCONNECTED = "Disconnected"
