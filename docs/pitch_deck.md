# DocVerify — Pitch Deck
*Real-time AI fraud detection for loan document verification*

---

## Slide 1 — The Problem & Our Architecture

### The Problem
Bank underwriters manually verify land records, property deeds, salary slips, and financial statements for every loan application. Three failure points cost banks crores every year:
- **Invisible tampering** — edited PDF metadata, altered fonts, copy-pasted seals, overwritten numbers, with no visual tell.
- **No cross-document sanity checking** — a salary slip claims ₹80,000, the bank statement shows ₹40,000, and nothing flags it.
- **Delayed detection** — fraud surfaces after disbursement, when it's a legal and financial write-off, not a declined application.

### Our Architecture — A Security-First Microservice Pipeline

```
┌────────────┐      ┌──────────────┐      ┌────────────────────┐      ┌─────────────────────┐
│  Frontend  │ ───▶ │   Backend    │ ───▶ │   Security Gateway  │ ───▶ │   Model / Detection │
│ React 19 + │      │  FastAPI     │      │   (Layer 0)         │      │   Service (L1–L5)    │
│ TanStack   │      │  orchestrator│      │  malware reject +   │      │  OCR → forensics →   │
│ Start      │ ◀─── │  + L7 audit  │ ◀─── │  CDR flatten        │ ◀─── │  cross-check →       │
└────────────┘      └──────┬───────┘      └──────────────────────┘     │  registry → scoring  │
                            │                                           └─────────────────────┘
                            ▼
                     ┌─────────────┐
                     │  PostgreSQL │  (case results, JSONB + hash-chained audit ledger)
                     └─────────────┘
```

Each service runs in its **own Docker container with its own isolated build context** — the security gateway never shares a process with the code that renders untrusted PDFs, and the detection engine never touches a raw uploaded file, only sanitized artifacts.

### Technology Stack
| Layer | Tech |
|---|---|
| Frontend | React 19, TanStack Start + Router + Query, Tailwind v4, Radix UI, Zod |
| Backend orchestrator | FastAPI, psycopg3 |
| Security gateway | FastAPI, PyMuPDF, pdf2image (Poppler), Pillow |
| Detection engine | FastAPI, Tesseract OCR, NumPy, (Ollama LLM for narrative summaries) |
| Persistence | PostgreSQL 16 (JSONB case results) |
| Deployment | Docker Compose — 5 independently-scalable containers (frontend, backend, security, model, db) |

