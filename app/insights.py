"""Layer 5 — Fraud scoring and intelligent underwriting insights.

Turns the raw anomaly list into a 0–100 Fraud Confidence Score, a risk
band, and actionable recommendations for the underwriter.
"""

from __future__ import annotations

from .models import SEVERITY_WEIGHTS, Anomaly, Severity

# Anomaly code -> concrete underwriting action.
_ACTION_TEMPLATES: dict[str, str] = {
    "META_EDITING_SOFTWARE": "Request the original document directly from the issuing authority.",
    "META_POSSIBLE_BACKDATING": "Treat claimed document date as unverified; demand a certified copy.",
    "META_MODIFIED_AFTER_CREATION": "Ask the applicant to explain post-issuance modifications.",
    "FONT_OUTLIER": "Manually inspect the flagged text fields against a reference copy.",
    "ELA_EDITED_REGIONS": "Review the highlighted regions; request the physical original.",
    "INCOME_MISMATCH": "Obtain 6 months of verified bank statements via account aggregator.",
    "NAME_MISMATCH": "Signature/name mismatch across documents. Recommend video KYC.",
    "PAN_MISMATCH": "Multiple PANs in one bundle. Escalate to fraud-prevention unit.",
    "ADDRESS_MISMATCH": "Trigger physical address verification.",
    "RECENT_OWNERSHIP_CHANGE": "Land ownership changed shortly before application. High flip "
                               "risk — verify the seller chain and consider a title search.",
    "PAN_STRUCTURE_INVALID": "PAN is structurally invalid. Reject document and report.",
    "CIN_NOT_FOUND": "Employer not found in ROC records. Verify employment independently.",
    "CIN_INACTIVE": "Employer company is inactive at ROC. Verify employment independently.",
    "SURVEY_NOT_FOUND": "Survey number not in land registry. Order a manual title search.",
    "OWNERSHIP_CONFLICT": "Registry owner differs from applicant. Do not proceed without "
                          "a sub-registrar verified encumbrance certificate.",
    "REGISTRATION_DATE_CONFLICT": "Registration date conflicts with registry. Possible "
                                  "fabricated deed — escalate.",
}


def fraud_score(anomalies: list[Anomaly]) -> int:
    """Diminishing-returns sum of severity weights, capped at 100."""
    weights = sorted(
        (SEVERITY_WEIGHTS[a.severity] for a in anomalies), reverse=True
    )
    score = 0.0
    for rank, w in enumerate(weights):
        score += w * (0.85 ** rank)
    return min(100, round(score))


def risk_band(score: int) -> str:
    if score >= 70:
        return "CRITICAL"
    if score >= 40:
        return "HIGH"
    if score >= 15:
        return "MEDIUM"
    return "LOW"


def recommended_action(score: int) -> str:
    band = risk_band(score)
    return {
        "CRITICAL": "Decline / escalate to fraud-prevention unit before any disbursement.",
        "HIGH": "Hold disbursement; complete enhanced due diligence on every flagged item.",
        "MEDIUM": "Proceed with caution; resolve flagged items during standard underwriting.",
        "LOW": "Proceed with standard underwriting. No significant anomalies detected.",
    }[band]


def recommendations(anomalies: list[Anomaly]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    ordered = sorted(anomalies, key=lambda a: -SEVERITY_WEIGHTS[a.severity])
    for a in ordered:
        action = _ACTION_TEMPLATES.get(a.code)
        if action and a.code not in seen and a.severity != Severity.INFO:
            seen.add(a.code)
            out.append(action)
    return out
