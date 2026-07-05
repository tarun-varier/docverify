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

> **Progress:** Step 0 ✅, Step 1 ✅ (`6f56da3`), Step 3 ✅ (`42e0475`), Step 4 ✅ (`abe47de`). **Step 5 ✅ (`0e1f0c1`, `1a3610c`)** — orchestration + L7 move + persistence + retiring the `/predict` hop are done and verified end-to-end; the frontend is wired + typechecks but not yet driven in a browser.
>
> **Step 5 as-built:** Orchestration moved into `backend/app.py` as case endpoints — `POST /cases/{id}/documents` (per file: security `/scan` → buffer the EvidenceBundle), `POST /cases/{id}/analyze` (model `/analyze` over the buffered bundles → CaseResult → L7 → persist), `GET /cases/{id}/result`. The per-case bundle buffer is **in-memory** (single-instance dev; a multi-replica backend would move it to Postgres/object store — the bundles carry base64 page PNGs). **L7 moved to `backend/audit.py`**; the model no longer records (its `pipeline/audit.py` was deleted and `CaseResult.audit_entry` is now optional — the backend injects it). **Postgres persistence** lives in `backend/db.py` (psycopg3, whole `CaseResult` as JSONB in `case_results`, **best-effort/graceful-degrade** so local non-DB runs still work); compose `backend` now `depends_on` db+model+security. **The `security → model /predict` hop is retired**: `security/scan` no longer calls the model (no more `ml_prediction` in the bundle), the model's `/predict` stub is deleted, and `ML_SERVICE_URL` / `security depends_on model` are gone from compose. **Postgres password** is now env-overridable (`${POSTGRES_PASSWORD:-docverify_pass}`) with `.env.example`; it's still a dev default — **rotate for any non-local use**. Vestigial `backend/pipeline/`, `backend/analyzer.py`, and `backend/data/registries/` were retired. **Frontend** is wired to the real path (`src/lib/api.ts`; upload → `/documents`, analyzing route now calls `/analyze` and drives the transition on the real result; `mock-data.ts::applyCaseResult` adapts a `CaseResult` onto the existing `Case`/`CaseDoc`/`Anomaly` UI shape so report/document/decision render real data with no rewrite). **Hygiene:** a stale runtime `audit_ledger.jsonl` was leaking into the model image via `COPY . .` — added to `model/.dockerignore` + root `.dockerignore` (`**/audit_ledger.jsonl`) and removed the host leftover. **Verified** via `/tmp/dockver-verify-step5.py` over the live backend HTTP path: malicious PDF → 403 on the live path; three tampered docs → **100/CRITICAL**, all three classified, cross-doc `INCOME_MISMATCH`, L7 recorded **in the backend** (2-entry hash-chain intact, model container writes none), Postgres rows present + `GET /result` reload matches.
>
> **Step 3 as-built (deviation from the sketch below):** the `EvidenceBundle` was defined as a **service-local HTTP wire contract** (`security/evidence.py`), *not* on the canonical `schema/` package. The three services build from **isolated Docker contexts** (`./security`, `./model`, `.`), so none can import a root-level `schema/` without restructuring build contexts — a cross-cutting change that is not a prerequisite for moving forensics. Full `schema/` adoption is therefore deferred to its own step. `pdf_anomalies` travel as plain dicts in `backend/pipeline/models.py::Anomaly` shape so `model` can rehydrate them. The **backdating** sub-check (needs Layer-1 fields) was deferred to Step 4; `security` carries the raw `pdf_metadata` in the bundle so `model` can reconstruct it. Forensics were **copied** (not moved) into `security/forensics.py`; the monolith's `backend/pipeline/forensics.py` copy stays until the backend is retired.
>
> **Step 4 as-built:** `model` now has `POST /analyze` (`model/pipeline/` + `analyze.py`) consuming a case of EvidenceBundles → real `CaseResult`. The detection pipeline was **copied** from `backend/pipeline/` into `model/pipeline/` (isolated contexts), pure modules verbatim; `ingestion` dropped the `fitz` PDF branch (OCRs the flattened PNGs when native text is thin), `forensics` kept ELA + gained `backdating_from_metadata`. **`EvidenceBundle` gained `filename`.** L7 audit **still lives in `model`** for now → moves to backend in Step 5. Legacy `model/app.py::/predict` stub is left in place (unused by the new path) until the backend is rewired. **ELA gate:** ELA runs only on pages whose native text is thin (scanned/photo) — on vector-text pages freshly rasterized by CDR it false-positives on text edges (caught during verification). **`backend/pipeline/` is now vestigial** (its forensics → security, its analysis → model); retire it in Step 5. Verified via TestClient *and* a full security-container → model-container HTTP round-trip (100/CRITICAL, no ELA false positive).

**Step 0 — Unblock the name collision.** `backend/app.py` (proxy) vs `backend/app/` (package) makes `uvicorn app:app` load the wrong thing (audit §1). Rename the pipeline package (e.g. `backend/app/` → `backend/pipeline/`) or relocate it to the `model` service where most of it will live. Prerequisite for everything. *Verify:* backend imports unambiguously.

**Step 1 — Prove the pipeline runs in isolation.** Add its deps (pymupdf, pytesseract, numpy, pillow, reportlab; system `tesseract`), restore `data/registries/*.json` from history (`git show 81e2b26:temp/data/registries/…`), guard/remove the missing `static/` mount, run `analyze_case()` on a sample PDF locally with the LLM gracefully off. *Verify:* a real CaseResult with real anomalies from a crafted tampered PDF. **This validates the detection substance before any topology surgery — the safe first win.**

**Step 2 — Define the contracts.** `EvidenceBundle` + analyze request/response on top of `schema/`; write the `models.py` ↔ `schema/models.py` adapter.

**Step 3 — Move PDF-native work into security.** metadata + fonts + native text; security returns the `EvidenceBundle`. *Verify:* security still rejects malicious PDFs AND now emits forensic findings on a tampered-but-safe PDF.

**Step 4 — Make the model service the analyzer.** Port ELA + OCR + field extraction + classify + cross_check + registry + insights into model; consume the bundle; return `CaseResult`.

**Step 5 — Frontend + persistence + real audit.** ✅ (`0e1f0c1`, `1a3610c`) Point the UI at the real path, replace the fake `/analyzing` timed animation with real progress, persist to Postgres, record the L7 hash-chain in backend. *Done: backend orchestration, L7-in-backend, Postgres persistence, `/predict` hop retired, frontend wired + typechecked. Remaining: drive the frontend in a browser end-to-end; optionally a real progress stream (currently the analyzing route awaits one `/analyze` call with a cosmetic step animation).*

**Recommended start:** Step 0 then Step 1 — both are prerequisites, low-risk, and prove the detection works before we touch service boundaries.
