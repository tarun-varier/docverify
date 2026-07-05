"""Layer-1 extraction: table/column-aware recall on realistic Indian loan docs.

These tests feed the *flat text* the model actually receives (PyMuPDF
``page.get_text()`` / OCR output — no coordinates) and assert that:

  * ``salary_credits`` is read from the **credit/deposit column**, not the
    running-balance column, a reference number, or a year embedded in the
    narration;
  * ``monthly_income`` is recovered even when classification misses
    ``SALARY_SLIP`` and is biased to **net/take-home** pay (what actually lands
    in the bank), improving the INCOME_MISMATCH comparison;
  * the flagship cross-document ``INCOME_MISMATCH`` fires on a genuinely
    tampered pair with correct figures, and stays silent on a matching pair;
  * the existing single-line ``label: value`` happy path still extracts.

Run:  PYTHONPATH=model python -m pytest model/tests/test_l1_tables.py -q
Only needs pydantic + pillow (semantic Pass 2 degrades gracefully when
sentence-transformers is absent).
"""

from __future__ import annotations

from datetime import date

import pytest

from pipeline import cross_check, ingestion
from pipeline.models import DocType, DocumentReport, ExtractedFields


# ---------------------------------------------------------------------------
# Sample layouts (as flat text, the way the model receives it)
# ---------------------------------------------------------------------------

# Debit/Credit/Balance columns; narration carries a YEAR and a REFERENCE
# NUMBER before the real credit amount — the loose "first number after
# 'salary'" regex grabs those instead of 40,200.
BANK_TAMPERED = """ACME BANK - STATEMENT OF ACCOUNT
Account Holder : Ravi Kumar
Date        Description                       Debit       Credit      Balance
01/04/2024  SALARY FOR 04/2024 REF 100200300  -           40,200.00   1,40,200.00
05/04/2024  ATM Withdrawal                    5,000.00    -           1,35,200.00
01/05/2024  SALARY FOR 05/2024 REF 100200412  -           40,200.00   1,75,400.00
03/05/2024  UPI Payment                       2,500.00    -           1,72,900.00
01/06/2024  SALARY FOR 06/2024 REF 100200533  -           40,200.00   2,13,100.00
"""

# Matching statement: net salary of 80,000 actually credited.
BANK_MATCHING = """HDFC BANK - ACCOUNT STATEMENT
Account Holder : Ravi Kumar
Txn Date    Narration                    Withdrawal    Deposit      Balance
01-04-2024  SALARY-ACME CORP-04/2024     0.00          80,000.00    1,80,000.00
09-04-2024  BILLPAY ELECTRICITY          2,300.00      0.00         1,77,700.00
01-05-2024  SALARY-ACME CORP-05/2024     0.00          80,000.00    2,57,700.00
01-06-2024  SALARY-ACME CORP-06/2024     0.00          80,000.00    3,37,700.00
"""

# Salary slip where net pay (40,200) < gross (80,000). The tampered applicant
# CLAIMS 80,000 (gross) but only 40,200 net actually lands in the bank.
SLIP_NET_40200 = """ACME CORP PVT LTD - SALARY SLIP - April 2024
Employee Name : Ravi Kumar
PAN : ABCDE1234F
Earnings                Amount
Basic Pay               50,000.00
HRA                     20,000.00
Special Allowance       10,000.00
Gross Salary            80,000.00
Deductions              Amount
Provident Fund          6,000.00
Professional Tax        200.00
Income Tax              33,600.00
Net Pay                 40,200.00
"""

# Honest slip: net pay 80,000, matches the matching statement.
SLIP_NET_80000 = """ACME CORP PVT LTD - SALARY SLIP - April 2024
Employee Name : Ravi Kumar
PAN : ABCDE1234F
Basic Pay               60,000.00
HRA                     25,000.00
Gross Salary            85,000.00
Provident Fund          5,000.00
Net Pay                 80,000.00
"""

# A classic single-line label:value document (the happy path we must not regress).
LABELVALUE_LAND = """SUB-REGISTRAR OFFICE - SALE DEED / LAND RECORD
Name of Owner: Ravi Kumar
Survey Number: 123/4B
Registration Date: 12/03/2024
Address: 14 MG Road, Bengaluru, Karnataka 560001
"""

# Balance printed BEFORE debit/credit (some banks do this) — regression guard
# for the bug where _pick_credit assumed the running balance is always the
# rightmost money column and blindly dropped the last token.
BANK_BALANCE_FIRST = """XYZ BANK - STATEMENT OF ACCOUNT
Account Holder : Ravi Kumar
Date        Description         Balance      Debit       Credit
01/04/2024  SALARY CREDIT       1,40,200.00  -           40,200.00
01/05/2024  SALARY CREDIT       1,80,400.00  -           40,200.00
"""

# A land record whose incidental note happens to be padded like a table and
# names all three column words — classify() confidently calls this
# LAND_RECORD (four strong keyword hits), so it must never leak a
# salary_credits value even though the note's "Salary advance adjustment" row
# would otherwise parse as a genuine credit.
LAND_RECORD_TABULAR_NOTE = """SUB-REGISTRAR OFFICE - SALE DEED / LAND RECORD
Name of Owner: Ravi Kumar
Survey Number: 123/4B
Registration Date: 12/03/2024
Encumbrance Note            Debit        Credit       Balance
Pending dues                500.00       -            500.00
Salary advance adjustment   -            20,000.00    20,500.00
"""


