# DocVerify — Implementation Audit vs. Ideation Doc

**Date:** 2026-07-04
**Audited against:** `docs/ideation_doc.md`
**Scope:** Live code in `backend/`, `model/`, `security/`, `frontend/`, `ledger/` (+ scrapped prototype in git history under `temp/`)

---

## TL;DR

The ideation doc describes a **7-layer AI fraud-detection pipeline**. What is actually *running* today is a different, narrower thing:

- A genuinely solid **Layer 0 security/CDR gateway** (not in the ideation doc) that rejects malicious PDFs and flattens them to images.
- A **polished bank-officer dashboard** (Layer 6) — the most complete deliverable — but driven entirely by mock data in the browser's `localStorage`.
- **Stubs** where the actual fraud detection should be: the "ML model" returns a hardcoded `fraud_score: 0.03` for every document.

Critically, a **real ~1,800-line implementation of Layers 1–5 exists in git history** (`temp/app/`, commit `81e2b26`) but was **deleted** and replaced by the current microservice architecture, which does not carry that logic forward.

**Overall: the core promise (multi-layer fraud detection) is ~15–20% implemented in the live system.** The infrastructure, security wrapper, and UI are strong; the actual detection intelligence is not wired up.

---

## Architecture as-built

```
frontend (TanStack Start, :3000)
   │  POST /upload
   ▼
backend (FastAPI, :8000)          ← thin proxy only (app.py)
   │  POST /scan
   ▼
security "Layer 0" gateway (:8002) ← REAL: static analysis + CDR
   │  POST /predict
   ▼
model "ML" service (:8001)        ← STUB: returns hardcoded verdict
```

Plus: `db` (Postgres 16, provisioned in compose but **unused** — no service connects to it) and `ledger/` (Hardhat project, **untouched sample code**).

---

## Layer-by-layer assessment

| Layer (from ideation) | Status | Est. % | Where |
|---|---|---|---|
| **L0** Security sandbox / CDR *(bonus, not in doc)* | ✅ Real | 90% | `security/main.py` |
| **L1** Document Ingestion & OCR | 🟥 Stub | 10% | `model/app.py` |
| **L2** Tamper & Forgery (metadata, visual, ELA) | 🟥 Not live | 5% | — (stub verdict only) |
| **L3** Cross-Document Anomaly Detection | 🟧 Faked in UI | 10% | `frontend/.../mock-data.ts` |
| **L4** External Registry Correlation | 🟥 Hardcoded strings | 5% | `frontend/.../mock-data.ts` |
| **L5** Underwriting Insights | 🟧 Template strings | 15% | `frontend` (static) |
| **L6** Bank Officer Dashboard | ✅ Real UI, mock data | 75% | `frontend/src/routes/*` |
| **L7** Audit Trail (blockchain-ready) | 🟧 Mock table only | 15% | `frontend/.../audit.tsx`, `ledger/` |
| **Roadmap** Reusable verifiable credentials | ⬜ Not started | 0% | — (explicitly Phase 2) |

Legend: ✅ implemented · 🟧 partial/mocked · 🟥 stub/absent · ⬜ not started

---

### Layer 0 — Security Sandbox & CDR *(bonus — best-built component)* ✅ ~90%
**File:** `security/main.py`

- **Static analysis:** `_reject_if_malicious()` inspects the PDF catalog, pages, and annotations and rejects (`403`) on `/Names→/JavaScript`, `/OpenAction`, `/AA`, and `/JavaScript`/`/Launch` annotation actions. Handles encrypted/corrupt PDFs.
- **CDR (Content Disarm & Reconstruction):** `convert_from_bytes()` (poppler) rasterizes every page to a flat PNG — a legitimately strong way to neutralize active content. Memory is carefully managed (`gc.collect()`, image closing, `tmpfs` mount, `mem_limit`).
- This is real, defensible engineering — but it is a **safety wrapper**, not fraud detection. The ideation doc never asked for it; it's a good addition.

> **Dead code:** `security/scanner.py` and `security/converter.py` implement a richer, recursive threat scan and disk-streaming converter but are **never imported** by `main.py`. Likewise `backend/analyzer.py` (`PDFSandboxAnalyzer`, keyword threat-scoring) is **never imported** by `backend/app.py`. Three files of unused logic.

