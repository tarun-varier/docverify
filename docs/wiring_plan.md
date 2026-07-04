# DocVerify — Wiring Plan (making the in-tree pipeline real)

**Companion to `implementation_audit.md`.** The detection code exists at `backend/app/` (audit §1) but is unwired. This is the target design + an incremental path to turn it on **without breaking the L0 security guarantee**, and without CDR destroying L2 forensics (audit §5, and the CDR-vs-forensics discussion).

---

## Core principle

> **Only the hardened security service ever touches original (possibly hostile) PDF bytes.** Everything downstream works on *safe artifacts only* (flattened PNGs + extracted text + forensic findings).

This resolves the CDR-vs-forensics tension: forensics that need the PDF structure (metadata, fonts, `%%EOF`, native text layer) run **inside security, on the original, before flattening**. Everything that works on safe pixels/text runs downstream.

---

## Target architecture

```
frontend
  │  POST /cases (files)
  ▼
backend  ── orchestrator + persistence + audit (L7) ──
  │  per file: POST /scan (original bytes)
  ▼
security  ══ THE ONLY BOX THAT TOUCHES ORIGINAL BYTES ══
  │  1. static-analysis reject  (JS / OpenAction / Launch / AA)      [EXISTS]
  │  2. PDF-native extraction on the original:
  │       • native text layer, per page        (L1a — exact, no OCR noise)
  │       • metadata forensics                  (L2 — software/backdate/modified/EOF)
  │       • font-outlier findings               (L2 — needs the text-layer spans)
  │  3. CDR: flatten every page → safe PNG       [EXISTS]
  │  → returns EvidenceBundle { sha256, native_text[], pdf_anomalies[], page_pngs_b64[] }
  ▼
backend collects bundles → POST /analyze (bundles)
  ▼
model  ══ never sees the original PDF; safe artifacts only ══
  │  per doc:  OCR the PNGs *iff* native_text is thin   (L1b fallback)
  │            field extraction on text                 (L1c)
  │            classify                                  (L1)
  │            ELA on the PNGs                           (L2 — image-only, correct home)
  │            merge in security's pdf_anomalies
  │  bundle:   cross_check (L3) · registry (L4) · insights+llm (L5)
  │  → returns CaseResult
  ▼
backend  persists CaseResult (Postgres) + records audit hash-chain (L7) + returns to frontend
```

---

## Detector placement (who runs what, and why)

| Detector / step | Layer | Needs | Home |
|---|---|---|---|
| static-analysis reject | L0 | original bytes | **security** (exists) |
| native text extraction | L1a | PDF text layer | **security** (NEW) |
| metadata forensics | L2 | PDF structure | **security** (NEW) |
| font-outlier | L2 | PDF text spans | **security** (NEW) |
| CDR flatten → PNG | L0 | original bytes | **security** (exists) |
| OCR fallback | L1b | PNG images | **model** |
| field extraction | L1c | text | **model** |
| classification | L1 | text | **model** |
| ELA | L2 | PNG images | **model** |
| cross-document checks | L3 | extracted fields | **model** |
| registry correlation | L4 | fields + registry JSON | **model** |
| scoring + recommendations | L5 | anomaly list | **model** |
| LLM narrative (optional) | L5 | anomalies + ollama | **model** (graceful-off) |
| audit hash-chain | L7 | final result | **backend** (near persistence, durable) |

Notes: native text beats OCR when a text layer exists (exact vs noisy) and it's free since security already holds the PDF; scanned PDFs have no text layer, so the model still needs the OCR fallback. Font-outlier is only meaningful for text-layer PDFs; scanned/image docs are covered by ELA instead. L7 moves to backend so the ledger lives with Postgres, not in the ephemeral model container.

---

## What this means for the existing code

- `forensics.analyze_pdf_metadata` + `analyze_fonts` → **move to security**.
- `ingestion.extract_text`'s PDF-text branch → **move to security**; its OCR branch → **stays in model**.
- `forensics.error_level_analysis`, `ingestion.extract_fields`, `classify`, `cross_check`, `registry`, `insights`, `llm` → **model**.
- `audit` → **backend**.
- `pipeline.analyze_case` gets split across the security↔model boundary (its per-document phase is the part that straddles it).
- Contracts (`EvidenceBundle`, analyze request/response) should be expressed with the fetched **`schema/` canonical models** (audit §2), with an adapter to/from the pipeline's `backend/app/models.py` (they diverge — audit §6).

---

## Incremental path (do these one at a time, verify each)

> **Progress:** Step 0 ✅, Step 1 ✅ (committed `6f56da3`), Step 3 ✅ (uncommitted — see note below). Next: **Step 4**.
>
> **Step 3 as-built (deviation from the sketch below):** the `EvidenceBundle` was defined as a **service-local HTTP wire contract** (`security/evidence.py`), *not* on the canonical `schema/` package. The three services build from **isolated Docker contexts** (`./security`, `./model`, `.`), so none can import a root-level `schema/` without restructuring build contexts — a cross-cutting change that is not a prerequisite for moving forensics. Full `schema/` adoption is therefore deferred to its own step. `pdf_anomalies` travel as plain dicts in `backend/pipeline/models.py::Anomaly` shape so `model` can rehydrate them. The **backdating** sub-check (needs Layer-1 fields) was deferred to Step 4; `security` carries the raw `pdf_metadata` in the bundle so `model` can reconstruct it. Forensics were **copied** (not moved) into `security/forensics.py`; the monolith's `backend/pipeline/forensics.py` copy stays until Step 4 retires it.

**Step 0 — Unblock the name collision.** `backend/app.py` (proxy) vs `backend/app/` (package) makes `uvicorn app:app` load the wrong thing (audit §1). Rename the pipeline package (e.g. `backend/app/` → `backend/pipeline/`) or relocate it to the `model` service where most of it will live. Prerequisite for everything. *Verify:* backend imports unambiguously.

**Step 1 — Prove the pipeline runs in isolation.** Add its deps (pymupdf, pytesseract, numpy, pillow, reportlab; system `tesseract`), restore `data/registries/*.json` from history (`git show 81e2b26:temp/data/registries/…`), guard/remove the missing `static/` mount, run `analyze_case()` on a sample PDF locally with the LLM gracefully off. *Verify:* a real CaseResult with real anomalies from a crafted tampered PDF. **This validates the detection substance before any topology surgery — the safe first win.**

**Step 2 — Define the contracts.** `EvidenceBundle` + analyze request/response on top of `schema/`; write the `models.py` ↔ `schema/models.py` adapter.

**Step 3 — Move PDF-native work into security.** metadata + fonts + native text; security returns the `EvidenceBundle`. *Verify:* security still rejects malicious PDFs AND now emits forensic findings on a tampered-but-safe PDF.

**Step 4 — Make the model service the analyzer.** Port ELA + OCR + field extraction + classify + cross_check + registry + insights into model; consume the bundle; return `CaseResult`.

**Step 5 — Frontend + persistence + real audit.** Point the UI at the real path, replace the fake `/analyzing` timed animation with real progress, persist to Postgres, record the L7 hash-chain in backend.

**Recommended start:** Step 0 then Step 1 — both are prerequisites, low-risk, and prove the detection works before we touch service boundaries.
