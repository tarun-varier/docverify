# DocVerify Real-Time

AI-powered real-time anomaly detection for loan documents. Analyzes a bundle of
land records, legal documents and financial statements and returns a **Fraud
Confidence Score (0–100)** with explainable, actionable insights — in seconds.

Built per [ideation_doc.md](ideation_doc.md).

## Quick start

```bash
uv sync                                  # create the venv and install deps
uv run python samples/generate_samples.py   # build demo document bundles
uv run uvicorn app.main:app --reload     # start the dashboard
```

Open <http://localhost:8000>, drop in everything from `samples/fraud/`
(or `samples/clean/`) and click **Analyze Bundle**.

OCR for scanned documents/photos uses the system `tesseract` binary if
installed; PDFs with a text layer need nothing extra.

## The layered detection pipeline

| Layer | Module | What it does |
|---|---|---|
| 1 Ingestion & OCR | `app/ingestion.py` | PDF/image text extraction (PyMuPDF + Tesseract), document classification, structured field extraction (names, PAN, CIN, survey numbers, incomes, dates) |
| 2 Tamper & forgery | `app/forensics.py` | Metadata forensics (editing software, modified-after-creation, backdating vs claimed dates, incremental saves), font-outlier detection, Error Level Analysis with heatmap + suspicious region boxes |
| 3 Cross-document | `app/cross_check.py` | Salary slip vs bank statement income, name/PAN/address consistency across the bundle, recent-ownership-flip detection |
| 4 Registry correlation | `app/registry.py` | PAN structural validation, CIN status, land survey-number ownership — against mock registries in `data/registries/`, with a thin interface ready to re-point at CERSAI / ROC / state land-record APIs |
| 5 Insights | `app/insights.py` | Fraud score (diminishing-returns severity sum), risk band, recommended underwriting actions per anomaly |
| 6 Dashboard | `static/` | Bank-officer UI: score gauge, anomaly cards by severity, extracted fields, ELA heatmaps |
| 7 Audit trail | `app/audit.py` | Hash-chained JSONL ledger (document SHA-256 + timestamp + result); `GET /api/audit/verify` re-walks the chain |

## API

- `POST /api/analyze` — multipart upload of up to 12 PDFs/images; returns the full case result as JSON.
- `GET /api/audit/verify` — verifies the tamper-evident ledger.

## Demo bundles

`samples/clean/` is a consistent applicant (scores ~0, LOW). `samples/fraud/`
trips every layer: salary inflated 2× vs the bank statement, employer CIN
struck off, a deed for someone else's survey number that claims a 2019
registration but was produced in Photoshop two days ago, an amount overwritten
in a mismatched font, and a deed photo with a pasted seal that lights up under
ELA (scores 100, CRITICAL).

## Tests

```bash
uv run pytest
```

## Roadmap (Phase 2)

Reusable verification: issue a verifiable credential after a successful
verification so later applications validate a cryptographic proof instead of
re-running the pipeline. Aligned with DEPA / DID frameworks.