### Layer 1 — Document Ingestion & OCR 🟥 ~10%
**File:** `model/app.py`

- The "ML model service" opens each page image with PIL and returns **only its width/height/format**.
- The OCR "result" is a hardcoded string: `"DocVerify OCR verification completed for N rendered page(s)."` — **no OCR runs.**
- The fraud verdict is a constant: `is_fraudulent: False, fraud_score: 0.03, confidence: 0.97`.
- `model/requirements.txt` contains only `fastapi/uvicorn/pillow` — **no tesseract, no NLP.** (The root `requirements.txt` *does* list `pytesseract`, `opencv`, `sentence-transformers`, `torch`, `ollama`, but nothing installs or imports them — see "Scrapped prototype" below.)

### Layer 2 — Tamper & Forgery Detection 🟥 ~5%
- **Metadata forensics, font-inconsistency detection, copy-paste seal detection, ELA — none run in the live path.** The model stub emits a fixed verdict, so downstream "tamper" flags in the UI are synthesized from that constant (`is_fraudulent ? [one hardcoded box] : []`).
- The anomaly regions shown on documents for the seeded demo case (`3G327H`) are **hand-authored** in `mock-data.ts` (e.g. `"Seal appears copy-pasted"`, box coordinates typed by hand).

### Layer 3 — Cross-Document Anomaly Detection 🟧 ~10%
**File:** `frontend/src/lib/mock-data.ts` (`addDocToCase`)

- The claimed "unique edge." Live behavior: a **filename string match** — if one uploaded doc's name contains `"salary"` and another contains `"bank"`, a **fixed** conflict sentence is appended. No figures are extracted or compared.
- The compelling "₹80,000 vs ₹40,200" income-mismatch example is a **static string** in the seeded mock case.

### Layer 4 — Lightweight External Correlation 🟥 ~5%
- PAN/CIN/land-registry cross-checks are **hardcoded result strings** in `mock-data.ts` (`external: [...]`) and `integrations` (`"Connected (Test)"`).
- No registry data, no lookups. The scrapped prototype had `registry.py` + mock registry JSON (`cin_registry.json`, `land_records.json`) — not carried into the live services.

### Layer 5 — Intelligent Underwriting Insights 🟧 ~15%
- The three flagship recommendation sentences ("Signature mismatch… Recommend video KYC", "ownership changed 15 days before…", "metadata shows backdating…") are **verbatim static strings** in the seeded mock case, not generated.
- For real uploads, insight text is a **template** filled with the stub's constant score/confidence.
- No LLM is invoked (the scrapped `temp/app/llm.py` used `ollama`; not present live).

### Layer 6 — Bank Officer Dashboard ✅ ~75% (real UI) / data is mock
**Files:** `frontend/src/routes/*` (TanStack Start + shadcn/ui)

- **This is the strongest deliverable.** Full, professional UI: dashboard, case list/detail, **document viewer with anomaly-region overlays**, fraud score gauges/risk pills, report view, decision recording, audit trail, admin/users, settings.
- The real upload → backend → security-gateway → CDR round-trip **works** and renders sanitized page previews.
- **Caveats:**
  - All case data lives in browser `localStorage` (`docverify_cases`), seeded from `mockCasesInitial`. There is **no backend persistence** (the Postgres DB is provisioned but unconnected).
  - The `/analyzing` screen is a **fake 6-step timed animation** (~7s of `setTimeout`), not a live pipeline. It even lists the six ideation layers as if they run.
  - Scores/anomalies shown come from the stub verdict or hand-authored mock, not analysis.

### Layer 7 — Audit Trail (Mock Blockchain Ready) 🟧 ~15%
- **UI:** `audit.tsx` renders a "tamper-evident log" table from `mockCases`. The "hash" column is just the upload's `request_id` (a UUID), not a document hash; Export CSV/PDF buttons are non-functional.
- **Blockchain:** `ledger/` is the **unmodified Hardhat 3 sample project** — `Counter.sol` (`inc()/incBy()`), the sample tests, and the boilerplate README. There is **no DocVerify contract, no hashing-to-chain, nothing project-specific.** "Blockchain ready" = an empty scaffold.
- Note: `security/utils.py` has a real `calculate_sha256()`, but it is **not called** anywhere in the live path.

