"""Layer 1 — OCR preprocessing (deskew/denoise/binarize).

Run:  PYTHONPATH=model python -m pytest model/tests/test_ocr_preprocessing.py -q
Needs numpy + pillow always; the cv2-dependent tests skip cleanly if cv2
isn't importable, and the end-to-end test additionally skips if the
Tesseract binary isn't on PATH.
"""

from __future__ import annotations

import io

import numpy as np
import pytest
from PIL import Image, ImageDraw

from pipeline import ingestion

try:
    import cv2
    CV2_INSTALLED = True
except ImportError:
    CV2_INSTALLED = False

needs_cv2 = pytest.mark.skipif(not CV2_INSTALLED, reason="cv2 not installed")


def _measure_skew_angle(arr: np.ndarray) -> float:
    """Same Otsu+minAreaRect angle estimate _preprocess_for_ocr uses
    internally, applied here as an independent post-hoc check."""
    _, mask = cv2.threshold(arr, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    coords = cv2.findNonZero(mask)
    if coords is None:
        return 0.0
    rect_angle = cv2.minAreaRect(coords)[-1]
    return -(90 + rect_angle) if rect_angle < -45 else -rect_angle


def _skewed_noisy_text_image(angle_deg: float = 8.0) -> Image.Image:
    img = Image.new("L", (400, 200), color=255)
    draw = ImageDraw.Draw(img)
    draw.text((30, 80), "SALARY SLIP 250000", fill=0)
    img = img.rotate(angle_deg, fillcolor=255, expand=False)
    arr = np.asarray(img).copy()
    rng = np.random.default_rng(42)
    salt_pepper = rng.random(arr.shape)
    arr[salt_pepper < 0.02] = 0
    arr[salt_pepper > 0.98] = 255
    return Image.fromarray(arr).convert("RGB")


# ---------------------------------------------------------------------------
# Preprocessing function in isolation — no Tesseract needed
# ---------------------------------------------------------------------------

@needs_cv2
def test_preprocess_binarizes_output():
    img = _skewed_noisy_text_image()
    out = ingestion._preprocess_for_ocr(img)
    arr = np.asarray(out)
    unique_values = set(np.unique(arr).tolist())
    # Binarized output should be (almost) entirely 0/255, modulo a handful of
    # pixels the morphological open step can leave at intermediate values
    # along edges.
    non_binary_fraction = np.mean(~np.isin(arr, [0, 255]))
    assert non_binary_fraction < 0.05, f"expected near-binary output, got {unique_values}"


@needs_cv2
def test_preprocess_deskews_output():
    img = _skewed_noisy_text_image(angle_deg=8.0)
    out = ingestion._preprocess_for_ocr(img)
    residual_angle = _measure_skew_angle(np.asarray(out))
    assert abs(residual_angle) < 2.0, f"expected near-zero residual skew, got {residual_angle}"


# ---------------------------------------------------------------------------
# End-to-end — needs both cv2 and a real Tesseract binary
# ---------------------------------------------------------------------------

@pytest.mark.skipif(
    not (CV2_INSTALLED and ingestion.TESSERACT_AVAILABLE),
    reason="needs both cv2 and the tesseract binary",
)
def test_preprocessing_improves_or_matches_raw_ocr(monkeypatch):
    import difflib

    expected = "SALARY SLIP 250000"
    img = _skewed_noisy_text_image()
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    png_bytes = buf.getvalue()

    preprocessed_text = ingestion.ocr_png(png_bytes)

    monkeypatch.setattr(ingestion, "_try_import_cv2", lambda: False)
    raw_text = ingestion.ocr_png(png_bytes)

    def score(text: str) -> float:
        return difflib.SequenceMatcher(None, text.lower(), expected.lower()).ratio()

    # Fuzzy match, not exact equality -- OCR isn't perfectly deterministic
    # across environments/Tesseract versions. The preprocessed path should
    # do at least as well as the raw path on a skewed+noisy input.
    assert score(preprocessed_text) >= score(raw_text)


# ---------------------------------------------------------------------------
# Graceful degrade
# ---------------------------------------------------------------------------

def test_ocr_png_works_without_cv2(monkeypatch):
    monkeypatch.setattr(ingestion, "_try_import_cv2", lambda: False)
    img = Image.new("RGB", (100, 50), color=255)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    # Should not raise regardless of whether Tesseract itself is installed.
    ingestion.ocr_png(buf.getvalue())


@needs_cv2
def test_ocr_png_survives_preprocessing_exception(monkeypatch):
    def _boom(img):
        raise RuntimeError("simulated preprocessing failure")

    monkeypatch.setattr(ingestion, "_preprocess_for_ocr", _boom)
    img = Image.new("RGB", (100, 50), color=255)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    # Falls back to raw-image OCR instead of propagating the exception.
    ingestion.ocr_png(buf.getvalue())
