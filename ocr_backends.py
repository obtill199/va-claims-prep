#!/usr/bin/env python3
# Copyright (c) 2026 Oliver Tillinghast.
# Licensed under the PolyForm Noncommercial License 1.0.0.
# Free for veterans, VSOs, nonprofits and government. Commercial use
# requires a separate licence -- see LICENSE, NOTICE.md, COMMERCIAL.md.
"""
ocr_backends.py — platform OCR engines behind one interface.

The OCR tier was written against macOS's Vision framework, which made
scanned records — duty-limiting profiles, AF Form 469s, handwritten notes —
readable on a Mac and invisible everywhere else. Everything else in the tool
is already cross-platform: verified by running the whole flow with the pyobjc
frameworks blocked, which passes.

Each backend takes PNG bytes and returns (lines, error), where lines is
[{"text": str, "confidence": float|None}].

  macOS    Vision framework via pyobjc. Ships with the OS. Reports a
           per-observation confidence.
  Windows  Windows.Media.Ocr via the winsdk package. Ships with Windows 10+,
           so a user installs nothing beyond a pip package. NOTE: this API
           exposes no confidence score, so confidence is None and the caller
           falls back to judging a page by how much text came off it.
  Any      Tesseract via pytesseract, if the user has installed it. Reports
           confidence. Last resort because it needs a system install that
           non-technical users struggle with.

STATUS: the macOS backend is verified against real 106-page scans. The
Windows and Tesseract backends are written against their documented APIs but
have not been run on those platforms — see tests/test_ocr_backends.py, which
pins the contract they must satisfy.
"""

import platform


class _Unavailable(Exception):
    pass


# --------------------------------------------------------------- macOS

def _macos_available():
    if platform.system() != "Darwin":
        return False
    try:
        import Vision  # noqa: F401
        return True
    except ImportError:
        return False


def _macos_recognize(png_bytes):
    import Quartz
    import Vision
    from Foundation import NSData

    data = NSData.dataWithBytes_length_(png_bytes, len(png_bytes))
    source = Quartz.CGImageSourceCreateWithData(data, None)
    if source is None:
        return [], "could not decode image"
    image = Quartz.CGImageSourceCreateImageAtIndex(source, 0, None)

    request = Vision.VNRecognizeTextRequest.alloc().initWithCompletionHandler_(None)
    request.setRecognitionLevel_(Vision.VNRequestTextRecognitionLevelAccurate)
    request.setUsesLanguageCorrection_(True)

    handler = Vision.VNImageRequestHandler.alloc().initWithCGImage_options_(image, None)
    ok, error = handler.performRequests_error_([request], None)
    if not ok:
        return [], str(error)

    lines = []
    for observation in (request.results() or []):
        candidates = observation.topCandidates_(1)
        if candidates:
            lines.append({"text": candidates[0].string(),
                          "confidence": float(observation.confidence())})
    return lines, None


# ------------------------------------------------------------- Windows

def _windows_available():
    if platform.system() != "Windows":
        return False
    try:
        import winsdk.windows.media.ocr  # noqa: F401
        return True
    except ImportError:
        return False


def _windows_recognize(png_bytes):
    """Windows.Media.Ocr. Async API, driven synchronously here.

    The engine returns lines and words but no confidence value of any kind,
    so every line is reported with confidence None. classify() in ocr.py
    handles that by judging the page on how much text was recovered instead
    of on an average score.
    """
    import asyncio

    from winsdk.windows.globalization import Language
    from winsdk.windows.graphics.imaging import BitmapDecoder
    from winsdk.windows.media.ocr import OcrEngine
    from winsdk.windows.storage.streams import DataWriter, InMemoryRandomAccessStream

    async def run():
        stream = InMemoryRandomAccessStream()
        writer = DataWriter(stream.get_output_stream_at(0))
        writer.write_bytes(png_bytes)
        await writer.store_async()
        await writer.flush_async()
        stream.seek(0)

        decoder = await BitmapDecoder.create_async(stream)
        bitmap = await decoder.get_software_bitmap_async()

        engine = OcrEngine.try_create_from_user_profile_languages()
        if engine is None:
            engine = OcrEngine.try_create_from_language(Language("en-US"))
        if engine is None:
            raise _Unavailable(
                "Windows OCR has no language pack installed. Add one under "
                "Settings > Time & Language > Language & region.")

        result = await engine.recognize_async(bitmap)
        return [{"text": line.text, "confidence": None} for line in result.lines]

    try:
        return asyncio.run(run()), None
    except _Unavailable as exc:
        return [], str(exc)
    except Exception as exc:
        return [], f"{type(exc).__name__}: {exc}"


# ----------------------------------------------------------- Tesseract

def _tesseract_available():
    try:
        import pytesseract
        pytesseract.get_tesseract_version()
        return True
    except Exception:
        return False


def _tesseract_recognize(png_bytes):
    import io

    import pytesseract
    from PIL import Image

    try:
        image = Image.open(io.BytesIO(png_bytes))
        data = pytesseract.image_to_data(
            image, output_type=pytesseract.Output.DICT)
    except Exception as exc:
        return [], f"{type(exc).__name__}: {exc}"

    lines = []
    for raw_text, conf in zip(data.get("text", []), data.get("conf", []),
                              strict=False):   # tesseract pads unevenly
        text = (raw_text or "").strip()
        if not text:
            continue
        try:
            confidence = float(conf) / 100.0
        except (TypeError, ValueError):
            confidence = None
        lines.append({"text": text,
                      "confidence": confidence if confidence and confidence >= 0 else None})
    return lines, None


# -------------------------------------------------------------- registry

BACKENDS = [
    ("macos-vision", _macos_available, _macos_recognize,
     "macOS Vision framework"),
    ("windows-ocr", _windows_available, _windows_recognize,
     "Windows.Media.Ocr"),
    ("tesseract", _tesseract_available, _tesseract_recognize,
     "Tesseract"),
]


def select():
    """(name, recognize_fn, description) for the first usable backend."""
    for name, available, recognize, description in BACKENDS:
        try:
            if available():
                return name, recognize, description
        except Exception:   # noqa: S112 - one unreadable line must not
            continue        # discard an otherwise good page of OCR
    return None, None, None


def unavailable_reason():
    """Why OCR can't run here, phrased for the person reading it."""
    system = platform.system()
    if system == "Darwin":
        return ("OCR needs the pyobjc Vision bindings. Run ./setup.sh again, "
                "or: pip install pyobjc-framework-Vision pyobjc-framework-Quartz")
    if system == "Windows":
        return ("OCR needs the winsdk package, which uses the OCR engine "
                "built into Windows 10 and 11. Run: pip install winsdk")
    return ("OCR on this platform needs Tesseract installed, plus: "
            "pip install pytesseract pillow")


def describe():
    """Short status line for the UI and for start-up output."""
    name, _, description = select()
    if name:
        return True, f"OCR available via {description}"
    return False, unavailable_reason()
