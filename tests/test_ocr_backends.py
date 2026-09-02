# Copyright (c) 2026 Oliver Tillinghast.
# Licensed under the PolyForm Noncommercial License 1.0.0.
# Free for veterans, VSOs, nonprofits and government. Commercial use
# requires a separate licence -- see LICENSE, NOTICE.md, COMMERCIAL.md.
"""
The OCR backend contract.

OCR was macOS-only: Vision via pyobjc, imported at module level. Everything
else in the tool is already cross-platform — verified by running the whole
flow with the pyobjc frameworks blocked, which passes — so OCR was the single
thing standing between this and a Windows user.

Only the backend for the current platform can actually be exercised here.
These tests pin the contract every backend must satisfy, so the Windows and
Tesseract implementations can be checked against something concrete when
somebody runs them on real hardware.
"""

import os
import platform
import sys

import pytest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)

import ocr  # noqa: E402
import ocr_backends  # noqa: E402

# ------------------------------------------------------------- registry

def test_every_backend_declares_the_same_shape():
    for name, available, recognize, description in ocr_backends.BACKENDS:
        assert isinstance(name, str) and name
        assert callable(available)
        assert callable(recognize)
        assert isinstance(description, str) and description


def test_availability_checks_never_raise():
    """A probe for a backend that isn't installed must return False, not
    explode — otherwise importing on the wrong platform takes the app down."""
    for _, available, _, _ in ocr_backends.BACKENDS:
        assert available() in (True, False)


def test_select_returns_a_consistent_triple():
    name, recognize, description = ocr_backends.select()
    if name is None:
        assert recognize is None and description is None
    else:
        assert callable(recognize) and isinstance(description, str)


def test_describe_always_gives_an_actionable_reason():
    ok, message = ocr_backends.describe()
    assert isinstance(ok, bool)
    assert message and isinstance(message, str)
    if not ok:
        # A user who cannot run OCR must be told what to do about it.
        assert any(hint in message.lower()
                   for hint in ("pip install", "install", "setup"))


def test_unavailable_reason_is_platform_specific():
    reason = ocr_backends.unavailable_reason()
    assert reason
    system = platform.system()
    if system == "Windows":
        assert "winsdk" in reason
    elif system == "Darwin":
        assert "pyobjc" in reason


# ------------------------------------------------------ confidence tiers

def test_classify_handles_a_backend_with_no_confidence():
    """Windows.Media.Ocr reports no confidence at all. A page must still be
    rated, on how much text came off it."""
    sparse = [{"text": "x", "confidence": None} for _ in range(6)]
    dense = [{"text": "x", "confidence": None} for _ in range(40)]
    assert ocr.classify(sparse) == "low"
    assert ocr.classify(dense) == "medium"


def test_classify_never_returns_high():
    """BUILD_BRIEF decision 3: OCR output must never be presented with the
    same confidence as structured text."""
    perfect = [{"text": "x", "confidence": 1.0} for _ in range(200)]
    assert ocr.classify(perfect) == "medium"


def test_classify_rejects_a_nearly_empty_page():
    assert ocr.classify([]) == "low"
    assert ocr.classify([{"text": "x", "confidence": 0.99}]) == "low"


def test_classify_uses_confidence_when_the_backend_supplies_it():
    weak = [{"text": "x", "confidence": 0.2} for _ in range(30)]
    strong = [{"text": "x", "confidence": 0.9} for _ in range(30)]
    assert ocr.classify(weak) == "low"
    assert ocr.classify(strong) == "medium"


def test_mixed_confidence_ignores_the_unscored_lines():
    mixed = ([{"text": "x", "confidence": 0.9} for _ in range(10)]
             + [{"text": "x", "confidence": None} for _ in range(10)])
    assert ocr.classify(mixed) == "medium"


# ----------------------------------------------------- graceful absence

def test_ocr_image_reports_rather_than_raises_when_unavailable():
    lines, error = ocr.ocr_image(b"not-an-image", recognize=None) \
        if ocr_backends.select()[1] is None else ([], None)
    if error:
        assert isinstance(error, str) and error


def test_app_starts_without_any_ocr_backend(monkeypatch):
    """The whole point: no OCR must degrade, not crash."""
    monkeypatch.setattr(ocr_backends, "select", lambda: (None, None, None))
    sys.modules.pop("app.pipeline", None)
    from app import pipeline
    available, reason = pipeline.ocr_available()
    assert available is False
    assert reason


# ------------------------------------------------- live backend, if any

@pytest.mark.skipif(ocr_backends.select()[0] is None,
                    reason="no OCR backend available on this machine")
def test_live_backend_returns_the_declared_shape():
    """Whichever backend this machine has must honour the contract."""
    fitz = pytest.importorskip("fitz")
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 100), "DUTY LIMITING CONDITION REPORT", fontsize=18)
    png = ocr.rasterize(page, dpi=150)
    doc.close()

    lines, error = ocr.ocr_image(png)
    assert error is None, error
    assert lines, "a rendered line of text should produce observations"
    for line in lines:
        assert isinstance(line["text"], str)
        assert line["confidence"] is None or 0.0 <= line["confidence"] <= 1.0
    assert "DUTY" in " ".join(x["text"] for x in lines).upper()
