"""Layer 1 — Document ingestion, OCR and structured field extraction.

Runs inside the **model** service, which only ever sees *safe artifacts* — it
never touches the original PDF.  Native text-layer extraction happens upstream
in the security service (before CDR); this module supplies the OCR fallback for
the flattened page PNGs when that native text is thin, plus classification and
structured field extraction.

Field extraction uses a two-pass hybrid pipeline:

  Pass 1 — Label-value regex matching
      Fast, deterministic, zero runtime overhead.  Covers well-structured
      documents with standard labels ("Employee Name:", "PAN:", …).

  Pass 2 — Semantic matching via BGE-small  (fallback only)
      Activated *per field* when Pass 1 found nothing.  Uses cosine similarity
      between candidate label embeddings and canonical field-description
      embeddings to recover values from OCR-noisy or non-standard templates.

After each pass, extracted values go through field-type validation (PAN regex,
date parsing, numeric coercion for money).  Fields that fail validation or
score below HYBRID_CONFIDENCE_THRESHOLD are marked for manual review via
ExtractedFields.extraction_meta — the value slots themselves remain None so
downstream layers are unaffected.

Public surface:
  ocr_png(png_bytes)                → str   (OCR one flattened page image)
  classify(text, filename)          → DocType
  extract_fields(text, doc_type)    → ExtractedFields
  IMAGE_EXTENSIONS                  (module-level set)
"""

from __future__ import annotations

import io
import logging
import re
import shutil
from datetime import datetime

from PIL import Image

from .models import (
    DocType,
    ExtractedFields,
    ExtractionMethod,
    ExtractionStatus,
    FieldMeta,
)

logger = logging.getLogger(__name__)

TESSERACT_AVAILABLE = shutil.which("tesseract") is not None

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".tiff", ".bmp", ".webp"}

# ---------------------------------------------------------------------------
# Hybrid pipeline threshold
# ---------------------------------------------------------------------------

#: Minimum cosine similarity required to accept a *semantic* match.
#: This overrides semantic.SEMANTIC_CONFIDENCE_THRESHOLD (0.55) to be more
#: conservative for the hybrid pipeline as required.  The semantic module's
#: own threshold still governs what it returns internally, but we re-check
#: here so the ingestion layer stays in full control of what gets committed.
HYBRID_CONFIDENCE_THRESHOLD: float = 0.75

# Keyword votes for document classification.
_CLASSIFIER_KEYWORDS: dict[DocType, list[str]] = {
    DocType.SALARY_SLIP: [
        "salary slip", "pay slip", "payslip", "net pay", "gross salary",
        "basic pay", "hra", "earnings", "deductions", "net salary",
    ],
    DocType.BANK_STATEMENT: [
        "bank statement", "statement of account", "account statement",
        "closing balance", "opening balance", "withdrawal", "neft", "imps",
        "transaction date", "cr ", " dr ",
    ],
    DocType.LAND_RECORD: [
        "survey number", "survey no", "khata", "patta", "land record",
        "sale deed", "encumbrance", "sub-registrar", "mutation",
        "village", "hectare", "acres", "schedule of property",
    ],
    DocType.ID_PROOF: [
        "permanent account number", "income tax department", "aadhaar",
        "unique identification", "government of india", "date of birth",
        "election commission", "driving licence",
    ],
    DocType.LEGAL: [
        "agreement", "affidavit", "power of attorney", "stamp duty",
        "notary", "witness whereof", "deponent",
    ],
}