### Roadmap — Reusable Verification / Verifiable Credentials ⬜ 0%
- Correctly out of scope per the doc ("Planned for Phase 2"). Nothing present, which is expected.

---

## The scrapped prototype (important context)

Git commit `81e2b26` contains `temp/app/` — a **real, substantial implementation** of the ideation layers that has since been **deleted** from the working tree (visible as `D temp/...` in `git status`):

| Module | Lines | Implemented |
|---|---:|---|
| `ingestion.py` | 575 | OCR + text extraction, doc classification, field extraction (L1) |
| `semantic.py` | 276 | Semantic matching (L3) |
| `forensics.py` | 264 | PDF metadata analysis, font analysis, **ELA** (L2) |
| `llm.py` | 157 | LLM underwriting report via ollama (L5) |
| `pipeline.py` | 133 | Orchestrates Layers 1–7 |
| `cross_check.py` | 129 | Cross-document conflict detection (L3) |
| `registry.py` | 122 | External registry correlation (L4) |
| `insights.py` | 95 | Underwriting insights (L5) |
| `audit.py` | 68 | Audit trail (L7) |

That prototype tracked the ideation doc closely (its `pipeline.py` docstring literally reads *"Orchestrates Layers 1–7"*). **The project pivoted** from this monolithic detection pipeline to the current security-gateway + microservice + dashboard architecture — and in doing so, **the actual detection logic was dropped and replaced with stubs.** The root `requirements.txt` (pytesseract/opencv/torch/ollama) is a leftover from this prototype and matches no live service.

> Recovering/porting `temp/app/` into the `model` service would be the single highest-leverage step toward matching the ideation doc.

---

## Cross-cutting claims

- **"Fraud Risk Score within 90 seconds":** No real analysis runs, so timing is not meaningful. The UI *displays* a fake ~72s countdown.
- **"Detects if a PDF was edited in Photoshop/Canva… backdating":** Not implemented live (was in scrapped `forensics.py`).
- **Persistence/multi-user:** None. State is per-browser `localStorage`; the seeded officer/users/cases are mock. Postgres is declared but unwired.

---

## What to prioritize (if realigning to the doc)

1. **Port `temp/app/` (OCR + forensics + cross-check) into the `model` service** — restores L1/L2/L3 with code that already exists.
2. **Wire Postgres** for real case/audit persistence (replace `localStorage`).
3. **Make L7 real:** hash documents with the existing `calculate_sha256()` and store immutably; optionally replace the `ledger/` sample with an actual audit contract.
4. **Replace the fake `/analyzing` animation** with real pipeline progress.
5. **Delete dead code** (`backend/analyzer.py`, `security/scanner.py`, `security/converter.py`) or wire it in.

---

## Bottom line

| Aspect | Verdict |
|---|---|
| Security/CDR gateway (L0, bonus) | Strong, real |
| Dashboard & UX (L6) | Strong, real — but mock-fed |
| Core fraud detection (L1–L5) | **Stubs / mock — not implemented live** |
| Audit trail + blockchain (L7) | Mock UI; blockchain is empty scaffold |
| Data persistence | None (localStorage only) |
| Roadmap (Phase 2) | Not started (as intended) |

**The infrastructure and presentation promise the ideation doc's vision convincingly; the detection substance behind it is largely absent from the running system — despite having existed in an earlier, now-deleted prototype.**

---
---

# Re-audit — 2026-07-04 (after `git fetch`)

*Second pass, triggered by "I have now pulled some changes." This section supersedes the original audit where they conflict — it corrects one significant error above and assesses the newly-fetched work.*

## 0. What actually changed

- **Working tree / HEAD is unchanged** — still `a649fae`. The live source under `backend/ model/ security/ frontend/src/ ledger/` and `docker-compose.yml` is **byte-identical** to what the first audit read (`git diff HEAD -- …` is empty). So nothing that *runs* moved.
- **The "pull" was a `git fetch`, not a merge.** It brought one new commit into remote-tracking only: **`cdcba8f "added schema"` on `docverify/new`**. It is **not on `main`, not in the working tree.**
- **`docverify/new` is a divergent branch, not a superset of `main`.** It forks from an older common ancestor (`128719a`) and carries the *original monolith layout* (top-level `app/`, `data/`, `samples/`, `static/`, `tests/`) with `frontend/` as a **git submodule** — it does **not** contain the `backend/`, `security/`, or `model/` microservices at all. So you cannot simply merge it into `main` to "add the schema"; it represents a different project shape.

