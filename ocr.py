#!/usr/bin/env python3
"""
ocr.py — Milestone 3: OCR tier for files with no usable text layer.

Targets the scanned AF-forms/STR class of document — poor or absent text
layer, printed form labels mixed with handwritten or typed fill-in content.

The engine is chosen at run time by ocr_backends.select(): macOS Vision,
Windows.Media.Ocr, or Tesseract. Each ships with its platform (Tesseract
excepted), so a user installs nothing beyond a pip package.

Per BUILD_BRIEF.md section 4, decision 3: extraction confidence is always
visible, and a low-confidence extraction is never presented as fact. OCR
output here is tagged per page:
  - "medium": the backend's average per-page confidence is reasonably high —
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

import ocr_backends

# Below this average per-observation confidence, or below this many
# observations, a page is flagged "low" rather than "medium" — see module
# docstring. Picked from eyeballing the real file: printed cover/typed
# pages cluster well above 0.7 avg with 30+ observations; pages that are
# mostly a signature, a stamp, or handwritten fill-in text drop off sharply
# in both dimensions.
MIN_AVG_CONFIDENCE = 0.55
MIN_OBSERVATIONS = 5


def rasterize(page, dpi=300):
    """Page -> PNG bytes. Backend-agnostic: each OCR engine decodes the PNG
    itself, so this no longer depends on a macOS image type."""
    zoom = dpi / 72
    pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom))
    return pix.tobytes("png")


def ocr_image(png_bytes, recognize=None):
    """Recognise text in a rasterised page using whichever backend exists."""
    if recognize is None:
        _, recognize, _ = ocr_backends.select()
    if recognize is None:
        return [], ocr_backends.unavailable_reason()
    return recognize(png_bytes)


def classify(lines):
    """Rate a page's extraction as medium or low.

    Windows.Media.Ocr reports no confidence value, so a page there is judged
    purely on how much text came off it. Never returns "high": that tier is
    reserved for structured text, and OCR output must not be presented as
    equivalent (BUILD_BRIEF decision 3).
    """
    if len(lines) < MIN_OBSERVATIONS:
        return "low"

    scored = [l["confidence"] for l in lines if l.get("confidence") is not None]
    if not scored:
        # No confidence available. A page with a healthy amount of recognised
        # text is plausible; a nearly empty one is not.
        return "medium" if len(lines) >= MIN_OBSERVATIONS * 3 else "low"

    return "medium" if sum(scored) / len(scored) >= MIN_AVG_CONFIDENCE else "low"


def ocr_pdf(pdf_path, dpi=300, page_range=None):
    doc = fitz.open(pdf_path)
    if doc.needs_pass and not doc.authenticate(""):
        raise ValueError(f"{pdf_path}: encrypted with a non-empty password")

    _, recognize, description = ocr_backends.select()
    if recognize is None:
        raise RuntimeError(ocr_backends.unavailable_reason())

    indices = range(doc.page_count) if page_range is None else page_range
    results = []
    for i in indices:
        png = rasterize(doc[i], dpi=dpi)
        lines, error = ocr_image(png, recognize)
        confidence = classify(lines) if not error else "low"
        text = "\n".join(l["text"] for l in lines)
        scored = [l["confidence"] for l in lines if l.get("confidence") is not None]
        avg_conf = (sum(scored) / len(scored)) if scored else 0.0
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

    with open(args.output, "w", encoding="utf-8") as fh:
        json.dump(results, fh, indent=2)

    low = [r["page"] for r in results if r["confidence"] == "low"]
    medium = [r["page"] for r in results if r["confidence"] == "medium"]
    print(f"\n{len(results)} pages OCR'd -> {args.output}")
    print(f"  medium confidence: {len(medium)} pages")
    print(f"  low confidence / likely unreadable: {len(low)} pages: {low}")


if __name__ == "__main__":
    main()
