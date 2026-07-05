"""Layer 4 — Lightweight external correlation against mock registries.

Validates PAN structure, looks up CIN status and land survey numbers via a
RegistryAdapter. The default MockRegistryAdapter reads local JSON fixtures
under data/registries/; the adapter interface is deliberately thin so a real
implementation can re-point the same lookups at CERSAI, ROC and state
land-record APIs in production without touching run() or its caller.
"""

from __future__ import annotations

import hashlib
import json
import re
import time
from datetime import date
from pathlib import Path
from typing import Protocol

from .models import Anomaly, DocType, DocumentReport, Severity

REGISTRY_DIR = Path(__file__).resolve().parent.parent / "data" / "registries"

_PAN_STRUCTURE = re.compile(r"^[A-Z]{5}[0-9]{4}[A-Z]$")
# 4th character encodes holder type; these are the valid codes.
_PAN_HOLDER_TYPES = set("PCFHATBLJG")

# A land record's ownership change counts as "recent" relative to a document
# if it happened within this many days before the document's claimed date.
RECENCY_WINDOW_DAYS = 60


def _load(name: str) -> dict:
    path = REGISTRY_DIR / name
    if not path.exists():
        return {}
    return json.loads(path.read_text())


class RegistryTimeoutError(Exception):
    """A (simulated or real) registry lookup couldn't complete.

    Distinct from "not found": run() must not treat a timeout as the
    registry authoritatively saying a CIN/survey number doesn't exist —
    it degrades to a REGISTRY_LOOKUP_UNAVAILABLE anomaly instead of a false
    CIN_NOT_FOUND / SURVEY_NOT_FOUND.
    """


class RegistryAdapter(Protocol):
    """Lookup interface real registry clients (CERSAI, MCA-ROC, ...) satisfy.

    Returns the raw record dict, or None if genuinely absent from the
    registry, so run()'s existing dict-shaped checks need no changes when
    swapping adapters. May raise RegistryTimeoutError.
    """

    def lookup_cin(self, cin: str) -> dict | None: ...

    def lookup_land(self, survey_number: str) -> dict | None: ...


class MockRegistryAdapter:
    """Reads the local JSON fixtures. Optionally simulates latency/timeouts.

    Both simulation flags default off: run()'s default behavior (no adapter
    passed) is identical to a plain dict lookup, matching pre-adapter
    behavior exactly. Demo-mode simulation is an explicit opt-in at the
    call site, never in tests.

    When simulating, uses a SHA-1 digest of the lookup key (not the builtin
    hash()) so the simulated behavior is deterministic across runs — Python
    randomizes str hash() per-process unless PYTHONHASHSEED is fixed.
    """

    def __init__(self, *, simulate_latency: bool = False, simulate_flakiness: bool = False):
        self._simulate_latency = simulate_latency
        self._simulate_flakiness = simulate_flakiness
        self._cin_registry = _load("cin_registry.json")
        self._land_registry = _load("land_records.json")

    def _simulate(self, key: str) -> None:
        digest = int(hashlib.sha1(key.encode()).hexdigest(), 16)
        if self._simulate_latency:
            time.sleep(0.05 + (digest % 151) / 1000)  # 50-200ms, deterministic per key
        if self._simulate_flakiness and digest % 37 == 0:  # ~2.7% of keys, always the same ones
            raise RegistryTimeoutError(f"simulated registry timeout for {key!r}")

    def lookup_cin(self, cin: str) -> dict | None:
        self._simulate(f"cin:{cin}")
        return self._cin_registry.get(cin)

    def lookup_land(self, survey_number: str) -> dict | None:
        self._simulate(f"land:{survey_number}")
        record = self._land_registry.get(survey_number)
        if record is None:
            return None
        history = record.get("ownership_history") or []
        out = dict(record)
        if history:
            latest = max(history, key=lambda h: h["date"])
            out["owner"] = latest["owner"]
            out["last_transfer_date"] = latest["date"]
        return out


def _lookup_unavailable(filename: str, kind: str, key: str) -> Anomaly:
    return Anomaly(
        code="REGISTRY_LOOKUP_UNAVAILABLE",
        layer="registry",
        severity=Severity.INFO,
        title="Registry lookup unavailable",
        detail=f"The {kind} registry did not respond for '{key}' on {filename}; "
               "this field could not be corroborated externally.",
        documents=[filename],
        evidence={"kind": kind, "key": key},
    )