## 1. Correction to the first audit (this is the important one)

> The original audit's headline — *"a real ~1,800-line Layers 1–5 implementation exists in git history at `temp/app/` (commit `81e2b26`, since deleted); recover with `git show`"* — **is wrong.** The pipeline is **not deleted.** Commit **`f27342a` ("Refactor: move fraud detection pipeline into backend package")** moved `temp/app/` → **`backend/app/`**, and it is **tracked and present at HEAD right now.**

The real pipeline is sitting in the working tree, alongside the thin proxy:

```
backend/
  app.py            ← thin proxy (the audited "backend": forwards /upload → security gateway)
  app/              ← THE REAL LAYER 1–7 PIPELINE (was temp/app/)
    main.py         ← its own FastAPI app: POST /api/analyze → pipeline.analyze_case()
    pipeline.py     ← "Orchestrates Layers 1-7"
    ingestion.py forensics.py cross_check.py semantic.py registry.py insights.py llm.py audit.py models.py
```

**But it is dead code as shipped — present but not runnable and never invoked.** Three independent reasons:

1. **Name collision breaks the deployed entrypoint.** `backend/Dockerfile` runs `uvicorn app:app`. With both `app.py` (module) and `app/` (package, **empty `__init__.py`**) present, Python resolves `app` to the **package**, which has no `app` attribute. Reproduced locally: `import app` → `backend/app/__init__.py`; `hasattr(app,'app')` → `False`. That is exactly uvicorn's `getattr(module, "app")` failure → **the backend container cannot start as configured.** (This predates the fetch and was missed the first time — it also undercuts the first audit's claim that the upload round-trip "works" via the backend.)
2. **Dependencies aren't installed.** `backend/requirements.txt` = `fastapi/uvicorn/python-multipart/pydantic/pypdf` only. The pipeline imports `fitz` (PyMuPDF), `pytesseract`, `numpy`, `PIL`, `ollama`, `sentence-transformers`, `reportlab` — none installed in the backend image. So `app.main` can't import even if you named it correctly.
3. **It serves a directory that doesn't exist.** `app/main.py` does `StaticFiles(directory=…/backend/static)` and `FileResponse(static/index.html)`; `backend/static/` is absent. Import-time `RuntimeError`.

And nothing calls it: the live path is still `frontend → backend/app.py (proxy) → security:8002 (real CDR) → model:8001 (**stub, `fraud_score: 0.03`**)`. `backend/app/main.py`'s `/api/analyze` is wired to no one.

**Net effect on the layer scores:** the *running behaviour* is unchanged from the first audit (L1–L5 still stub/mock in the live path). What changes is the **recoverability / "how much code exists" story**: L1–L5 is not lost in deleted history requiring `git show` archaeology — it's **in-tree at `backend/app/`, one wiring job away** (install deps, resolve the `app`/`app/` name clash, point the frontend at `/api/analyze`, restore `static/` or drop the mount). That materially raises "how implemented is this?" if you count code-in-repo rather than code-in-the-running-path.

## 2. The fetched work — `schema/` + `ui_plan.md` (`cdcba8f`)

A genuinely well-built **canonical schema / data-contract layer** — *"the single source of truth for all four areas (ML, blockchain, backend, frontend)."*

