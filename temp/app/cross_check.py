"""Layer 3 — Cross-document anomaly detection.

Most systems check one document at a time; this layer connects the bundle:
salary slip vs bank statement, identity fields across documents, land
record internal consistency.
"""

from __future__ import annotations

import difflib
from datetime import date, datetime

from .models import Anomaly, DocType, DocumentReport, Severity


def _norm_name(name: str) -> str:
    return " ".join(name.lower().replace(".", " ").split())


def _names_match(a: str, b: str) -> bool:
    na, nb = _norm_name(a), _norm_name(b)
    if na == nb or set(na.split()) <= set(nb.split()) or set(nb.split()) <= set(na.split()):
        return True
    return difflib.SequenceMatcher(None, na, nb).ratio() > 0.85


def run(docs: list[DocumentReport], today: date | None = None) -> list[Anomaly]:
    today = today or date.today()
    anomalies: list[Anomaly] = []

    by_type: dict[DocType, list[DocumentReport]] = {}
    for d in docs:
        by_type.setdefault(d.doc_type, []).append(d)

    # --- Income: salary slip claim vs salary credits in the bank statement.
    slips = by_type.get(DocType.SALARY_SLIP, [])
    statements = by_type.get(DocType.BANK_STATEMENT, [])
    for slip in slips:
        claimed = slip.fields.monthly_income
        if not claimed:
            continue
        for stmt in statements:
            credits = stmt.fields.salary_credits
            if not credits:
                continue
            avg_credit = sum(credits) / len(credits)
            deviation = abs(claimed - avg_credit) / claimed
            if deviation > 0.25:
                anomalies.append(Anomaly(
                    code="INCOME_MISMATCH",
                    layer="cross_document",
                    severity=Severity.CRITICAL if deviation > 0.4 else Severity.HIGH,
                    title="Income mismatch between salary slip and bank statement",
                    detail=(
                        f"Salary slip claims ₹{claimed:,.0f}/month but the bank statement "
                        f"shows average salary credits of ₹{avg_credit:,.0f} "
                        f"({deviation:.0%} deviation)."
                    ),
                    documents=[slip.filename, stmt.filename],
                    evidence={"claimed": claimed, "average_credit": round(avg_credit, 2),
                              "credits_seen": credits},
                ))

    # --- Identity: names must agree across every document that states one.
    named = [(d.filename, d.fields.applicant_name) for d in docs if d.fields.applicant_name]
    for i in range(len(named)):
        for j in range(i + 1, len(named)):
            (fa, na), (fb, nb) = named[i], named[j]
            if not _names_match(na, nb):
                anomalies.append(Anomaly(
                    code="NAME_MISMATCH",
                    layer="cross_document",
                    severity=Severity.HIGH,
                    title="Name inconsistency across documents",
                    detail=f"'{na}' on {fa} does not match '{nb}' on {fb}.",
                    documents=[fa, fb],
                    evidence={"names": [na, nb]},
                ))

    # --- PAN: every document quoting a PAN must quote the same one.
    pans = {(d.filename, d.fields.pan) for d in docs if d.fields.pan}
    distinct = {p for _, p in pans}
    if len(distinct) > 1:
        anomalies.append(Anomaly(
            code="PAN_MISMATCH",
            layer="cross_document",
            severity=Severity.CRITICAL,
            title="Conflicting PAN numbers in the bundle",
            detail=f"Documents quote {len(distinct)} different PANs: {', '.join(sorted(distinct))}.",
            documents=sorted(f for f, _ in pans),
            evidence={"pans": sorted(distinct)},
        ))

    # --- Address consistency across documents that state one.
    addressed = [(d.filename, d.fields.address) for d in docs if d.fields.address]
    for i in range(len(addressed)):
        for j in range(i + 1, len(addressed)):
            (fa, aa), (fb, ab) = addressed[i], addressed[j]
            if difflib.SequenceMatcher(None, aa.lower(), ab.lower()).ratio() < 0.5:
                anomalies.append(Anomaly(
                    code="ADDRESS_MISMATCH",
                    layer="cross_document",
                    severity=Severity.MEDIUM,
                    title="Address inconsistency across documents",
                    detail=f"Address on {fa} ('{aa}') differs substantially from {fb} ('{ab}').",
                    documents=[fa, fb],
                    evidence={"addresses": [aa, ab]},
                ))

    # --- Land record: ownership registered suspiciously close to application.
    for land in by_type.get(DocType.LAND_RECORD, []):
        reg = land.fields.registration_date
        if reg:
            days = (today - datetime.fromisoformat(reg).date()).days
            if 0 <= days <= 60:
                anomalies.append(Anomaly(
                    code="RECENT_OWNERSHIP_CHANGE",
                    layer="cross_document",
                    severity=Severity.HIGH,
                    title="Land ownership changed shortly before application",
                    detail=(
                        f"Land record registration date is {reg}, only {days} day(s) "
                        "before this application. High flip risk."
                    ),
                    documents=[land.filename],
                    evidence={"registration_date": reg, "days_before_application": days},
                ))

    return anomalies
