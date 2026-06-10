"""Layer 1 — Document ingestion, OCR and structured field extraction.

Accepts PDFs and images. PDFs with a text layer are read directly via
PyMuPDF; scanned pages and images fall back to Tesseract OCR when the
binary is available.
"""

from __future__ import annotations

import io
import re
import shutil
from datetime import datetime

import fitz  # PyMuPDF
from PIL import Image

from .models import DocType, ExtractedFields

TESSERACT_AVAILABLE = shutil.which("tesseract") is not None

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".tiff", ".bmp", ".webp"}

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
    r"(?:employee\s+name|applicant\s+name|account\s+holder|name\s+of\s+(?:owner|holder|employee)|owner\s+name|name)"
    r"\s*[:\-]\s*([A-Za-z][A-Za-z .]{2,40})",
    re.IGNORECASE,
)
_INCOME_RE = re.compile(
    r"(?:net\s+pay|net\s+salary|gross\s+salary|total\s+earnings|monthly\s+income)"
    r"\s*[:\-]?\s*(?:rs\.?|inr|₹)?\s*([0-9][0-9,]*(?:\.[0-9]{1,2})?)",
    re.IGNORECASE,
)
_SALARY_CREDIT_RE = re.compile(
    r"(?:salary|sal\s+cr|salary\s+credit)[^\n]*?([0-9][0-9,]{2,}(?:\.[0-9]{1,2})?)",
    re.IGNORECASE,
)
_REG_DATE_RE = re.compile(
    r"(?:registration\s+date|date\s+of\s+registration|registered\s+on)"
    r"\s*[:\-]?\s*([0-9]{1,2}[-/][0-9]{1,2}[-/][0-9]{4}|[0-9]{4}-[0-9]{2}-[0-9]{2})",
    re.IGNORECASE,
)
_ADDRESS_RE = re.compile(r"address\s*[:\-]\s*([^\n]{8,100})", re.IGNORECASE)
_ANY_DATE_RE = re.compile(r"\b([0-9]{1,2}[-/][0-9]{1,2}[-/][0-9]{4}|[0-9]{4}-[0-9]{2}-[0-9]{2})\b")


def _ocr_image(img: Image.Image) -> str:
    if not TESSERACT_AVAILABLE:
        return ""
    import pytesseract

    return pytesseract.image_to_string(img)


def extract_text(filename: str, payload: bytes) -> tuple[str, int, bool]:
    """Return (text, page_count, ocr_used) for a PDF or image payload."""
    lower = filename.lower()
    if any(lower.endswith(ext) for ext in IMAGE_EXTENSIONS):
        img = Image.open(io.BytesIO(payload)).convert("RGB")
        return _ocr_image(img), 1, True

    doc = fitz.open(stream=payload, filetype="pdf")
    try:
        parts: list[str] = []
        ocr_used = False
        for page in doc:
            text = page.get_text()
            if len(text.strip()) < 20 and TESSERACT_AVAILABLE:
                # Scanned page: rasterize and OCR it.
                pix = page.get_pixmap(dpi=200)
                img = Image.open(io.BytesIO(pix.tobytes("png")))
                text = _ocr_image(img)
                ocr_used = True
            parts.append(text)
        return "\n".join(parts), doc.page_count, ocr_used
    finally:
        doc.close()


def classify(text: str, filename: str = "") -> DocType:
    haystack = f"{filename.lower()} {text.lower()}"
    scores = {
        doc_type: sum(1 for kw in keywords if kw in haystack)
        for doc_type, keywords in _CLASSIFIER_KEYWORDS.items()
    }
    best = max(scores, key=lambda k: scores[k])
    return best if scores[best] > 0 else DocType.UNKNOWN


def _to_float(raw: str) -> float:
    return float(raw.replace(",", ""))


def normalize_date(raw: str) -> str | None:
    """Normalize the date formats we extract to ISO YYYY-MM-DD."""
    for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y"):
        try:
            return datetime.strptime(raw, fmt).date().isoformat()
        except ValueError:
            continue
    return None


def extract_fields(text: str, doc_type: DocType) -> ExtractedFields:
    fields = ExtractedFields()

    if m := _NAME_RE.search(text):
        fields.applicant_name = m.group(1).strip().rstrip(".")
    if m := _PAN_RE.search(text):
        fields.pan = m.group(1)
    if m := _CIN_RE.search(text):
        fields.cin = m.group(1)
    if m := _SURVEY_RE.search(text):
        fields.survey_number = m.group(1)
    if m := _ADDRESS_RE.search(text):
        fields.address = m.group(1).strip()
    if m := _REG_DATE_RE.search(text):
        fields.registration_date = normalize_date(m.group(1))

    if doc_type == DocType.SALARY_SLIP:
        amounts = [_to_float(m) for m in _INCOME_RE.findall(text)]
        if amounts:
            fields.monthly_income = max(amounts)
    if doc_type == DocType.BANK_STATEMENT:
        fields.salary_credits = [_to_float(m) for m in _SALARY_CREDIT_RE.findall(text)]

    fields.dates = [d for raw in _ANY_DATE_RE.findall(text) if (d := normalize_date(raw))]
    return fields
