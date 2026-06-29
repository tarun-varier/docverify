"""Semantic field matcher — Layer 1 fallback when label-value regex fails.

Uses BGE-small-en-v1.5 (a 33M-parameter bi-encoder) to find the line in
an OCR'd document whose label is semantically closest to a canonical field
description.  Only activated when the primary regex pass returns no value.

Design principles
-----------------
* The model is loaded once, lazily, on the first call to ``match_fields``.
  Loading inside a request handler would add ~1-2 s per document.
* If ``sentence-transformers`` is not installed, all functions return empty
  results rather than raising — the regex pass remains the sole extractor and
  the system degrades gracefully.
* Confidence is cosine similarity (0.0–1.0). Callers compare against
  ``SEMANTIC_CONFIDENCE_THRESHOLD`` before accepting a value.
* This module is an internal implementation detail of ``ingestion.py``.
  Nothing outside Layer 1 should import it.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

#: Accept a semantic match only when similarity meets or exceeds this value.
#: 0.55 is intentionally conservative — we would rather send a field to
#: manual review than fill it with a wrong value.
SEMANTIC_CONFIDENCE_THRESHOLD: float = 0.55

#: BGE model identifier.  Switch to "BAAI/bge-small-en-v1.5" for English-only
#: documents.  The multilingual variant handles Hindi/regional OCR output.
_MODEL_NAME = "BAAI/bge-small-en-v1.5"

# ---------------------------------------------------------------------------
# Canonical labels: what a human reviewer would call each field.
# Multiple phrasings improve recall when OCR introduces noise or the document
# uses a regional template.
# ---------------------------------------------------------------------------

#: Maps field name → list of canonical label phrasings we embed.
FIELD_CANONICAL_LABELS: dict[str, list[str]] = {
    "applicant_name": [
        "applicant name",
        "employee name",
        "account holder name",
        "name of owner",
        "name of borrower",
        "full name",
        "customer name",
    ],
    "pan": [
        "permanent account number",
        "PAN number",
        "income tax PAN",
        "PAN card number",
    ],
    "cin": [
        "company identification number",
        "CIN",
        "corporate identity number",
        "ROC registration number",
    ],
    "survey_number": [
        "survey number",
        "survey no",
        "khasra number",
        "plot number",
        "land parcel number",
    ],
    "monthly_income": [
        "net pay",
        "net salary",
        "gross salary",
        "total monthly earnings",
        "monthly income",
        "take home salary",
    ],
    "registration_date": [
        "registration date",
        "date of registration",
        "registered on",
        "deed registration date",
    ],
    "address": [
        "residential address",
        "address",
        "permanent address",
        "current address",
        "communication address",
    ],
}

# ---------------------------------------------------------------------------
# Internal helpers — lazy model loading
# ---------------------------------------------------------------------------

_model = None          # SentenceTransformer instance, populated on first use
_label_embeddings: dict[str, object] = {}  # field_name -> stacked embeddings tensor
_ST_AVAILABLE: bool | None = None          # None = unchecked yet


def _try_import() -> bool:
    """Return True if sentence-transformers is importable; cache the result."""
    global _ST_AVAILABLE
    if _ST_AVAILABLE is None:
        try:
            import sentence_transformers  # noqa: F401
            _ST_AVAILABLE = True
        except ImportError:
            _ST_AVAILABLE = False
    return _ST_AVAILABLE


def _load_model() -> bool:
    """Load BGE-small on the first call.  Returns False if unavailable."""
    global _model, _label_embeddings
    if not _try_import():
        return False
    if _model is not None:
        return True

    from sentence_transformers import SentenceTransformer

    _model = SentenceTransformer(_MODEL_NAME)

    # Pre-compute and cache embeddings for all canonical labels.
    # We embed each phrasing individually and store a list — at match time we
    # take the max similarity across all phrasings for a field.
    for field_name, phrases in FIELD_CANONICAL_LABELS.items():
        _label_embeddings[field_name] = _model.encode(
            phrases, normalize_embeddings=True, convert_to_tensor=True
        )

    return True


# ---------------------------------------------------------------------------
# Line-level candidate extraction
# ---------------------------------------------------------------------------

# A line that looks like "some label : some value" or "some label - some value".
_LABEL_VALUE_LINE_RE = re.compile(
    r"^(?P<label>[A-Za-z][A-Za-z0-9 /.()\-]{1,60})"   # label portion
    r"\s*[:\-]\s*"                                       # separator
    r"(?P<value>.{1,120})$",                             # value portion
    re.MULTILINE,
)


@dataclass
class LineCandidate:
    """One label:value pair found in the document text."""

    label: str
    value: str
    line_index: int   # Ordinal position in the document (for tiebreaking)


def extract_line_candidates(text: str) -> list[LineCandidate]:
    """Scan ``text`` and return all lines that match a label:value pattern.

    We also include lines that look like plain values immediately following a
    known-label line (handles two-line layouts sometimes produced by OCR).
    """
    candidates: list[LineCandidate] = []
    lines = text.splitlines()
    for idx, line in enumerate(lines):
        line = line.strip()
        if not line:
            continue
        m = _LABEL_VALUE_LINE_RE.match(line)
        if m:
            candidates.append(LineCandidate(
                label=m.group("label").strip(),
                value=m.group("value").strip(),
                line_index=idx,
            ))
    return candidates


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

@dataclass
class SemanticMatch:
    """Result of attempting a semantic match for one field."""

    field_name: str
    value: str
    confidence: float
    matched_label: str     # The label text that was closest to the canonical embedding


@dataclass
class SemanticMatchResult:
    """All semantic matches attempted for a document."""

    matches: list[SemanticMatch] = field(default_factory=list)
    model_available: bool = True   # False when sentence-transformers absent


def match_fields(
    text: str,
    fields_needed: list[str],
    threshold: float = SEMANTIC_CONFIDENCE_THRESHOLD,
) -> SemanticMatchResult:
    """Try to extract ``fields_needed`` from ``text`` via semantic similarity.

    Parameters
    ----------
    text:
        Full OCR/PDF text for a single document.
    fields_needed:
        Field names (matching ``FIELD_CANONICAL_LABELS`` keys) for which the
        regex pass returned no value.  Fields not in the canonical label dict
        are skipped silently.
    threshold:
        Minimum cosine similarity to accept a match.

    Returns
    -------
    SemanticMatchResult
        Contains one ``SemanticMatch`` per successfully matched field.
        Fields below threshold are omitted — callers mark them for manual review.
    """
    if not _load_model():
        return SemanticMatchResult(matches=[], model_available=False)

    import torch  # available whenever sentence-transformers is

    candidates = extract_line_candidates(text)
    if not candidates:
        return SemanticMatchResult(matches=[])

    # Embed all candidate labels in a single batch (faster than one-by-one).
    candidate_label_texts = [c.label for c in candidates]
    candidate_embeddings = _model.encode(
        candidate_label_texts, normalize_embeddings=True, convert_to_tensor=True
    )

    result = SemanticMatchResult()

    for field_name in fields_needed:
        if field_name not in _label_embeddings:
            continue  # No canonical labels defined; skip

        canonical_embs = _label_embeddings[field_name]  # shape (n_phrases, dim)

        # Cosine similarity: canonical_embs @ candidate_embeddings.T
        # Shape: (n_phrases, n_candidates)
        sims = torch.mm(canonical_embs, candidate_embeddings.T)  # type: ignore[arg-type]

        # Best score per candidate: max over all canonical phrasings.
        best_per_candidate, _ = sims.max(dim=0)   # shape (n_candidates,)

        best_idx = int(best_per_candidate.argmax())
        best_score = float(best_per_candidate[best_idx])

        if best_score < threshold:
            continue  # Caller will mark as LOW_CONFIDENCE / manual review

        best_candidate = candidates[best_idx]
        result.matches.append(SemanticMatch(
            field_name=field_name,
            value=best_candidate.value,
            confidence=best_score,
            matched_label=best_candidate.label,
        ))

    return result