| File | What it is |
|---|---|
| `schema/models.py` (350) | Pydantic domain models: `BoundingBox, AnomalyRegion, DocumentMetadata, ExtractedFields, Anomaly, Document, ExternalCheck, Conflict, AuditEntry, CaseResult, Applicant, Loan, Decision, Case, User, Integration` + `build_case()` assembler |
| `schema/enums.py` (214) | Canonical vocab: `RiskBand/Severity`, `SEVERITY_WEIGHTS`, `RISK_BAND_THRESHOLDS` + `risk_band()`, `DocType/DocCategory`, `AnomalyLayer/AnomalyCategory` + `anomaly_category()`, lifecycle/decision/role enums |
| `schema/_base.py` (29) | `CanonicalModel` — snake_case in Python, **camelCase on the wire** (FastAPI `by_alias`), so one model feeds both the JSON API and the generated TS |
| `schema/generate.py` (129) | Codegen → `schema/json/docverify.schema.json` (JSON Schema, present, 1107 lines) **and** `frontend/src/lib/schema.ts` (via `json-schema-to-typescript`) |
| `ui_plan.md` (312) | 12-screen UI spec (login → dashboard → new case → upload → analysis → report → viewer → decision → post-decision → audit → admin → settings) tracking the ideation doc |

**Assessment — real value, but it is scaffolding, not detection:**

- ✅ **Strong groundwork.** This is exactly the shared, typed contract the first audit implied was missing (frontend types were ad-hoc, mock-driven). Pydantic-first with generated JSON Schema + TS is a clean way to make ML / backend / blockchain / frontend agree on shapes. `risk_band()` thresholds, `SEVERITY_WEIGHTS`, and `build_case()` are real, testable pure functions.
- 🟥 **Zero change to what runs.** No detector, no OCR, no forensics. It is **not imported by any service** (grep for `import schema` in `backend/model/security` → none), it's on an **unmerged divergent branch**, and that branch **deletes the very `backend/app/` pipeline** discussed in §1. The docstrings describe an integration (`app/audit.py` computing the hash chain, "the case service" calling `build_case`) that **does not exist** in either tree — the contract is written *as if* the ported pipeline were wired up.
- **Also structural:** on `docverify/new`, `frontend/` becomes a **git submodule** (`Subproject commit a8d707e`). Adopting that changes how the repo is cloned/built.

**Layer-score impact of the fetch: ~0%.** It moves the *contract*, not the *capability*.

## 3. Revised bottom line

| Aspect | First audit said | Corrected / updated |
|---|---|---|
| L1–L5 detection code | "deleted, only in git history (`temp/app/`)" | **In-tree at `backend/app/`** (moved by `f27342a`) — but **unwired + entrypoint broken** |
| Backend service health | round-trip "works" | **`uvicorn app:app` can't start** — `app.py` vs `app/` package name collision (reproduced) |
| Running detection behaviour | stub/mock (~15–20%) | **Unchanged** — still stub verdict + mock UI |
| Fetched `schema/` + `ui_plan.md` | n/a | Real, high-quality **contract layer**; unmerged, unimported, **0% detection** |

## 4. Revised priorities

1. **Fix the backend name collision first** — it's a live breakage, not a nicety. Rename the proxy or the package (`backend/app.py` ↔ `backend/app/`), or point the Dockerfile at the real one. Decide *which* backend you want: the thin proxy or `app/main.py`.
2. **Wire `backend/app/` (it's already in-tree)** — add its deps to `backend/requirements.txt` (pymupdf/pytesseract/numpy/pillow/reportlab/ollama…) + system tesseract in the Dockerfile, restore or remove the `static/` mount, and route the frontend's analysis call to `/api/analyze`. This is now the single highest-leverage step and *lower cost than the first audit implied* (no history recovery needed).
3. **Adopt `schema/` as the contract** for that wiring so backend responses and `frontend/src/lib/schema.ts` share one source of truth. Cherry-pick the `schema/` package onto `main` rather than merging the divergent `docverify/new` wholesale.
4. Persistence (Postgres), real L7 hashing, real `/analyzing` progress — unchanged from the first audit's list.

> **Gotcha for whoever continues:** don't `git merge docverify/new` expecting to "just add the schema" — it forks from an old ancestor, drops the microservices, and submodules the frontend. Cherry-pick `cdcba8f`'s `schema/` + `ui_plan.md` instead.

## 5. Completeness of the in-tree detectors (L2–L5, L7)

Now that we know the real pipeline is at `backend/app/` (§1), here is how complete each layer's **code** actually is — measured as algorithm substance, *not* whether it runs (it doesn't — see §1). These are genuine detectors, not the stub/mock the first audit scored.

