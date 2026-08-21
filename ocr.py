#!/usr/bin/env python3
"""
ocr.py — Milestone 3: OCR tier for files with no usable text layer.

Targets the scanned AF-forms/STR class of document (BUILD_BRIEF.md section
3.1) — poor/absent text layer, printed form labels mixed with handwritten
or typed fill-in content. Uses macOS's built-in Vision framework (via
pyobjc) rather than tesseract, since tesseract needs Homebrew and this
machine doesn't have it — Vision needs nothing beyond the pip packages
already installed in this venv.

Per BUILD_BRIEF.md section 4, decision 3: extraction confidence is always
visible, and a low-confidence extraction is never presented as fact. OCR
output here is tagged per page:
  - "medium": Vision's average per-page confidence is reasonably high —
    plausibly usable, but still OCR, never "high" (structured-text only).
  - "low": average confidence is weak, OR too few text observations to be
    a real printed page (blank, mostly-image, or mostly-handwritten) —
    surfaced as a page number needing human review, not guessed at.

Usage:
    python ocr.py record.pdf -o ocr_output.json [--dpi 300] [--pages 1-20]
"""

import argparse
import io
import json

import fitz  # pymupdf
import Quartz
import Vision
from Foundation import NSData

# Below this average per-observation confidence, or below this many
# observations, a page is flagged "low" rather than "medium" — see module
# docstring. Picked from eyeballing the real file: printed cover/typed
# pages cluster well above 0.7 avg with 30+ observations; pages that are
# mostly a signature, a stamp, or handwritten fill-in text drop off sharply
# in both dimensions.
MIN_AVG_CONFIDENCE = 0.55
MIN_OBSERVATIONS = 5


def rasterize(page, dpi=300):
    zoom = dpi / 72
    pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom))
    png_bytes = pix.tobytes("png")
    ns_data = NSData.dataWithBytes_length_(png_bytes, len(png_bytes))
    src = Quartz.CGImageSourceCreateWithData(ns_data, None)
    return Quartz.CGImageSourceCreateImageAtIndex(src, 0, None)


def ocr_image(cg_image):
    req = Vision.VNRecognizeTextRequest.alloc().initWithCompletionHandler_(None)
    req.setRecognitionLevel_(Vision.VNRequestTextRecognitionLevelAccurate)
    req.setUsesLanguageCorrection_(True)

    handler = Vision.VNImageRequestHandler.alloc().initWithCGImage_options_(cg_image, None)
    success, error = handler.performRequests_error_([req], None)
    if not success:
        return [], str(error)

    observations = req.results() or []
    lines = []
    for obs in observations:
        candidate = obs.topCandidates_(1)
        if not candidate:
            continue
        lines.append({
            "text": candidate[0].string(),
            "confidence": float(obs.confidence()),
        })
    return lines, None


def classify(lines):
    if len(lines) < MIN_OBSERVATIONS:
        return "low"
    avg_conf = sum(l["confidence"] for l in lines) / len(lines)
    return "medium" if avg_conf >= MIN_AVG_CONFIDENCE else "low"


def ocr_pdf(pdf_path, dpi=300, page_range=None):
    doc = fitz.open(pdf_path)
    if doc.needs_pass and not doc.authenticate(""):
        raise ValueError(f"{pdf_path}: encrypted with a non-empty password")

    indices = range(doc.page_count) if page_range is None else page_range
    results = []
    for i in indices:
        cg_image = rasterize(doc[i], dpi=dpi)
        lines, error = ocr_image(cg_image)
        confidence = classify(lines) if not error else "low"
        text = "\n".join(l["text"] for l in lines)
        avg_conf = (sum(l["confidence"] for l in lines) / len(lines)) if lines else 0.0
        results.append({
            "page": i + 1,
            "confidence": confidence,
            "n_observations": len(lines),
            "avg_observation_confidence": round(avg_conf, 3),
            "text": text,
            "error": error,
        })
        print(f"  page {i + 1}/{doc.page_count}: {confidence} "
              f"({len(lines)} obs, avg conf {avg_conf:.2f})")
    return results


def _parse_page_range(spec):
    if not spec:
        return None
    start, end = spec.split("-")
    return range(int(start) - 1, int(end))  # 1-indexed CLI -> 0-indexed


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pdf")
    ap.add_argument("-o", "--output", default="ocr_output.json")
    ap.add_argument("--dpi", type=int, default=300)
    ap.add_argument("--pages", help="1-indexed inclusive range, e.g. 1-20")
    args = ap.parse_args()

    results = ocr_pdf(args.pdf, dpi=args.dpi, page_range=_parse_page_range(args.pages))

    with open(args.output, "w") as fh:
        json.dump(results, fh, indent=2)

    low = [r["page"] for r in results if r["confidence"] == "low"]
    medium = [r["page"] for r in results if r["confidence"] == "medium"]
    print(f"\n{len(results)} pages OCR'd -> {args.output}")
    print(f"  medium confidence: {len(medium)} pages")
    print(f"  low confidence / likely unreadable: {len(low)} pages: {low}")


if __name__ == "__main__":
    main()
