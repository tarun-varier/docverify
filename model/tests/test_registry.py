"""Layer 4 — registry adapter behavior.

Covers both the RegistryAdapter abstraction (via lightweight fake adapters
that isolate run()'s logic from fixture content) and the real
MockRegistryAdapter against the actual fixture JSON (catches fixture-authoring
mistakes the fakes can't see).

Run:  PYTHONPATH=model python -m pytest model/tests/test_registry.py -q
"""

from __future__ import annotations

import time

import pytest

from pipeline import registry
from pipeline.models import DocType, DocumentReport, ExtractedFields


def _doc(doc_type: DocType, **fields) -> DocumentReport:
    return DocumentReport(
        filename="doc.pdf",
        sha256="0" * 64,
        doc_type=doc_type,
        fields=ExtractedFields(**fields),
    )


class _FakeAdapter:
    """Minimal hand-written adapter for tests that don't need real fixtures."""

    def __init__(self, cin_records: dict | None = None, land_records: dict | None = None,
                 raise_on_cin: bool = False, raise_on_land: bool = False):
        self._cin = cin_records or {}
        self._land = land_records or {}
        self._raise_on_cin = raise_on_cin
        self._raise_on_land = raise_on_land

    def lookup_cin(self, cin: str) -> dict | None:
        if self._raise_on_cin:
            raise registry.RegistryTimeoutError("boom")
        return self._cin.get(cin)

    def lookup_land(self, survey_number: str) -> dict | None:
        if self._raise_on_land:
            raise registry.RegistryTimeoutError("boom")
        return self._land.get(survey_number)


# ---------------------------------------------------------------------------
# CIN checks (fake adapter — isolates run()'s logic from fixture content)
# ---------------------------------------------------------------------------

def test_cin_active_no_anomaly():
    adapter = _FakeAdapter(cin_records={"CIN1": {"name": "Acme", "status": "Active"}})
    doc = _doc(DocType.UNKNOWN, cin="CIN1")
    anomalies = registry.run([doc], adapter=adapter)
    assert not any(a.code in ("CIN_NOT_FOUND", "CIN_INACTIVE") for a in anomalies)


def test_cin_not_found():
    adapter = _FakeAdapter(cin_records={})
    doc = _doc(DocType.UNKNOWN, cin="CIN_MISSING")
    anomalies = registry.run([doc], adapter=adapter)
    codes = [a.code for a in anomalies]
    assert "CIN_NOT_FOUND" in codes


# ---------------------------------------------------------------------------
# CIN checks against the real fixtures (proves the new "Dissolved" entry
# and the pre-existing "Struck Off" entry both still resolve correctly)
# ---------------------------------------------------------------------------

def test_cin_dissolved_real_fixture():
    doc = _doc(DocType.UNKNOWN, cin="U29253KA2018PTC112233")
    anomalies = registry.run([doc])  # no adapter -> default MockRegistryAdapter()
    codes = [a.code for a in anomalies]
    assert "CIN_INACTIVE" in codes


def test_cin_struck_off_real_fixture_regression():
    doc = _doc(DocType.UNKNOWN, cin="U74999MH2012PTC234567")
    anomalies = registry.run([doc])
    codes = [a.code for a in anomalies]
    assert "CIN_INACTIVE" in codes


# ---------------------------------------------------------------------------
# Land checks (fake adapter)
# ---------------------------------------------------------------------------

def test_survey_not_found():
    adapter = _FakeAdapter(land_records={})
    doc = _doc(DocType.LAND_RECORD, survey_number="999/9")
    anomalies = registry.run([doc], adapter=adapter)
    assert any(a.code == "SURVEY_NOT_FOUND" for a in anomalies)


def test_ownership_conflict_regression():
    adapter = _FakeAdapter(land_records={
        "1/1": {"owner": "Registry Owner", "last_transfer_date": "2020-01-01"},
    })
    doc = _doc(DocType.LAND_RECORD, survey_number="1/1", applicant_name="Someone Else")
    anomalies = registry.run([doc], adapter=adapter)
    assert any(a.code == "OWNERSHIP_CONFLICT" for a in anomalies)


def test_registration_date_conflict_regression():
    adapter = _FakeAdapter(land_records={
        "1/1": {"owner": "Same Name", "last_transfer_date": "2020-01-01"},
    })
    doc = _doc(DocType.LAND_RECORD, survey_number="1/1", applicant_name="Same Name",
               registration_date="2021-06-15")
    anomalies = registry.run([doc], adapter=adapter)
    assert any(a.code == "REGISTRATION_DATE_CONFLICT" for a in anomalies)


# ---------------------------------------------------------------------------
# New: recency check (fake adapter, exact control over history/dates)
# ---------------------------------------------------------------------------