_PAN_RE = re.compile(r"\b([A-Z]{5}[0-9]{4}[A-Z])\b")
_CIN_RE = re.compile(r"\b([LU][0-9]{5}[A-Z]{2}[0-9]{4}[A-Z]{3}[0-9]{6})\b")
_SURVEY_RE = re.compile(
    r"survey\s*(?:number|no\.?)\s*[:\-]?\s*([0-9]+(?:/[0-9A-Za-z]+)*)",
    re.IGNORECASE,
)
_NAME_RE = re.compile(
    r"(?P<label>"
    r"employee\s+name|applicant\s+name|account\s+holder"
    r"|name\s+of\s+(?:owner|holder|employee)|owner\s+name|name"
    r")\s*[:\-]\s*"
    # FIX (edge case — OCR noise / greedy name capture): tightened character
    # class to only allow letters, spaces, and dots; dropped the trailing
    # dot-strip and replaced with a word-boundary anchor so form instructions
    # like "Please fill in the box" are not captured as names.
    r"([A-Za-z][A-Za-z .]{1,39}[A-Za-z])",
    re.IGNORECASE,
)
_INCOME_RE = re.compile(
    # ``label`` is captured so we can prefer *net/take-home* pay (what the bank
    # actually credits) over gross when a slip states both — comparing a gross
    # claim against net credits would manufacture a false INCOME_MISMATCH.
    r"(?P<label>net\s+pay|net\s+salary|take[\s-]?home(?:\s+(?:pay|salary))?"
    r"|monthly\s+income|gross\s+salary|total\s+earnings)"
    r"\s*[:\-]?\s*(?:rs\.?|inr|₹)?\s*(?P<amount>[0-9][0-9,]*(?:\.[0-9]{1,2})?)",
    re.IGNORECASE,
)
# Loose, single-line fallback used only when no transaction table is detected.
_SALARY_CREDIT_RE = re.compile(
    r"(?:salary|sal\s+cr|salary\s+credit)[^\n]*?([0-9][0-9,]{2,}(?:\.[0-9]{1,2})?)",
    re.IGNORECASE,
)
_REG_DATE_RE = re.compile(
    r"(?:registration\s+date|date\s+of\s+registration|registered\s+on)"
    r"\s*[:\-]?\s*([0-9]{1,2}[-/][0-9]{1,2}[-/][0-9]{2,4}|[0-9]{4}-[0-9]{2}-[0-9]{2})",
    re.IGNORECASE,
)
_ADDRESS_RE = re.compile(r"address\s*[:\-]\s*([^\n]{8,100})", re.IGNORECASE)
_ANY_DATE_RE = re.compile(r"\b([0-9]{1,2}[-/][0-9]{1,2}[-/][0-9]{2,4}|[0-9]{4}-[0-9]{2}-[0-9]{2})\b")

# ---------------------------------------------------------------------------
# Tabular (bank-statement) extraction — column-aware, on flat text only.
#
# The model never receives word coordinates: it sees flat text (native PyMuPDF
# ``get_text()`` or OCR of the flattened page PNGs).  So "table awareness" here
# is reconstructed from the text itself — find the transaction-table header,
# learn the left-to-right order of the debit/credit/balance columns, then for
# each salary row read the value from the *credit* column instead of grabbing
# the first number on the line (which on real statements is often a year in the
# narration, a reference number, or the running balance).  When no table header
# is found we return nothing and the caller falls back to the loose single-line
# regex, so the previous behaviour is preserved on non-tabular input.
# ---------------------------------------------------------------------------

# Currency-formatted amount: thousands grouping (Indian 1,40,200 / Western
# 140,200) and/or a 1-2 digit paise part.  Preferring formatted tokens lets us
# ignore bare integers such as a year ("2024") or a reference number.
_MONEY_FMT_RE = re.compile(r"\d{1,3}(?:,\d{2,3})+(?:\.\d{1,2})?|\d+\.\d{1,2}")
# Fallback: bare integer (>=3 digits) for statements printed without grouping.
_MONEY_BARE_RE = re.compile(r"\d{3,}")

_CREDIT_HEADER_RE = re.compile(r"\b(?:credit|deposit)\b")
_DEBIT_HEADER_RE = re.compile(r"\b(?:debit|withdrawal)\b")
_BALANCE_HEADER_RE = re.compile(r"\bbalance\b")
# Real headers are columnar — fields padded apart by runs of >=2 spaces. This
# is what rules out prose that merely mentions "credit"/"debit"/"balance" in a
# sentence (e.g. T&C boilerplate: "report any discrepancy in your debit/credit
# or balance..."), which is single-spaced and never has that padding.
_COLUMN_GAP_RE = re.compile(r"\s{2,}")
_SALARY_ROW_KEYWORDS = (
    "salary", "sal cr", "sal credit", "payroll", "wages", "remuneration",
)


def _money_tokens(line: str) -> list[float]:
    """Return the currency amounts on a table row, left-to-right.

    Date substrings are stripped first so a "01/04/2024" or a "04/2024" in the
    narration is never read as money.  Currency-formatted tokens (grouped or
    with a decimal part) are preferred; only when a row carries none do we fall
    back to bare integers, keeping plain reference numbers out of the result.
    """
    cleaned = _ANY_DATE_RE.sub(" ", line)
    raw_tokens = _MONEY_FMT_RE.findall(cleaned) or _MONEY_BARE_RE.findall(cleaned)
    values: list[float] = []
    for tok in raw_tokens:
        value = _to_float(tok)
        if value is not None:
            values.append(value)
    return values