| Layer | Module | Code completeness | Real? | Dominant gap |
|---|---|---:|---|---|
| **L2** Tamper/forgery | `forensics.py` | ~80% | ✅ real | ELA images-only (PDFs get metadata+fonts, no ELA); no dedicated copy-move detector |
| **L3** Cross-document | `cross_check.py` | ~75% | ✅ real | Fully gated on L1 field extraction; no signature-image matching |
| **L4** Registry | `registry.py` | ~45% | ⚠️ real logic, **no data** | `backend/data/registries/*.json` **missing** → every CIN/survey misfires as "not found" |
| **L5** Insights/scoring | `insights.py`, `llm.py` | ~80% | ✅ real | Deterministic scoring solid; LLM narrative real but ollama not provisioned → degrades to "unavailable" |
| **L7** Audit | `audit.py` | ~80% chain / ~15% "chain-on-blockchain" | ✅ real hash-chain | Local JSONL only; `ledger/` still the `Counter.sol` sample; ephemeral (no volume) |

**L2 — `forensics.py` (real, strong).** Three working sub-detectors: metadata forensics (12 editing-tool signatures, modified-vs-created gap, backdating via claimed-date vs file-born-date with 365d/30d windows, incremental-save `%%EOF` counting), font-outlier detection (per-span font/size usage via `fitz`, flags <20%-usage off-family fonts), and true Error Level Analysis (Q90 recompress → amplified diff → 32px grid hotspots → flood-fill bounding boxes → base64 heatmap). Gap: ELA runs **only on image uploads**; PDFs are never rasterized in this path, so a tampered-PDF's visual forgery isn't ELA-checked. The ideation "copy-pasted seal" is approximated by ELA, not a dedicated copy-move detector.

**L3 — `cross_check.py` (real, shallow).** Actual computed checks over extracted fields: income mismatch (slip claim vs bank-statement avg credits, >25% → HIGH, >40% → CRITICAL), name mismatch (normalized + subset + `difflib` >0.85), conflicting PANs, address divergence (`difflib` <0.5), land-ownership registered ≤60 days before application. The flagship "₹80,000 vs ₹40,200" is now **computed**, not a static string — *if* L1 populates the fields. Entirely dependent on ingestion; no false-positive risk but silent no-op when fields are empty. No signature-image comparison (surfaced only as a recommendation on NAME_MISMATCH). `semantic.py` (BGE-small bi-encoder) is actually an **L1** extraction fallback, degrading gracefully if `sentence-transformers` is absent.

**L4 — `registry.py` (logic real, data gone).** PAN structural validation (regex + 4th-char holder-type) is real and self-contained. CIN status and land survey/owner/date checks are real lookups — but they read `backend/data/registries/cin_registry.json` / `land_records.json`, which **don't exist**: the move commit `f27342a` relocated `app/` but left `temp/data/` behind (now deleted). `_load()` returns `{}`, so every CIN → `CIN_NOT_FOUND` and every survey → `SURVEY_NOT_FOUND` (false positives). Easy fix — restore the JSON from history (`git show 81e2b26:temp/data/registries/…`) into `backend/data/registries/` — but as-shipped L4 is half-broken.

**L5 — `insights.py` + `llm.py` (scoring real; LLM operationally off).** `fraud_score()` is a defensible severity-weighted model (unique per anomaly code, `0.85^rank` diminishing returns, capped 100) with 70/40/15 band thresholds; `recommendations()` maps 16 anomaly codes → concrete underwriting actions, dedup + severity-ordered. All deterministic and real — the insights are **derived**, no longer static strings. `llm.py` is a real ollama call (`qwen2.5:3b`) with a tight reporting-only system prompt and JSON fallback, but nothing provisions an ollama server (not in compose/requirements), and `pipeline.py` wraps it in try/except → falls back to "AI underwriting summary unavailable." So the narrative degrades gracefully to OFF.

**L7 — `audit.py` (real hash-chain; not a blockchain).** Genuine tamper-evident ledger: append-only JSONL where each entry embeds the prior entry's SHA-256; `verify_chain()` re-walks and recomputes every hash + checks `prev_hash` linkage. Records real per-document SHA-256s. It writes fine at runtime (`mkdir parents=True`). But it's a flat file — nothing anchors to `ledger/` (still the untouched `Counter.sol`), and with no compose volume it's ephemeral. As a hash-chain it's ~80% done; as the ideation "blockchain" it's unchanged (~15%).

