# DocVerify — Pitch Deck Script
*Matches the 5-slide designed deck. Each slide's content is mapped against the required demo template — Slides 1&2 = Technology & Architecture, Slides 2-3-4 = Functionality/Capabilities, Slides 3-4-5 = USP — so it's clear which template bullet each block satisfies.*

> **Two fixes applied vs. the current designed slides** (flagged, not silently changed — confirm before regenerating the visuals):
> 1. **Branding mismatch**: Slide 1 header said "SURAKSHA HACKATHON 2026," Slide 5 footer said "Canara Bank Hackathon 2026." Standardized both to **"CANARA BANK SURAKSHA HACKATHON 2026"** — pick whichever is the actual event name and make both bookends match.
> 2. **Tech-stack accuracy** (Slide 2): LayoutLM, pikepdf, ExifTool, and Kubernetes aren't in the actual codebase (verified against `model/requirements.txt`, `security/requirements.txt`, and `docker-compose.yml` this session — it's Tesseract + PyMuPDF/pdf2image for OCR/forensics, plain Docker Compose, no K8s). Swapped to what's real so a technical judge's follow-up question doesn't expose a gap.

---

## Slide 1 — Title / Hook
*Template role: opens Slides 1&2's "Technology & Architecture" bucket via its block-flow diagram; everything else is the hook.*