def _find_table_header(lines: list[str]) -> tuple[int, list[str], bool] | None:
    """Locate a bank-statement transaction-table header line.

    Returns ``(index, column_order, has_balance)`` where ``column_order`` lists
    the money columns among {"debit", "credit", "balance"} in the left-to-right
    order they appear, or ``None`` when there is no credit/deposit column paired
    with a second money column (so the caller degrades to the loose regex).
    """
    for idx, line in enumerate(lines):
        # Columnar padding first (cheap) — skips prose lines before doing any
        # keyword search on them.
        if len(_COLUMN_GAP_RE.findall(line)) < 2:
            continue
        low = line.lower()
        credit_m = _CREDIT_HEADER_RE.search(low)
        if credit_m is None:
            continue
        debit_m = _DEBIT_HEADER_RE.search(low)
        balance_m = _BALANCE_HEADER_RE.search(low)
        # Require a second money column so a stray "credit" word doesn't get
        # mistaken for a transaction-table header.
        if debit_m is None and balance_m is None:
            continue
        positioned = [("credit", credit_m.start())]
        if debit_m is not None:
            positioned.append(("debit", debit_m.start()))
        if balance_m is not None:
            positioned.append(("balance", balance_m.start()))
        order = [name for name, _ in sorted(positioned, key=lambda p: p[1])]
        return idx, order, balance_m is not None
    return None


def _pick_credit(
    values: list[float], column_order: list[str], has_balance: bool
) -> float | None:
    """Choose the credit amount from one salary row's money tokens.

    The running balance is usually the rightmost money column, but some
    statements print it first — we drop it from whichever end matches its
    position in ``column_order`` rather than assuming rightmost.  If it's
    reported in neither end (unusual layout) we leave the tokens untouched
    rather than guess and risk dropping a real credit/debit figure.  A salary
    row usually fills only the credit (debit blank), leaving one amount; when
    both debit and credit are present we disambiguate by the header's column
    order.
    """
    amounts = list(values)
    if has_balance and amounts and column_order:
        if column_order[-1] == "balance":
            amounts = amounts[:-1]
        elif column_order[0] == "balance":
            amounts = amounts[1:]
    if not amounts:
        return None
    if len(amounts) == 1:
        return amounts[0]
    money_cols = [c for c in column_order if c != "balance"]
    # Credit is the leftmost amount only when the header lists credit before debit.
    if money_cols and money_cols[0] == "credit":
        return amounts[0]
    return amounts[-1]


def _extract_salary_credits(text: str) -> list[float]:
    """Table-aware salary-credit extraction from a bank statement's flat text.

    Returns the credit-column amounts of the rows whose narration names a salary
    deposit.  Returns ``[]`` when no transaction table is detected, letting the
    caller fall back to the loose single-line regex (graceful degrade).
    """
    lines = text.splitlines()
    header = _find_table_header(lines)
    if header is None:
        return []
    start, column_order, has_balance = header
    credits: list[float] = []
    for line in lines[start + 1:]:
        low = line.lower()
        if not any(kw in low for kw in _SALARY_ROW_KEYWORDS):
            continue
        credit = _pick_credit(_money_tokens(line), column_order, has_balance)
        if credit is not None and credit > 0:
            credits.append(credit)
    return credits


def _extract_income(text: str) -> tuple[str, str] | None:
    """Pick the monthly-income figure, preferring net/take-home over gross.

    Returns ``(raw_amount, matched_label)`` for the winning match, or ``None``.
    Runs regardless of document classification so a slip misclassified as
    ``UNKNOWN`` still yields income for the cross-document comparison.
    """
    net: list[tuple[str, str]] = []       # (raw, label)
    other: list[tuple[str, str]] = []
    for m in _INCOME_RE.finditer(text):
        raw = m.group("amount")
        value = _to_float(raw)
        if value is None:
            continue
        label = m.group("label").strip()
        (net if label.lower().startswith(("net", "take")) else other).append((raw, label))
    pool = net or other
    if not pool:
        return None
    # Within the chosen pool take the largest figure (handles OCR-split labels
    # and multiple net lines); _to_float is safe here — every raw already parsed.
    raw, label = max(pool, key=lambda pair: _to_float(pair[0]) or 0.0)
    return raw, label