def test_recent_ownership_change_fires_within_window():
    adapter = _FakeAdapter(land_records={
        "1/1": {
            "owner": "placeholder", "last_transfer_date": "placeholder",
            "ownership_history": [
                {"owner": "Old Owner", "date": "2020-01-01"},
                {"owner": "New Owner", "date": "2024-01-01"},
            ],
        },
    })
    doc = _doc(DocType.LAND_RECORD, survey_number="1/1", applicant_name="New Owner",
               registration_date="2024-01-20")  # 19 days after the transfer
    anomalies = registry.run([doc], adapter=adapter)
    hits = [a for a in anomalies if a.code == "REGISTRY_RECENT_OWNERSHIP_CHANGE"]
    assert len(hits) == 1
    assert hits[0].evidence["days_before_document"] == 19
    assert hits[0].severity.value == "medium"


def test_recent_ownership_change_does_not_fire_outside_window():
    adapter = _FakeAdapter(land_records={
        "1/1": {
            "owner": "placeholder", "last_transfer_date": "placeholder",
            "ownership_history": [{"owner": "Old Owner", "date": "2020-01-01"}],
        },
    })
    doc = _doc(DocType.LAND_RECORD, survey_number="1/1", applicant_name="Old Owner",
               registration_date="2024-01-20")  # years later
    anomalies = registry.run([doc], adapter=adapter)
    assert not any(a.code == "REGISTRY_RECENT_OWNERSHIP_CHANGE" for a in anomalies)


def test_recent_ownership_change_excludes_future_history_entries():
    """A history entry AFTER the document's claimed date must not count as
    'recent before this application' -- it's registry data the document
    predates, not evidence of a suspicious flip before it."""
    adapter = _FakeAdapter(land_records={
        "1/1": {
            "owner": "placeholder", "last_transfer_date": "placeholder",
            "ownership_history": [
                {"owner": "Old Owner", "date": "2010-01-01"},
                {"owner": "Future Owner", "date": "2024-02-01"},  # after doc date below
            ],
        },
    })
    doc = _doc(DocType.LAND_RECORD, survey_number="1/1", applicant_name="Old Owner",
               registration_date="2024-01-20")
    anomalies = registry.run([doc], adapter=adapter)
    assert not any(a.code == "REGISTRY_RECENT_OWNERSHIP_CHANGE" for a in anomalies)


def test_recent_ownership_change_real_fixture():
    """Exercises the real '301/7' fixture record added for this purpose."""
    doc = _doc(DocType.LAND_RECORD, survey_number="301/7", applicant_name="Suresh Gowda",
               registration_date="2026-06-01")  # 12 days after the 2026-05-20 transfer
    anomalies = registry.run([doc])
    assert any(a.code == "REGISTRY_RECENT_OWNERSHIP_CHANGE" for a in anomalies)


# ---------------------------------------------------------------------------
# Graceful degrade: timeout -> REGISTRY_LOOKUP_UNAVAILABLE, not a false
# CIN_NOT_FOUND / SURVEY_NOT_FOUND
# ---------------------------------------------------------------------------

def test_cin_timeout_degrades_without_false_not_found():
    adapter = _FakeAdapter(raise_on_cin=True)
    doc = _doc(DocType.UNKNOWN, cin="CIN1")
    anomalies = registry.run([doc], adapter=adapter)
    codes = [a.code for a in anomalies]
    assert "REGISTRY_LOOKUP_UNAVAILABLE" in codes
    assert "CIN_NOT_FOUND" not in codes


def test_land_timeout_degrades_without_false_not_found():
    adapter = _FakeAdapter(raise_on_land=True)
    doc = _doc(DocType.LAND_RECORD, survey_number="1/1")
    anomalies = registry.run([doc], adapter=adapter)
    codes = [a.code for a in anomalies]
    assert "REGISTRY_LOOKUP_UNAVAILABLE" in codes
    assert "SURVEY_NOT_FOUND" not in codes


# ---------------------------------------------------------------------------
# Compatibility + suite-speed guards
# ---------------------------------------------------------------------------

def test_run_with_no_adapter_arg_works_against_real_fixtures():
    """analyze.py calls registry.run(documents) with no adapter kwarg."""
    doc = _doc(DocType.UNKNOWN, cin="U72200KA2015PTC081234")  # Active in the real fixture
    anomalies = registry.run([doc])
    assert not any(a.code in ("CIN_NOT_FOUND", "CIN_INACTIVE") for a in anomalies)


def test_default_mock_adapter_never_sleeps_or_raises():
    """Guards the test suite's speed against a future default flip to True."""
    adapter = registry.MockRegistryAdapter()
    t0 = time.monotonic()
    for _ in range(20):
        adapter.lookup_cin("anything")
        adapter.lookup_land("anything")
    assert time.monotonic() - t0 < 0.1