def _recent_ownership_change(doc: DocumentReport, f, record: dict) -> Anomaly | None:
    """Flags a land record whose ownership changed shortly before the document's
    own claimed date, per the registry's history — distinct from
    cross_check.RECENT_OWNERSHIP_CHANGE, which compares the document's claimed
    date against *today* rather than against registry data. Anomaly.code has
    no dedup registry and fraud_score collapses by code, so these two checks
    must use different codes or one would silently swallow the other's
    contribution to scoring.
    """
    history = record.get("ownership_history") or []
    doc_date = f.registration_date
    if not history or not doc_date:
        return None
    try:
        doc_date_parsed = date.fromisoformat(doc_date)
    except ValueError:
        return None
    # Only compare against transfers that had already happened as of the
    # document's date — a transfer *after* the document's date isn't "a
    # recent change before this application," it's registry data the
    # document predates.
    prior = [h for h in history if h.get("date") and h["date"] <= doc_date]
    if not prior:
        return None
    latest = max(prior, key=lambda h: h["date"])
    days = (doc_date_parsed - date.fromisoformat(latest["date"])).days
    if not (0 <= days <= RECENCY_WINDOW_DAYS):
        return None
    return Anomaly(
        code="REGISTRY_RECENT_OWNERSHIP_CHANGE",
        layer="registry",
        # Deliberately below cross_check's self-reported HIGH check: this is
        # a corroborating registry-sourced signal, not a direct admission,
        # and the two checks often fire together for one underlying fact —
        # stacking two HIGHs would over-weight it given fraud_score's
        # per-code-max design.
        severity=Severity.MEDIUM,
        title="Land registry shows an ownership change shortly before this document",
        detail=(
            f"Survey no. {f.survey_number} changed hands to '{latest['owner']}' on "
            f"{latest['date']} — only {days} day(s) before this document's "
            f"registration/application date of {doc_date}."
        ),
        documents=[doc.filename],
        evidence={
            "survey_number": f.survey_number,
            "transfer_date": latest["date"],
            "transfer_owner": latest["owner"],
            "document_date": doc_date,
            "days_before_document": days,
        },
    )


def run(docs: list[DocumentReport], adapter: RegistryAdapter | None = None) -> list[Anomaly]:
    adapter = adapter or MockRegistryAdapter()
    anomalies: list[Anomaly] = []

    for doc in docs:
        f = doc.fields

        if f.pan:
            if not _PAN_STRUCTURE.match(f.pan) or f.pan[3] not in _PAN_HOLDER_TYPES:
                anomalies.append(Anomaly(
                    code="PAN_STRUCTURE_INVALID",
                    layer="registry",
                    severity=Severity.CRITICAL,
                    title="PAN fails structural validation",
                    detail=f"'{f.pan}' on {doc.filename} does not conform to the "
                           "Income Tax Department PAN format.",
                    documents=[doc.filename],
                    evidence={"pan": f.pan},
                ))

        if f.cin:
            try:
                record = adapter.lookup_cin(f.cin)
            except RegistryTimeoutError:
                anomalies.append(_lookup_unavailable(doc.filename, "cin", f.cin))
            else:
                if record is None:
                    anomalies.append(Anomaly(
                        code="CIN_NOT_FOUND",
                        layer="registry",
                        severity=Severity.HIGH,
                        title="CIN not found in company registry",
                        detail=f"CIN {f.cin} on {doc.filename} has no match in the ROC registry.",
                        documents=[doc.filename],
                        evidence={"cin": f.cin},
                    ))
                elif record.get("status", "").lower() != "active":
                    anomalies.append(Anomaly(
                        code="CIN_INACTIVE",
                        layer="registry",
                        severity=Severity.HIGH,
                        title="Employer company is not active",
                        detail=f"CIN {f.cin} ({record.get('name')}) has ROC status "
                               f"'{record.get('status')}'.",
                        documents=[doc.filename],
                        evidence={"cin": f.cin, "record": record},
                    ))

        if doc.doc_type == DocType.LAND_RECORD and f.survey_number:
            try:
                record = adapter.lookup_land(f.survey_number)
            except RegistryTimeoutError:
                anomalies.append(_lookup_unavailable(doc.filename, "land", f.survey_number))
            else:
                if record is None:
                    anomalies.append(Anomaly(
                        code="SURVEY_NOT_FOUND",
                        layer="registry",
                        severity=Severity.HIGH,
                        title="Survey number absent from land registry",
                        detail=f"Survey number {f.survey_number} on {doc.filename} has no "
                               "entry in the state land-record registry.",
                        documents=[doc.filename],
                        evidence={"survey_number": f.survey_number},
                    ))
                else:
                    owner = record.get("owner", "")
                    claimed = f.applicant_name or ""
                    if claimed and owner and owner.lower().strip() != claimed.lower().strip():
                        anomalies.append(Anomaly(
                            code="OWNERSHIP_CONFLICT",
                            layer="registry",
                            severity=Severity.CRITICAL,
                            title="Registry owner differs from document owner",
                            detail=(
                                f"Land registry lists survey no. {f.survey_number} under "
                                f"'{owner}', but {doc.filename} names '{claimed}'."
                            ),
                            documents=[doc.filename],
                            evidence={"registry_owner": owner, "document_owner": claimed},
                        ))
                    reg_date = record.get("last_transfer_date")
                    doc_reg = f.registration_date
                    if reg_date and doc_reg and reg_date != doc_reg:
                        anomalies.append(Anomaly(
                            code="REGISTRATION_DATE_CONFLICT",
                            layer="registry",
                            severity=Severity.HIGH,
                            title="Registration date conflicts with registry",
                            detail=(
                                f"Document claims registration on {doc_reg} but the registry "
                                f"records the last transfer of survey no. {f.survey_number} "
                                f"on {reg_date}."
                            ),
                            documents=[doc.filename],
                            evidence={"document_date": doc_reg, "registry_date": reg_date},
                        ))
                    recency_anomaly = _recent_ownership_change(doc, f, record)
                    if recency_anomaly:
                        anomalies.append(recency_anomaly)

    return anomalies