### Deployment & Scalability
- Stateless services behind Docker Compose today; each container can be **independently scaled or swapped** (e.g., the OCR/model service is the natural horizontal-scale point under load, since it's the CPU/GPU-heavy hop).
- Clean service boundary means the detection engine can later be swapped for a GPU-backed inference cluster without touching the security gateway or frontend.
- Postgres persistence is already wired for multi-instance deployments; the only current single-instance constraint is an in-memory per-case document buffer between "upload" and "analyze" — a natural next step is backing it with object storage/Redis for horizontal backend scaling.

---

## Slide 2 — How It Works: The Layered Detection Pipeline

**Every document is analyzed within seconds through 7 progressive layers before the underwriter ever sees a case:**

1. **Layer 0 — Security Sandbox (our addition, beyond the brief).** Every uploaded PDF is statically scanned for embedded JavaScript, launch actions, and auto-actions before anything else touches it, then **Content-Disarm-and-Reconstructed**: rasterized page-by-page into flat images. A malicious file is rejected outright — the detection engine never executes attacker-controlled content.
2. **Layer 1 — Ingestion & OCR.** Native PDF text extraction where available, Tesseract OCR fallback for scans/photos, automatic document-type classification (salary slip, bank statement, land record, ID proof...), and structured field extraction (income, PAN, CIN, survey number, dates) with per-field confidence scoring.
3. **Layer 2 — Tamper & Forgery Detection.** Metadata forensics (12+ editing-tool signatures, modified-vs-created timestamp gaps, incremental-save tampering), font-outlier detection, and Error Level Analysis to surface compressed/edited image regions invisible to the eye.
4. **Layer 3 — Cross-Document Anomaly Detection (our core differentiator).** Most systems check one document in isolation. We connect them: salary slip vs. bank statement income mismatch, land ownership timeline vs. application date, identity/name/address consistency across every document in the case.
5. **Layer 4 — External Registry Correlation.** PAN structural validation, CIN status, and land-record cross-checks against registry data — architected as a pluggable adapter so it drops into a bank's real CERSAI/ROC/land-record APIs with no pipeline changes.
6. **Layer 5 — Underwriting Insights.** A deterministic, explainable severity-weighted scoring model turns raw anomalies into a 0–100 Fraud Risk Score and a risk band (LOW/MEDIUM/HIGH/CRITICAL), plus concrete recommended actions ("Signature mismatch — recommend video KYC").
7. **Layer 7 — Tamper-Evident Audit Trail.** Every analysis is recorded in a SHA-256 hash-chained ledger — each entry embeds the previous entry's hash, so any retroactive edit to the audit log is cryptographically detectable. Built to anchor on-chain.

### User Experience Walkthrough
`Login → Dashboard (case queue, risk-sorted) → New Case (applicant + loan intake) → Document Upload (land / legal / financial, 3 categorized panels) → Live Analysis → Report (fraud score, per-document findings, cross-document conflicts) → Underwriting Decision → Audit Trail`

The officer never manually inspects a PDF pixel-by-pixel — they get a scored, explained, evidence-linked case in the time it takes to make coffee.

### Real-World Relevance
This mirrors exactly how a bank's loan-processing desk already works — intake, document collection, verification, decision, audit — so it drops into an existing workflow rather than requiring officers to learn a new mental model. The registry layer is deliberately architected against a stable interface so a bank's existing CERSAI/ROC/state land-record integrations plug in without touching detection logic.

---

## Slide 3 — What Makes This Different

- **Security-first, not an afterthought.** We built a dedicated Content-Disarm-and-Reconstruction gateway *before* building the fraud detector — untrusted files are neutralized structurally, not just scanned. Most hackathon (and many production) fraud tools skip this and run detection directly on attacker-controlled bytes.
- **Cross-document intelligence, not single-file scoring.** The unique value isn't "is this one PDF edited" — it's "does this applicant's story hold together across every document they submitted." That's the fraud pattern real underwriters actually chase and the hardest one to fake consistently.
- **Explainable, not a black box.** Every fraud score decomposes into named, severity-weighted anomaly codes with plain-language recommendations — an underwriter can defend a decision to a regulator or a customer, unlike an opaque ML confidence number.
- **Tamper-evident by design.** The audit ledger is hash-chained at the application layer today and architected to anchor to a smart contract — so the fraud *finding itself* can't be quietly altered after the fact, closing the loop on the exact trust problem the product solves for the bank's own documents.
- **Graceful degradation everywhere.** No LLM server available? Narrative insights degrade to "unavailable" without breaking the score. No registry data for a given CIN? It's flagged as unverified, not silently ignored. The system fails safe, never silently wrong.

---

## Slide 4 — USP, Continued: Security & Integration Strengths

- **Defense in depth:** malicious-content rejection → CDR flattening → isolated microservice boundaries — an attacker who compromises the OCR/detection service still never had access to a live, executable PDF.
- **Boundary discipline:** the security gateway and detection engine run from **separate Docker build contexts** with no shared code path — a deliberate architectural choice so a vulnerability in one service can't reach into the other's dependency surface.
- **Integration-ready by contract, not by rewrite:** the registry correlation layer (Layer 4) is built behind a pluggable adapter interface specifically so a bank's real CERSAI/ROC/land-record systems can be swapped in without touching the detection pipeline — we designed for the bank's real APIs from day one, not just our own mock data.
- **Performance:** the pipeline runs OCR, forensics, and cross-checks over an entire multi-document case and returns a fully explained, scored verdict inline — turning a manual review that takes an underwriter minutes-to-hours per document into a single automated pass.

## Slide 5 — Relevance & Roadmap

**Relevance to the hackathon theme:** directly targets a named, quantified pain point in bank loan operations — document fraud losses, underwriter time, and customer delay — with a working, demoable pipeline, not a slide-only concept.

**Roadmap (explicitly scoped, not hand-waved):**
- **Phase 2 — Reusable Verification:** once a customer's PAN/Aadhaar/bank statement pass verification, issue a **verifiable credential to a user-controlled wallet** — future loan applications skip re-running OCR and tamper detection entirely, cutting verification from 90 seconds to milliseconds. Aligned with India's DEPA and upcoming DID frameworks.
- On-chain anchoring of the audit hash-chain (contract scaffolding already in progress).
- Deeper forensic detectors: dedicated copy-move/seal-duplication detection, OCR preprocessing (deskew/denoise) for low-quality scans, table-aware statement parsing.

---

## Live Demo Script (4 minutes)

1. **(30s) Dashboard** — show the case queue, risk-sorted, color-coded.
2. **(30s) New Case** — create a case with applicant/loan intake details.
3. **(60s) Upload** — upload a clean document set into the three category panels; upload one deliberately malicious/malformed PDF to show Layer 0 rejecting it live.
4. **(90s) Analysis → Report** — trigger analysis on a tampered document bundle (edited metadata + income mismatch planted), show the live fraud score, the anomaly breakdown by layer, and the cross-document conflict (salary slip vs. bank statement).
5. **(30s) Decision & Audit** — record an underwriting decision, then show the audit trail entry and its hash-chain linkage to the previous entry.

## Anticipated Q&A Prep (2 minutes)

- **"How do you handle a false positive?"** — Every anomaly is explainable and severity-weighted, not a binary reject; the underwriter always makes the final call, and the tool's job is to surface evidence, not auto-decline.
- **"What if OCR misreads a document?"** — Every extracted field carries a confidence/provenance tag; low-confidence extractions are flagged for manual review rather than silently trusted.
- **"Is this production-ready for a real bank?"** — The security/CDR boundary and audit hash-chain are built to production discipline; the registry integrations are mocked behind a real adapter interface pending a bank's actual CERSAI/ROC data-sharing agreement — that's an integration/legal step, not a rebuild.
- **"Why microservices instead of a monolith?"** — Isolation: the highest-risk code (parsing untrusted PDFs) is quarantined in its own container with its own minimal dependency surface, separate from the detection logic and the customer-facing app.
