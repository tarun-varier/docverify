# DocVerify — Detection Depth Design (Item 5)

**Date:** 2026-07-05
**Companions:** `docs/implementation_audit.md` §5 (L2/L3/L4) and §6 (L1 ceiling), `docs/ideation_doc.md`, `docs/wiring_plan.md` (architecture boundary)
**Status:** Design decided in a whiteboard session. No service code has changed yet — this doc is the design-of-record for follow-up implementation issues.

---

## What "item 5" is

Detection *depth* beyond the audit's core asks — the long-tail quality that separates "runs correctly on crafted test docs" from "robust on real Indian loan paperwork." Three sub-areas, each with a real design fork that had to be resolved before any code:

- **5a** — L4 registry integrations run against static JSON fixtures today; real vs. mock is a scope call.
- **5b** — no dedicated copy-move detector, and signature-image matching is *undefined* without a reference signature.
- **5c** — L1 OCR has no preprocessing and only a brittle single-line-regex table scrape; deeper extraction could cross the security/model architecture boundary.

**Headline result: every fork below resolved to the lower-risk, architecture-boundary-preserving option.** Nothing in this design moves PDF-native extraction into `security`, and nothing adds a new unprovisioned external dependency (real registry APIs, LLM-assisted extraction). This matches the house style — graceful degradation, submission scope discipline, the 90-second SLA — over production completeness.

---

## 5a — Real registry integrations (L4)

| | |
|---|---|
| **Chosen approach** | Richer mock fixtures behind a pluggable adapter interface — not real external APIs |
| **PAN** | Stays structural-only (regex + 4th-char holder-type validation) |
| **Placement** | `model/pipeline/registry.py` — unchanged, operates on already-extracted fields |
| **New dependencies** | None |

**Why not real APIs:** PAN/NSDL, MCA/ROC (CIN), CERSAI, and state-specific land records each require separate auth, have their own rate limits, and differ per state. Real integration risks blowing the 90-second SLA and makes demo reliability depend on third-party uptime — not worth it for a submission where "core fraud detection remains the focus."

**Why PAN stays structural-only:** there is no public PAN verification API without an NSDL agreement, so structural validation already matches production reality — a mock PAN adapter would add interface consistency but no substance, and was explicitly rejected for that reason.

**In scope now:**
- Define a small `RegistryAdapter` protocol (e.g. `lookup_cin(cin) -> CINResult`, `lookup_land(survey_no) -> LandResult`) with a `MockRegistryAdapter` implementation — the same interface a real adapter would satisfy later.
- Enrich the fixture JSON (`cin_registry.json`, `land_records.json`) with more realistic variety: multiple CIN statuses (active/struck-off/dissolved), multi-entry land ownership history with dates — so the "ownership changed ≤60 days before application" check has real cases to exercise, not just a single canned record.
- Simulate latency (~50–200ms) and occasional not-found/timeout responses *deliberately*, so the graceful-degradation path is exercised on purpose rather than discovered by accident via missing data.

**False-positive risk:** fixture staleness or mismatch against demo case IDs. Mitigate by keeping fixtures aligned to the seeded demo case plus a handful of adversarial variants.

**Later / explicitly out of scope now:** real CERSAI / MCA-ROC / state land-record API integration. The adapter interface is the re-pointing seam for this; auth/cost/latency tradeoffs are only worth revisiting if this moves from submission-demo to production.

---

## 5b — Copy-move / signature-image detection (L2)

| | |
|---|---|
| **Chosen approach** | Dedicated block-matching copy-move detector |
| **Signature matching** | Out of scope — no reference signature source exists |
| **Placement** | `model`, on safe flattened PNGs — same home as ELA |
| **New dependencies** | numpy (present); optional scipy/opencv for clustering, graceful-degrade if absent |

**Why not signature matching:** matching is undefined without something to match *against*. This submission has no KYC document store and no defined convention for treating one uploaded document as a trusted reference for another. Rather than inventing an unjustified reference source, signature-image matching is dropped entirely; today's behavior — a name mismatch surfaces a "recommend video KYC" action — stays as the stand-in.