def _fields(text: str, filename: str = "") -> tuple[DocType, ExtractedFields]:
    dt = ingestion.classify(text, filename)
    return dt, ingestion.extract_fields(text, dt)


def _report(text: str, filename: str) -> DocumentReport:
    dt, f = _fields(text, filename)
    return DocumentReport(filename=filename, sha256="0" * 64, doc_type=dt, fields=f)


# ---------------------------------------------------------------------------
# salary_credits — must pick the credit column, not balance/year/ref
# ---------------------------------------------------------------------------

def test_salary_credits_reads_credit_column_not_balance_or_noise():
    _, f = _fields(BANK_TAMPERED, "bank_statement.pdf")
    assert f.salary_credits == [40200.0, 40200.0, 40200.0], f.salary_credits
    avg = sum(f.salary_credits) / len(f.salary_credits)
    assert avg == pytest.approx(40200.0)


def test_salary_credits_withdrawal_deposit_layout():
    _, f = _fields(BANK_MATCHING, "bank_statement.pdf")
    assert f.salary_credits == [80000.0, 80000.0, 80000.0], f.salary_credits


def test_salary_credits_ignores_zero_and_debit_amounts():
    # No 0.00 (withdrawal placeholder) or 2,300 (a debit) should leak in.
    _, f = _fields(BANK_MATCHING, "bank_statement.pdf")
    assert 0.0 not in f.salary_credits
    assert 2300.0 not in f.salary_credits


def test_salary_credits_balance_first_column_layout():
    _, f = _fields(BANK_BALANCE_FIRST, "bank_statement.pdf")
    assert f.salary_credits == [40200.0, 40200.0], f.salary_credits


def test_table_header_ignores_prose_mentioning_column_words():
    # Single-spaced prose naming all three column words (plus "salary credit")
    # must not be mistaken for a transaction-table header — it lacks the
    # columnar padding of a real header row.
    text = (
        "Please report any discrepancy in your debit/credit or balance "
        "within 30 days of any salary credit posting to your account.\n"
    )
    assert ingestion._extract_salary_credits(text) == []


def test_salary_credits_not_populated_on_non_financial_doc_type():
    dt, f = _fields(LAND_RECORD_TABULAR_NOTE, "land_record.pdf")
    assert dt == DocType.LAND_RECORD
    assert f.salary_credits == []


# ---------------------------------------------------------------------------
# monthly_income — un-gated from classification, biased to net/take-home
# ---------------------------------------------------------------------------

def test_monthly_income_prefers_net_pay_over_gross():
    _, f = _fields(SLIP_NET_40200, "salary_slip.pdf")
    assert f.monthly_income == 40200.0, f.monthly_income


def test_monthly_income_survives_classification_miss():
    # Force the model to see text with no salary-slip keywords in the filename
    # and pretend classify missed — extract_fields must still find income when
    # the net-pay label is present, regardless of doc_type.
    f = ingestion.extract_fields(SLIP_NET_80000, DocType.UNKNOWN)
    assert f.monthly_income == 80000.0, f.monthly_income


# ---------------------------------------------------------------------------
# Cross-document INCOME_MISMATCH — fires on tamper, silent on match
# ---------------------------------------------------------------------------

def test_income_mismatch_fires_on_tampered_pair():
    slip = _report(SLIP_NET_40200, "slip.pdf")
    # Applicant CLAIMS 80,000 income; only 40,200 net lands in the bank.
    slip.fields.monthly_income = 80000.0  # claimed (as it would read off a doctored slip header)
    stmt = _report(BANK_TAMPERED, "stmt.pdf")
    anomalies = cross_check.run([slip, stmt], today=date(2024, 7, 1))
    codes = [a.code for a in anomalies]
    assert "INCOME_MISMATCH" in codes, codes
    a = next(x for x in anomalies if x.code == "INCOME_MISMATCH")
    assert a.evidence["claimed"] == 80000.0
    assert a.evidence["average_credit"] == pytest.approx(40200.0)


def test_no_income_mismatch_on_matching_pair():
    slip = _report(SLIP_NET_80000, "slip.pdf")
    stmt = _report(BANK_MATCHING, "stmt.pdf")
    anomalies = cross_check.run([slip, stmt], today=date(2024, 7, 1))
    assert "INCOME_MISMATCH" not in [a.code for a in anomalies]


# ---------------------------------------------------------------------------
# Regression — the single-line label:value happy path still extracts
# ---------------------------------------------------------------------------

def test_labelvalue_happy_path_unregressed():
    dt, f = _fields(LABELVALUE_LAND, "land_record.pdf")
    assert dt == DocType.LAND_RECORD
    assert f.applicant_name == "Ravi Kumar"
    assert f.survey_number == "123/4B"
    assert f.registration_date == "2024-03-12"
    assert f.address and "MG Road" in f.address


def test_labelvalue_slip_still_extracts_name_and_pan():
    _, f = _fields(SLIP_NET_40200, "salary_slip.pdf")
    assert f.applicant_name == "Ravi Kumar"
    assert f.pan == "ABCDE1234F"
