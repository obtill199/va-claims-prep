#!/usr/bin/env python3
"""
find_evidence.py — targeted keyword search over ocr.py's output.

AF forms don't follow MHS Genesis's "Diagnosis:" structure, so
extract_conditions.py's regex parser has nothing to match here even on
clean OCR text — this is Milestone 4's reconciliation problem, not a
structured-extraction one. In the meantime, this does the narrower, safer
thing: report which page(s) mention a given set of keywords and at what
OCR confidence, so a human knows where to look rather than trusting a
guess at content on a low-confidence (often handwritten) page.

Usage:
    python find_evidence.py ocr_output.json "duty limiting" "AF Form 469" "profile"
"""

import argparse
import json


def search(ocr_results, keywords):
    keywords_lower = [k.lower() for k in keywords]
    hits = []
    for page in ocr_results:
        text_lower = page["text"].lower()
        matched = [k for k, kl in zip(keywords, keywords_lower) if kl in text_lower]
        if matched:
            hits.append({
                "page": page["page"],
                "confidence": page["confidence"],
                "n_observations": page["n_observations"],
                "matched_keywords": matched,
            })
    return hits


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("ocr_json")
    ap.add_argument("keywords", nargs="+")
    args = ap.parse_args()

    with open(args.ocr_json, encoding="utf-8") as fh:
        results = json.load(fh)

    hits = search(results, args.keywords)
    print(f"{len(hits)} page(s) match at least one keyword:")
    for h in hits:
        print(f"  page {h['page']} [{h['confidence']} confidence, "
              f"{h['n_observations']} obs]: {h['matched_keywords']}")

    unreadable = [r["page"] for r in results if r["confidence"] == "low"]
    print(f"\n{len(unreadable)} page(s) low-confidence/likely unreadable "
          f"(handwriting, blank, or image-only) -- not searched reliably: {unreadable}")


if __name__ == "__main__":
    main()