**Why block-matching over keypoint (SIFT/ORB):** simpler, faster, and easier to bound at the 90-second SLA. It's tuned for exactly the ideation doc's target case — a duplicated rectangular region like a pasted seal/stamp — at the cost of being less robust to rotation/scale of the pasted region, which is an acceptable tradeoff for this submission.

**In scope now:**
- Tile each safe PNG page into overlapping fixed-size blocks (e.g. 16×16 or 32×32), reduce each to a compact descriptor (DCT low-frequency coefficients or average-hash), and search for near-duplicate block pairs above a similarity threshold.
- False-positive controls: require a minimum spatial separation between matched blocks (rejects trivially-uniform backgrounds matching themselves), reject low-variance/near-blank blocks outright (whitespace matches everywhere), require a minimum cluster size before reporting (an isolated single-block match is noise, not a finding), and cap the number of reported regions per page.
- Emit a new finding (e.g. `COPY_MOVE_REGION`) with a bounding box, alongside the existing ELA output — not replacing it.

**Explicitly out of scope:** signature-image matching. Revisit only if/when a real reference-signature source (e.g. a KYC document store) becomes available.

---

## 5c — OCR recall / extraction depth (L1)

| | |
|---|---|
| **Chosen approach** | Deterministic preprocessing (deskew/binarize/denoise) + generalized table heuristics on the OCR/text stream |
| **Data source for tables** | OCR/text heuristics — explicitly not native-PDF word coordinates |
| **LLM-assisted extraction** | Out of scope for this submission |
| **Multi-language** | Out of scope for this submission |
| **Placement** | Entirely within `model`, on the safe PNGs / OCR text it already owns |
| **New dependencies** | opencv (`cv2`) for deskew/denoise, if not already present — graceful-degrade to raw-PNG Tesseract if unavailable |

**The architecture fork, resolved:** the handoff flagged that if better OCR needed higher-DPI rasters or the native PDF text layer *with coordinates*, that extraction would have to move upstream into `security` (before CDR flattening), since `model` only ever sees safe PNGs/text. This design deliberately stays on OCR/text heuristics instead of native-PDF word coordinates — so **no security-side change is needed**, and the security/model boundary from `docs/wiring_plan.md` is preserved untouched. The tradeoff is weaker column reconstruction on complex multi-column tables, and no help at all for scanned/photographed documents (which never had native text to begin with) — judged an acceptable ceiling for this submission.

**In scope now:**
- A preprocessing step in `model`, ahead of/around the existing Tesseract fallback: deskew (Hough-line or minAreaRect angle correction), binarize (adaptive threshold), denoise (median blur / morphological open).
- Generalize the table logic added in PR #3 (currently salary-specific) into a reusable column-detection heuristic driven by spacing/alignment patterns in the OCR/text output — so it also helps e.g. bank-statement credit-column extraction, not just salary slips.

**Explicitly out of scope for this submission:**
- **LLM-assisted extraction fallback** — ties to the ollama work tracked separately; deliberately deferred since it adds non-determinism and a new operational dependency.
- **Multi-language / Devanagari support.**
- **Native-PDF-coordinate table reconstruction** — would require moving text extraction into `security`; deliberately avoided to keep this item's blast radius inside `model`.

---

## Cross-cutting notes

- Every new detector follows the existing graceful-degrade house style: missing optional dependencies or fixture misses register as "not run"/"not found," never crash the pipeline.
- **Nothing in item 5 crosses the security/model architecture boundary.** All of it lands inside `model`, so the isolated Docker build contexts (`./security`, `./model`, `.`) are unaffected.
- New anomaly codes (`COPY_MOVE_REGION`) and adapter result shapes should be written with the eventual `schema/` adoption in mind (canonical `Anomaly`/enum shapes), so that migration doesn't force a redesign later — a note for whoever does that adoption, not a blocker now.

---

## Follow-up issues

1. Registry adapter interface + enriched mock fixtures (5a)
2. Block-matching copy-move detector (5b)
3. OCR preprocessing pipeline — deskew/binarize/denoise (5c)
4. Generalized table-parsing heuristic beyond salary (5c)

No service code changes shipped in this session — the above are the implementation follow-ups.
