#!/usr/bin/env python3
# Copyright (c) 2026 Oliver Tillinghast.
# Licensed under the PolyForm Noncommercial License 1.0.0.
# Free for veterans, VSOs, nonprofits and government. Commercial use
# requires a separate licence -- see LICENSE, NOTICE.md, COMMERCIAL.md.
"""
tools/batch_test.py — run a folder of record PDFs through the pipeline.

Reports what each file yields, so format differences show up as numbers
rather than as a silent zero. Prints structure and counts, not record
content.

    python tools/batch_test.py <folder>
"""

import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)

import extract_conditions  # noqa: E402
from pdf_io import extract_text_with_page_offsets  # noqa: E402


def probe(path):
    name = os.path.basename(path)
    try:
        text, page_starts = extract_text_with_page_offsets(path)
    except Exception as exc:
        return {"name": name, "error": f"{type(exc).__name__}"}

    diagnoses = list(extract_conditions.parse_diagnoses(text, page_starts, name))
    problems = list(extract_conditions.parse_problems(text))
    records = extract_conditions.aggregate(diagnoses, problems)
    clinical = [r for r in records if not r["administrative"]]

    # Which anchors the parser depends on are actually present?
    anchors = {a: text.count(a) for a in
               ("Diagnosis:", "Diagnosis Date:", "Problem Name:",
                "Life Cycle Status:", "Code:", "Responsible Provider:")}

    return {"name": name, "pages": len(page_starts), "chars": len(text),
            "diagnoses": len(diagnoses), "problems": len(problems),
            "clinical": len(clinical), "anchors": anchors,
            "conditions": [(c["icd10"], c["condition"]) for c in clinical]}


def main():
    folder = sys.argv[1]
    paths = sorted(os.path.join(folder, f) for f in os.listdir(folder)
                   if f.lower().endswith(".pdf"))
    results = [probe(p) for p in paths]

    print(f"{'file':<46}{'pp':>4}{'chars':>8}{'diag':>6}{'prob':>6}{'cond':>6}")
    print("-" * 76)
    for r in results:
        if "error" in r:
            print(f"{r['name'][:45]:<46}{'ERROR: ' + r['error']:>30}")
            continue
        print(f"{r['name'][:45]:<46}{r['pages']:>4}{r['chars']:>8}"
              f"{r['diagnoses']:>6}{r['problems']:>6}{r['clinical']:>6}")

    print("\nparser anchors present in each file:")
    for r in results:
        if "error" in r:
            continue
        present = {k: v for k, v in r["anchors"].items() if v}
        print(f"  {r['name'][:45]:<46} {present if present else 'NONE'}")

    print("\nconditions extracted:")
    for r in results:
        if "error" in r:
            continue
        print(f"  {r['name'][:45]}")
        if not r["conditions"]:
            print("      (none)")
        for icd, cond in r["conditions"]:
            print(f"      {icd or '—':<10} {cond}")


if __name__ == "__main__":
    main()