- Logo: **DocVerify** (shield icon)
- Top-right: **CANARA BANK SURAKSHA HACKATHON 2026**
- Title: **DocVerify**
- Subtitle: **Real-Time Loan Document Fraud Intelligence**
- Body: *"AI anomaly detection across land, legal & financial documents — one explainable Fraud Risk Score in under 90 seconds."*
- 5-step flow strip (this **is** the architecture-overview diagram the template wants for Slide 1 — keep it, don't replace it):
  `Ingest & OCR (PDFs · scans · deeds) → Tamper Forensics (Metadata · ELA · visual) → Cross-Doc Check (Connect every doc) → Registry Match (CERSAI · ROC · Land) → Score & Advise (0–100 + next action)`
  - *Optional addition, one line under the strip:* "5-service microservice pipeline · sub-90-second SLA" — makes the architecture linkage explicit for a judge skimming past the icons.
- Bottom callout: *"Banks lose crores to tampering manual underwriting can't see. **DocVerify catches it before disbursement.**"*

---

## Slide 2 — Technology & Architecture (2/5)
*Template role: the core of the "Technology & Architecture" bucket (system diagram already shown Slide 1; here: technologies + deployment/scale). The 7-layer list also does double duty as "Core features or modules" for the Functionality bucket — no move needed, just worth naming when presenting.*

**Eyebrow:** TECHNOLOGY & ARCHITECTURE
**Title:** A 7-Layer Detection Engine

1. **Ingestion & OCR** — Text, seals, survey numbers & financial figures
2. **Tamper & Forgery** — Metadata forensics + ELA + font/seal checks
3. **Cross-Document Anomaly** — Income, ownership & identity conflicts
4. **External Correlation** — PAN · CIN · land-record validation
5. **Underwriting Insights** — Actionable, explainable recommendations
6. **Officer Dashboard** — Highlighted regions + confidence score
7. **Audit Trail** — Hash + timestamp, tamper-evident logs

**Tech Stack** *(corrected to match the real build)*:
- OCR / text extraction — **Tesseract**, native PDF text layer via **PyMuPDF**
- Vision / forensics — **PyMuPDF** (metadata, font-outlier), **Error Level Analysis** on scanned pages
- CDR / rasterization — **pdf2image (Poppler)**
- Backend/services — **FastAPI** across all 3 services
- Frontend — **React 19, TanStack Start**
- Persistence — **PostgreSQL** (JSONB case results) + hash-chained JSONL audit ledger

**Deploy & Scale** *(corrected)*:
- Containerized microservices — **Docker Compose**, one isolated build context per service (frontend / backend / security / model / db)
- Each service independently scalable — the OCR/detection service is the natural horizontal-scale point under load
- Deployment target: a bank's private VPC or cloud, container-by-container — no shared dependency surface between the security gateway and the detection engine

---

## Slide 3 — Functionality / Capabilities (3/5)
*Template role: core of the "Functionality" bucket (UX walkthrough). The "Explainable insights" card already bridges into the USP bucket (Slides 3-4-5) — this overlap is intentional, not a gap.*

**Eyebrow:** FUNCTIONALITY / CAPABILITIES
**Title:** What the Underwriter Sees

**Left — Officer Dashboard mockup:**
- Score: **78/100 — HIGH RISK**
- Findings: 🔴 Metadata edited pre-submit · 🟠 Signature mismatch vs ID · 🔴 Income ₹80k vs ₹40k · 🟢 PAN structure valid
- Action banner: **"Trigger Video KYC before approval"**

**Right — From upload to verdict, 90 seconds:**
`Upload (Any format) → Auto-analyze (7 layers) → Score (+ highlights) → Act (Next step)`

**Explainable insights, not just a number** *(this is the USP bridge — call it out explicitly when presenting)*:
- *"Metadata created 2 days before submission but claims registration year 2019 — possible backdating."*
- *"Land record ownership changed 15 days before application — high flip risk."*

---

## Slide 4 — Unique Selling Point (4/5)
*Template role: core of the "USP" bucket. Also satisfies Functionality's "real-world use case" bullet via the concrete income-mismatch example — another intentional overlap, no move needed.*

**Eyebrow:** UNIQUE SELLING POINT
**Title:** Documents That Talk to Each Other
**Subtitle:** *"Most tools inspect one document. DocVerify connects them — and the conflicts between documents are where fraud actually hides."*

**Flow:** Salary Slip + Bank Statement + ID/Land Deed → **Cross-Check Engine**

| Most tools | DocVerify |
|---|---|
| ❌ Check one document in isolation | ✅ Connects every document + registry |
| ❌ Visual-only, misses hidden edits | ✅ Forensic: metadata, ELA, seals |
| ❌ Fraud surfaces after disbursement | ✅ Caught before the money moves |

**Bottom chips:** 🔴 ₹80k slip vs ₹40k statement · 🔴 Owner ≠ registered name · 🟠 Name/address conflict

---

## Slide 5 — USP + Hackathon Relevance (Closing)
*Template role: closes the "USP" bucket — security/integration strengths, innovation/roadmap, and explicit hackathon-theme relevance all land here.*

**Eyebrow:** BUILT FOR CANARA BANK
**Title:** Secure · Integrated · Future-Ready

| Secure by Design | Native Integration | Roadmap · Phase 2 |
|---|---|---|
| Tamper-evident hash + timestamp logs | Plugs into CERSAI, ROC & land APIs | Reusable verifiable credentials |
| Hash-chained, blockchain-anchor-ready audit trail | Complements existing underwriting | 90 seconds → milliseconds |
| Deployable inside the bank's own VPC | No rip-and-replace deployment | Aligned with DEPA & DID frameworks |

**Closing banner:** *"90 seconds to trust. Zero blind spots."*
**Right-aligned benefits:** Fewer NPAs · Faster approvals for honest borrowers · Real-time fraud intelligence
**Footer:** DocVerify logo — **CANARA BANK SURAKSHA HACKATHON 2026** *(matches Slide 1 — see fix #1 above)*

---

## Live Demo Script (4 minutes)

1. **(30s) Dashboard** — case queue, risk-sorted, color-coded.
2. **(30s) New Case** — create a case with applicant/loan intake details.
3. **(60s) Upload** — upload a clean document set into the three category panels; upload one deliberately malformed PDF to show the Layer-0 security gateway rejecting it live.
4. **(90s) Analysis → Report** — run analysis on a tampered document bundle (edited metadata + planted income mismatch); show the live fraud score, the per-layer anomaly breakdown, and the cross-document conflict (salary slip vs. bank statement) — this is Slide 3 and Slide 4 coming alive.
5. **(30s) Decision & Audit** — record an underwriting decision, then show the audit trail entry and its hash-chain linkage to the previous entry.

## Anticipated Q&A Prep (2 minutes)

- **"How do you handle a false positive?"** — Every anomaly is explainable and severity-weighted, not a binary reject; the underwriter always makes the final call.
- **"What if OCR misreads a document?"** — Every extracted field carries a confidence/provenance tag; low-confidence extractions go to manual review rather than being silently trusted.
- **"Is this production-ready for a real bank?"** — The security/CDR boundary and audit hash-chain are built to production discipline; the registry integrations are mocked behind a real adapter interface pending a bank's actual CERSAI/ROC data-sharing agreement — an integration/legal step, not a rebuild.
- **"Why microservices instead of a monolith?"** — Isolation: the highest-risk code (parsing untrusted PDFs) is quarantined in its own container with its own minimal dependency surface, separate from the detection logic and the customer-facing app.
- **"What does LayoutLM/Kubernetes do in your stack?"** *(pre-empted by fix #2 above — don't claim these unless they're actually wired in before demo day.)*