**Cross-cutting:** all of L2–L5 quality is capped by **L1 ingestion** actually extracting `monthly_income`, `salary_credits`, `pan`, `cin`, `survey_number`, `registration_date`, etc. — the cross-check and registry richness is invisible until L1 fills those fields. And every number above is *code* completeness; **running** completeness is still 0% until §1's wiring is fixed.

## 6. Completeness of L1 ingestion — `ingestion.py` (the ceiling on L2–L5)

**Code completeness ~80%; effective extraction recall on real scanned/tabular docs is the true bottleneck.** The plumbing is excellent and clearly hardened (many `FIX (…)` comments for OCR-noise, determinism, crash-safety); the *breadth* of what it can pull out is the limit — and L3/L4/L5 can only flag what L1 extracts.

| Sub-stage | Fn | Done | Notes |
|---|---|---:|---|
| Text extraction | `extract_text` | ~85% | PyMuPDF text layer + per-page 200 DPI raster→Tesseract fallback (<20 chars); images → Tesseract. **Hard dep on the `tesseract` binary** — absent, every image & scanned-PDF yields empty text → `UNKNOWN`, no fields. No deskew/threshold/denoise. |
| Classification | `classify` | ~70% | Keyword-vote over 5 `DocType`s, deterministic tie-break, `UNKNOWN` on zero hits. Brittle on OCR noise/non-standard templates; **misclassification cascades** (income is extracted *only* for `SALARY_SLIP`; survey/registry checks need `LAND_RECORD`). |
| Field extraction | `extract_fields` | ~80% infra | Two-pass hybrid: regex → BGE-small semantic per-missing-field → validation/coercion → **per-field provenance** (`FieldMeta`: method/confidence/validated/status/`manual_review`). Values only committed when validated; failures left `None` so downstream stays clean. Sane validators (PAN/CIN/date incl. 2-digit years/income bounds [500, 10M]). This provenance layer is above typical production quality. |

**The real ceiling — recall, not plumbing:**

1. **Both passes assume `label : value` on a single line.** The regexes are label-anchored, and the semantic fallback's `extract_line_candidates` reuses the *same* `^label[:\-]value$` line pattern — so Pass 2 only broadens the **label vocabulary**, not the **layout**. Multi-column, tabular, or OCR-wrapped text produces no candidates and both passes miss.
2. **No table parsing.** Bank statements/salary slips are tables. `salary_credits` is scraped by a loose regex (any line containing "salary" → grab a number), which can catch the wrong column (balance vs credit). That value feeds L3's flagship `INCOME_MISMATCH` — so the headline cross-check rides on a fragile scrape.
3. **`monthly_income` is gated on `SALARY_SLIP` classification** — a classify() miss silently suppresses the income comparison.
4. **Semantic Pass 2 needs `sentence-transformers` + `torch` + a ~130 MB model download** on first call (not in `backend/requirements.txt`); it degrades gracefully to regex-only, at which point every non-`label:value` field → `NOT_FOUND`/manual review.

**Failure mode is mostly false-negative (silent), not false-positive:** unextracted fields just leave L3/L4 quiet — *except* L4's missing registry JSON (§5), which false-positives on any CIN/survey that *does* get extracted. L2 (metadata/fonts/ELA) works on raw bytes and is **not** capped by L1.

**Model divergence to reconcile during wiring:** the pipeline's `backend/app/models.py` (`DocumentReport`, `ExtractedFields.extraction_meta`, `CaseResult.llm_summary` + `audit_entry: dict`, `Anomaly.layer: str`) does **not** match the fetched `schema/models.py` (`Document`/`Case`, `CaseResult.external_checks`, `Anomaly` with `id`/`code`/enum `layer`/`category`). Adopting `schema/` (§2) means writing an adapter or refactoring the pipeline onto the canonical models — not a drop-in.

**L1 verdict:** real, well-engineered, crash-hardened extractor with best-in-class provenance — but layout-bound (label:value + regex), so on messy real-world Indian loan docs its field recall (and therefore the entire L3/L4/L5 "cross-document intelligence" the product sells) will be modest until table/template-aware extraction is added.
