"""End-to-end and unit tests for the DocVerify pipeline."""

from datetime import datetime, timedelta, timezone

import pytest

import generate_samples as gen
from app import audit, cross_check, insights, pipeline, registry
from app.ingestion import classify, extract_fields, extract_text
from app.models import DocType, Severity


def _stamp(payload, **kw):
    defaults = dict(producer="Test Producer", creator="Test",
                    created=datetime.now(timezone.utc) - timedelta(days=30))
    defaults.update(kw)
    return gen._stamp_metadata(payload, **defaults)


@pytest.fixture(scope="module")
def clean_bundle():
    return [
        ("salary_slip.pdf", _stamp(gen.salary_slip(
            "Ramesh Kumar", "ABCPK1234F", "U72200KA2015PTC081234",
            "80,000.00", tampered_amount_font=False))),
        ("bank_statement.pdf", _stamp(gen.bank_statement(
            "Ramesh Kumar", "ABCPK1234F", "80,000.00"))),
        ("land_record.pdf", _stamp(gen.land_deed("Ramesh Kumar", "142/2A", "14-03-2019"),
                                   created=datetime(2019, 3, 20, tzinfo=timezone.utc))),
    ]


@pytest.fixture(scope="module")
def fraud_bundle():
    two_days = datetime.now(timezone.utc) - timedelta(days=2)
    return [
        ("salary_slip.pdf", _stamp(
            gen.salary_slip("Suresh Patel", "AAAPS9999K", "U74999MH2012PTC234567",
                            "80,000.00", tampered_amount_font=True),
            producer="Adobe Photoshop 25.0", creator="Adobe Photoshop", created=two_days)),
        ("bank_statement.pdf", _stamp(gen.bank_statement(
            "Suresh Patel", "AAAPS9999K", "40,000.00"))),
        ("land_deed.pdf", _stamp(
            gen.land_deed("Suresh Patel", "142/2A", "14-03-2019"),
            producer="Adobe Photoshop 25.0", creator="Adobe Photoshop", created=two_days)),
        ("deed_photo.jpg", gen.tampered_photo()),
    ]


def _codes(result):
    return {
        a.code
        for d in result.documents for a in d.anomalies
    } | {a.code for a in result.cross_document_anomalies + result.registry_anomalies}


# ---- Layer 1 -------------------------------------------------------------

def test_classification_and_fields(clean_bundle):
    text, pages, _ = extract_text(*clean_bundle[0])
    assert pages == 1
    assert classify(text) == DocType.SALARY_SLIP
    fields = extract_fields(text, DocType.SALARY_SLIP)
    assert fields.applicant_name == "Ramesh Kumar"
    assert fields.pan == "ABCPK1234F"
    assert fields.monthly_income == 80000.0


def test_bank_statement_credits(clean_bundle):
    text, _, _ = extract_text(*clean_bundle[1])
    assert classify(text) == DocType.BANK_STATEMENT
    fields = extract_fields(text, DocType.BANK_STATEMENT)
    assert fields.salary_credits == [80000.0] * 3


# ---- Full pipeline -------------------------------------------------------

def test_clean_bundle_scores_low(clean_bundle):
    result = pipeline.analyze_case(clean_bundle)
    assert result.fraud_score < 15
    assert result.risk_band == "LOW"
    assert _codes(result) == set()


def test_fraud_bundle_scores_critical(fraud_bundle):
    result = pipeline.analyze_case(fraud_bundle)
    assert result.fraud_score >= 70
    assert result.risk_band == "CRITICAL"
    codes = _codes(result)
    assert {"INCOME_MISMATCH", "OWNERSHIP_CONFLICT", "META_POSSIBLE_BACKDATING",
            "META_EDITING_SOFTWARE", "FONT_OUTLIER", "CIN_INACTIVE",
            "ELA_EDITED_REGIONS"} <= codes
    assert result.recommendations  # actionable insights present


def test_ela_finds_pasted_seal(fraud_bundle):
    result = pipeline.analyze_case([fraud_bundle[3]])
    photo = result.documents[0]
    assert photo.ela_image
    assert photo.suspicious_regions
    # The seal was pasted around (700, 480); a region must cover it.
    assert any(r["x"] <= 700 <= r["x"] + r["w"] and r["y"] <= 480 <= r["y"] + r["h"]
               for r in photo.suspicious_regions)


# ---- Layer 3/4 unit checks ------------------------------------------------

def test_name_mismatch_detected(clean_bundle, fraud_bundle):
    mixed = [clean_bundle[0], fraud_bundle[1]]  # Ramesh slip + Suresh statement
    result = pipeline.analyze_case(mixed)
    assert "NAME_MISMATCH" in _codes(result)
    assert "PAN_MISMATCH" in _codes(result)


def test_invalid_pan_structure():
    slip = _stamp(gen.salary_slip("Test User", "ABXQZ1234K", "U72200KA2015PTC081234",
                                  "50,000.00", tampered_amount_font=False))
    result = pipeline.analyze_case([("slip.pdf", slip)])
    # 4th char 'Q' is not a valid PAN holder-type code.
    assert "PAN_STRUCTURE_INVALID" in _codes(result)


# ---- Layer 5 --------------------------------------------------------------

def test_score_bands():
    assert insights.risk_band(0) == "LOW"
    assert insights.risk_band(20) == "MEDIUM"
    assert insights.risk_band(50) == "HIGH"
    assert insights.risk_band(85) == "CRITICAL"


# ---- Layer 7 --------------------------------------------------------------

def test_audit_chain_detects_tampering(tmp_path, monkeypatch):
    monkeypatch.setattr(audit, "LEDGER_PATH", tmp_path / "ledger.jsonl")
    audit.record("case1", {"a.pdf": "x" * 64}, 10, "LOW")
    audit.record("case2", {"b.pdf": "y" * 64}, 90, "CRITICAL")
    assert audit.verify_chain() == (True, 2)

    # Retroactively lower case2's score: the chain must break.
    lines = audit.LEDGER_PATH.read_text().splitlines()
    lines[1] = lines[1].replace('"fraud_score": 90', '"fraud_score": 5')
    audit.LEDGER_PATH.write_text("\n".join(lines) + "\n")
    intact, _ = audit.verify_chain()
    assert not intact


# ---- API ------------------------------------------------------------------

def test_api_analyze(fraud_bundle):
    from fastapi.testclient import TestClient
    from app.main import app

    client = TestClient(app)
    files = [("files", (name, payload, "application/octet-stream"))
             for name, payload in fraud_bundle]
    res = client.post("/api/analyze", files=files)
    assert res.status_code == 200
    body = res.json()
    assert body["risk_band"] == "CRITICAL"
    assert body["audit_entry"]["entry_hash"]

    res = client.get("/api/audit/verify")
    assert res.json()["intact"] is True


def test_api_rejects_bad_type():
    from fastapi.testclient import TestClient
    from app.main import app

    client = TestClient(app)
    res = client.post("/api/analyze", files=[("files", ("evil.exe", b"x", "application/octet-stream"))])
    assert res.status_code == 400