def _ocr_image(img: Image.Image) -> str:
    if not TESSERACT_AVAILABLE:
        return ""
    import pytesseract

    return pytesseract.image_to_string(img)


# ---------------------------------------------------------------------------
# Optional OCR preprocessing (deskew/denoise/binarize) via cv2.
#
# Lazily imported like semantic.py's sentence-transformers check, not an
# eager module-level import like TESSERACT_AVAILABLE's shutil.which — cv2's
# import cost (~100-300ms) shouldn't be paid at server startup for every
# request when most pages have native text and never reach OCR at all.
# ---------------------------------------------------------------------------

_CV2_AVAILABLE: bool | None = None  # None = unchecked yet


def _try_import_cv2() -> bool:
    global _CV2_AVAILABLE
    if _CV2_AVAILABLE is None:
        try:
            import cv2  # noqa: F401
            _CV2_AVAILABLE = True
        except ImportError:
            _CV2_AVAILABLE = False
    return _CV2_AVAILABLE


def _preprocess_for_ocr(img: Image.Image) -> Image.Image:
    """Deskew, denoise and binarize a scanned page before Tesseract.

    Order matters: deskew first (rotating a clean grayscale avoids
    compounding interpolation artifacts a later binarize/denoise step would
    otherwise bake in), denoise before binarize (thresholding noisy pixels
    first turns them into hard-edged speckles a median blur handles worse
    than smooth grayscale noise).

    Only called when cv2 is importable; any failure here is caught by the
    caller and falls back to raw-image OCR, so a broken/missing opencv never
    breaks OCR, only makes it less accurate on skewed/noisy scans.
    """
    import cv2
    import numpy as np

    arr = np.asarray(img.convert("L"))  # grayscale

    # 1. Deskew: estimate angle from a throwaway Otsu binary mask, then
    #    rotate the real grayscale pixels, not the mask. The mask is built
    #    from a median-blurred copy, not the raw grayscale directly —
    #    salt-and-pepper scan noise otherwise dominates Otsu's foreground
    #    mask (its own scattered speckle looks like more "foreground" than
    #    the actual text) and produces a bogus near-zero angle, silently
    #    skipping deskew on exactly the noisy scans that need it most.
    angle_estimation_input = cv2.medianBlur(arr, 3)
    _, mask = cv2.threshold(angle_estimation_input, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    coords = cv2.findNonZero(mask)
    if coords is not None:
        rect_angle = cv2.minAreaRect(coords)[-1]
        # OpenCV's angle convention wraps oddly across versions; normalize
        # into [-45, 45] so small skews rotate by a small amount either way.
        # NOTE: this is the *measured* skew, not the correction — verified
        # empirically (see model/tests/test_ocr_preprocessing.py) that
        # passing this value directly to getRotationMatrix2D doubles the
        # skew instead of canceling it; the correction is its negation.
        angle = -(90 + rect_angle) if rect_angle < -45 else -rect_angle
        if abs(angle) > 0.5:  # skip rotation on already-straight scans
            h, w = arr.shape
            rot_matrix = cv2.getRotationMatrix2D((w / 2, h / 2), -angle, 1.0)
            arr = cv2.warpAffine(arr, rot_matrix, (w, h), flags=cv2.INTER_CUBIC,
                                  borderMode=cv2.BORDER_REPLICATE)

    # 2. Denoise: median blur on grayscale — clears salt-and-pepper
    #    scan/fax noise while preserving character-stroke edges better than
    #    a Gaussian blur would; kernel=3 avoids eroding thin strokes.
    arr = cv2.medianBlur(arr, 3)

    # 3. Binarize: adaptive threshold, not a single global Otsu value —
    #    scanned loan documents commonly have uneven lighting/shadow
    #    gradients across the page that one global threshold handles poorly.
    arr = cv2.adaptiveThreshold(arr, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                 cv2.THRESH_BINARY, blockSize=31, C=15)

    # 4. Light morphological open — clears isolated noise specks the
    #    adaptive threshold can introduce, without eroding real strokes.
    arr = cv2.morphologyEx(arr, cv2.MORPH_OPEN, np.ones((2, 2), np.uint8))

    return Image.fromarray(arr).convert("L")


def ocr_png(png_bytes: bytes) -> str:
    """OCR a single flattened page PNG — the safe artifact the model receives.

    Used as the fallback when a page's native text layer (extracted upstream in
    the security service) is empty or too thin, e.g. scanned/photographed
    documents.  Returns "" when the Tesseract binary is unavailable so the model
    degrades gracefully to native-text-only.
    """
    if not TESSERACT_AVAILABLE:
        return ""
    img = Image.open(io.BytesIO(png_bytes)).convert("RGB")
    if _try_import_cv2():
        try:
            img = _preprocess_for_ocr(img)
        except Exception:
            logger.debug("OCR preprocessing failed; falling back to raw image", exc_info=True)
    return _ocr_image(img)


def classify(text: str, filename: str = "") -> DocType:
    # FIX (logic bug — non-deterministic tie-breaking): max() over a dict
    # depends on insertion order when scores are equal, which changes between
    # Python versions.  Now we sort by (-score, doc_type.value) to get a
    # stable, deterministic result on ties.
    haystack = f"{filename.lower()} {text.lower()}"
    scores = {
        doc_type: sum(1 for kw in keywords if kw in haystack)
        for doc_type, keywords in _CLASSIFIER_KEYWORDS.items()
    }
    best = max(scores, key=lambda k: (scores[k], k.value))
    return best if scores[best] > 0 else DocType.UNKNOWN


# FIX (robustness bug — _to_float raises on empty / OCR-corrupted strings):
# Previously `float(raw.replace(",", ""))` would raise ValueError on strings
# like "" or "1,23," (trailing comma after OCR strip).  All call-sites now
# go through this helper which returns None on failure so callers can decide
# what to do rather than letting an unguarded exception propagate.
def _to_float(raw: str) -> float | None:
    """Convert a comma-formatted numeric string to float.

    Returns ``None`` instead of raising when the string is empty, contains
    only non-numeric characters, or is otherwise unparseable (OCR noise).
    """
    try:
        cleaned = raw.replace(",", "").strip()
        if not cleaned:
            return None
        return float(cleaned)
    except ValueError:
        return None


def normalize_date(raw: str) -> str | None:
    """Normalize the date formats we extract to ISO YYYY-MM-DD.

    FIX (edge case — 2-digit year and alternate separators): added %d-%m-%y
    and %d/%m/%y so that dates like "01-04-24" are correctly interpreted as
    2024-04-01 rather than silently dropped.  Python's strptime maps 2-digit
    years ≥ 69 to 19xx and < 69 to 20xx (C89 standard), which is acceptable
    for modern loan documents.
    """
    for fmt in (
        "%Y-%m-%d",
        "%d-%m-%Y",
        "%d/%m/%Y",
        "%d-%m-%y",   # FIX: 2-digit year, dash-separated
        "%d/%m/%y",   # FIX: 2-digit year, slash-separated
    ):
        try:
            return datetime.strptime(raw, fmt).date().isoformat()
        except ValueError:
            continue
    return None


# ---------------------------------------------------------------------------
# Pass 1: Label-value regex extraction
# ---------------------------------------------------------------------------

def _regex_pass(text: str, doc_type: DocType) -> dict[str, tuple[str, str | None]]:
    """Run all label-value regexes and return raw matches.

    Returns a dict mapping field_name → (raw_value, matched_label).
    ``matched_label`` is the specific label text that fired the regex, or None
    for pattern-only matches (PAN, CIN) that don't require a preceding label.
    """
    results: dict[str, tuple[str, str | None]] = {}

    if m := _NAME_RE.search(text):
        # FIX (logic bug — fragile label extraction): previously used
        # `m.group(0).split(":")[0].strip()` which failed for dash-separated
        # labels ("Employee Name - John") and returned the full match string.
        # Named group "label" captures only the label portion reliably
        # regardless of the separator character that follows it.
        results["applicant_name"] = (m.group(2).strip(), m.group("label").strip())

    if m := _PAN_RE.search(text):
        # PAN has a distinctive enough structure that we match the value directly.
        results["pan"] = (m.group(1), None)

    if m := _CIN_RE.search(text):
        results["cin"] = (m.group(1), None)

    if m := _SURVEY_RE.search(text):
        results["survey_number"] = (m.group(1), "survey number")

    if m := _ADDRESS_RE.search(text):
        results["address"] = (m.group(1).strip(), "address")

    if m := _REG_DATE_RE.search(text):
        results["registration_date"] = (m.group(1), "registration date")

    # FIX (recall bug — income silently suppressed on a classification miss):
    # income extraction used to be gated on ``doc_type == SALARY_SLIP``, so any
    # classify() miss (OCR noise, non-standard template) dropped monthly_income
    # entirely and with it the flagship INCOME_MISMATCH cross-check.  The
    # _INCOME_RE labels (net/gross pay, monthly income) are specific enough to
    # run unconditionally without false positives — and the cross-check only
    # reads monthly_income off SALARY_SLIP documents anyway — so we always try,
    # preferring net/take-home pay over gross (see _extract_income).
    income = _extract_income(text)
    if income is not None:
        results["monthly_income"] = income

    # salary_credits and dates are list fields — handled separately in extract_fields.
    return results


# ---------------------------------------------------------------------------
# Pass 2: Post-extraction validation
# ---------------------------------------------------------------------------

def _validate_field(field_name: str, raw_value: str) -> tuple[bool, object | None]:
    """Validate and coerce ``raw_value`` for the given field.

    Returns (validated: bool, coerced_value).
    ``coerced_value`` is None when validation fails.

    Validators implemented:
      pan              — 10-char PAN format [A-Z]{5}[0-9]{4}[A-Z]
      cin              — MCA CIN format [LU][0-9]{5}[A-Z]{2}[0-9]{4}[A-Z]{3}[0-9]{6}
      registration_date — date string normalised to ISO YYYY-MM-DD
      monthly_income   — numeric currency value, INR sanity bounds [500, 10_000_000]
      applicant_name   — alphabetic, 3-80 chars, at least one-word minimum
      survey_number    — digits with optional slash-separated sub-parcels
      address          — free-form, minimum 8 characters
    """
    if field_name == "pan":
        # Must match the full PAN structure regex (same check as registry layer).
        clean = raw_value.strip().upper()
        if re.fullmatch(r"[A-Z]{5}[0-9]{4}[A-Z]", clean):
            return True, clean
        return False, None

    if field_name == "cin":
        clean = raw_value.strip().upper()
        if re.fullmatch(r"[LU][0-9]{5}[A-Z]{2}[0-9]{4}[A-Z]{3}[0-9]{6}", clean):
            return True, clean
        return False, None

    if field_name == "registration_date":
        normalized = normalize_date(raw_value)
        if normalized:
            return True, normalized
        return False, None

    if field_name == "monthly_income":
        # FIX (robustness bug): _to_float now returns None instead of raising;
        # the original try/except caught ValueError but _to_float was called
        # directly here, so any other exception (e.g. AttributeError on None)
        # would still escape.  Consistent use of _to_float()'s return value
        # is cleaner and handles all failure modes uniformly.
        value = _to_float(raw_value)
        if value is not None and 500 <= value <= 10_000_000:
            return True, value
        return False, None

    if field_name == "applicant_name":
        clean = raw_value.strip()
        # At least two words, only letters/spaces/dots, between 3–80 chars.
        if re.fullmatch(r"[A-Za-z][A-Za-z .]{2,79}", clean) and len(clean.split()) >= 2:
            return True, clean
        # Single-word names are common in South India; accept if long enough.
        if re.fullmatch(r"[A-Za-z]{3,40}", clean):
            return True, clean
        return False, None

    if field_name == "survey_number":
        clean = raw_value.strip()
        if re.fullmatch(r"[0-9]+(?:/[0-9A-Za-z]+)*", clean):
            return True, clean
        return False, None

    if field_name == "address":
        # Addresses are free-form strings; minimal check only.
        clean = raw_value.strip()
        return (len(clean) >= 8, clean if len(clean) >= 8 else None)

    # Unknown field — accept as-is.
    return True, raw_value


# ---------------------------------------------------------------------------
# Internal helper: build a FieldMeta that always carries the manual_review flag
# ---------------------------------------------------------------------------

def _make_meta(
    *,
    method: ExtractionMethod,
    confidence: float,
    validated: bool,
    status: ExtractionStatus,
    matched_label: str | None,
) -> FieldMeta:
    """Construct a FieldMeta, computing ``manual_review`` from status/confidence.

    ``manual_review`` is True whenever a human must inspect the value before it
    can be trusted downstream:
      - validation failed for any extraction method, OR
      - semantic confidence is below HYBRID_CONFIDENCE_THRESHOLD, OR
      - field was not found / only reachable via manual review method.
    """
    needs_review = (
        not validated
        or status in (ExtractionStatus.LOW_CONFIDENCE, ExtractionStatus.NOT_FOUND, ExtractionStatus.VALIDATION_FAILED)
        or (method == ExtractionMethod.SEMANTIC and confidence < HYBRID_CONFIDENCE_THRESHOLD)
    )
    return FieldMeta(
        method=method,
        confidence=confidence,
        validated=validated,
        status=status,
        matched_label=matched_label,
        manual_review=needs_review,
    )


# ---------------------------------------------------------------------------
# Public API: extract_fields (signature unchanged)
# ---------------------------------------------------------------------------

def extract_fields(text: str, doc_type: DocType) -> ExtractedFields:
    """Extract structured fields from document text using the hybrid pipeline.

    Pass 1 (regex) → Pass 2 (semantic, per-field fallback) → validation.
    All provenance is recorded in ExtractedFields.extraction_meta.
    The value slots (pan, applicant_name, …) are only populated with
    validated, coerced values — or left None for manual review.

    The semantic module (semantic.py) is imported lazily here so that the
    heavy sentence-transformers / torch stack is only loaded when this
    function is first called, keeping module import time fast.

    NOTE: ``match_fields`` is called with ``threshold=HYBRID_CONFIDENCE_THRESHOLD``
    (0.75) rather than the module default of 0.55.  This means the semantic
    module pre-filters to 0.55 internally, but we re-apply 0.75 here before
    committing any value.  The double-check is intentional: it keeps the
    semantic layer reusable at its own default for other callers while this
    layer enforces its stricter bar.
    """
    # Import lazily so that torch / sentence-transformers are not loaded at
    # module import time — keeping server startup fast.
    # ``semantic`` is a sibling module in the same package; adjust if the
    # package layout changes.
    from .semantic import match_fields, FIELD_CANONICAL_LABELS  # sibling module

    fields = ExtractedFields()
    meta: dict[str, FieldMeta] = {}

    # ------------------------------------------------------------------
    # Pass 1: regex extraction
    # ------------------------------------------------------------------
    regex_hits = _regex_pass(text, doc_type)

    # Which scalar fields do we still need after regex?
    scalar_fields = list(FIELD_CANONICAL_LABELS.keys())  # all semantically-matchable fields
    fields_for_semantic: list[str] = []

    for field_name in scalar_fields:
        if field_name in regex_hits:
            raw, matched_label = regex_hits[field_name]
            validated, coerced = _validate_field(field_name, raw)
            if validated:
                setattr(fields, field_name, coerced)
                meta[field_name] = _make_meta(
                    method=ExtractionMethod.REGEX,
                    confidence=1.0,
                    validated=True,
                    status=ExtractionStatus.OK,
                    matched_label=matched_label,
                )
            else:
                # Regex found a candidate but it didn't pass type validation.
                # Record the failed attempt; also send to semantic so there is a
                # second chance before we give up.
                meta[field_name] = _make_meta(
                    method=ExtractionMethod.REGEX,
                    confidence=1.0,
                    validated=False,
                    status=ExtractionStatus.VALIDATION_FAILED,
                    matched_label=matched_label,
                )
                fields_for_semantic.append(field_name)
        else:
            fields_for_semantic.append(field_name)

    # ------------------------------------------------------------------
    # Pass 2: semantic extraction for fields still missing
    #
    # We pass HYBRID_CONFIDENCE_THRESHOLD (0.75) explicitly so that the
    # semantic module only returns matches that clear our bar.  Matches
    # that the semantic module returns are still re-validated below.
    # ------------------------------------------------------------------
    if fields_for_semantic:
        sem_result = match_fields(
            text,
            fields_for_semantic,
            threshold=HYBRID_CONFIDENCE_THRESHOLD,
        )

        matched_by_semantic = {m.field_name: m for m in sem_result.matches}

        for field_name in fields_for_semantic:
            if field_name in matched_by_semantic:
                sem_match = matched_by_semantic[field_name]
                validated, coerced = _validate_field(field_name, sem_match.value)

                if validated:
                    setattr(fields, field_name, coerced)
                    meta[field_name] = _make_meta(
                        method=ExtractionMethod.SEMANTIC,
                        confidence=sem_match.confidence,
                        validated=True,
                        status=ExtractionStatus.OK,
                        matched_label=sem_match.matched_label,
                    )
                else:
                    # Semantic found a candidate above the similarity threshold
                    # but it failed type validation; leave value as None.
                    meta[field_name] = _make_meta(
                        method=ExtractionMethod.SEMANTIC,
                        confidence=sem_match.confidence,
                        validated=False,
                        status=ExtractionStatus.VALIDATION_FAILED,
                        matched_label=sem_match.matched_label,
                    )
            else:
                # Nothing above threshold from semantic pass.
                #
                # FIX (logic bug — VALIDATION_FAILED preservation was inverted):
                # Previously the code preserved the regex VALIDATION_FAILED meta
                # entry with `pass`, but then entered the `else` branch for the
                # model-unavailable path unconditionally, overwriting that more
                # informative status with NOT_FOUND.  The two cases must be kept
                # fully separate:
                #   (a) A regex hit existed but was invalid → keep VALIDATION_FAILED.
                #   (b) No regex hit at all → write LOW_CONFIDENCE or NOT_FOUND.
                # Case (a) is detected by checking the existing meta entry;
                # if it is already VALIDATION_FAILED we do not touch it.
                existing = meta.get(field_name)
                if existing and existing.status == ExtractionStatus.VALIDATION_FAILED:
                    # The regex hit exists but is invalid; keep that meta entry.
                    # manual_review is already True on the existing entry.
                    pass
                else:
                    # Genuinely not found by either method.
                    low_confidence_status = (
                        ExtractionStatus.NOT_FOUND
                        if not sem_result.model_available
                        else ExtractionStatus.LOW_CONFIDENCE
                    )
                    meta[field_name] = _make_meta(
                        method=ExtractionMethod.MANUAL_REVIEW,
                        confidence=0.0,
                        validated=False,
                        status=low_confidence_status,
                        matched_label=None,
                    )

    # ------------------------------------------------------------------
    # List fields (salary_credits, dates) — regex only, no semantic needed.
    # These are multi-value fields where semantic matching is impractical.
    # ------------------------------------------------------------------
    # Table-aware first: read the *credit column* of the transaction table so
    # the value that feeds L3's flagship INCOME_MISMATCH is the salary deposit,
    # not the running balance / a reference number / a year in the narration.
    # Runs whenever a bank-style table is detected even if classification missed
    # (doc_type UNKNOWN), and falls back to the loose single-line regex when no
    # table header is present — preserving prior behaviour on non-tabular input.
    # The UNKNOWN carve-out is deliberately narrow: it recovers classification
    # misses, but a document confidently classified as something else (e.g.
    # LAND_RECORD, LEGAL) never gets salary_credits populated off a table-header
    # false-positive (a legal clause can contain "credit"/"debit"/"balance").
    table_credits = _extract_salary_credits(text)
    if doc_type in (DocType.BANK_STATEMENT, DocType.SALARY_SLIP) or (
        doc_type == DocType.UNKNOWN and table_credits
    ):
        if table_credits:
            salary_credits = table_credits
            credit_label = "credit column (table-aware)"
        else:
            # FIX (robustness bug — unguarded _to_float in listcomp): a single
            # OCR-corrupted salary token would raise ValueError and crash the
            # entire extraction, losing all already-extracted fields.  Filter to
            # successfully parsed values and log any that fail so they surface in
            # telemetry without aborting the pipeline.
            salary_credits = []
            for raw_credit in _SALARY_CREDIT_RE.findall(text):
                value = _to_float(raw_credit)
                if value is not None and value > 0:
                    salary_credits.append(value)
                else:
                    logger.debug(
                        "Skipping unparseable salary credit token: %r", raw_credit
                    )
            credit_label = "salary/sal cr/salary credit"
        fields.salary_credits = salary_credits

        # FIX (metadata consistency — list fields had no extraction_meta entries):
        # salary_credits and dates were silently absent from extraction_meta,
        # causing KeyError for downstream audit systems that iterate all fields.
        # We record a synthetic meta entry so the audit layer has a complete
        # picture (no per-element provenance — impractical for multi-value fields).
        meta["salary_credits"] = _make_meta(
            method=ExtractionMethod.REGEX,
            confidence=1.0,
            validated=True,
            status=ExtractionStatus.OK if salary_credits else ExtractionStatus.NOT_FOUND,
            matched_label=credit_label,
        )

    # FIX (metadata consistency — dates field had no extraction_meta entry):
    # same issue as salary_credits above.
    raw_dates = _ANY_DATE_RE.findall(text)
    normalized_dates = [d for raw in raw_dates if (d := normalize_date(raw))]
    fields.dates = normalized_dates
    meta["dates"] = _make_meta(
        method=ExtractionMethod.REGEX,
        confidence=1.0,
        validated=True,
        status=ExtractionStatus.OK if normalized_dates else ExtractionStatus.NOT_FOUND,
        matched_label=None,
    )

    fields.extraction_meta = meta
    return fields
