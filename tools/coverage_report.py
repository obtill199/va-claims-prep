#!/usr/bin/env python3
"""
tools/coverage_report.py — how many extracted conditions reach a form question.

The number that matters for a stranger using this tool: of the conditions
found in their records, how many produce a proposal? The old hand-written
map answered that only for the codes one person happened to have.

    python tools/coverage_report.py <folder-of-pdfs>
"""

import json
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)

import coded_records  # noqa: E402
import condition_library as cl  # noqa: E402
import extract_conditions as ec  # noqa: E402
import field_map  # noqa: E402
from pdf_io import extract_text_with_page_offsets  # noqa: E402


def conditions_in(path):
    name = os.path.basename(path)
    text, page_starts = extract_text_with_page_offsets(path)

    # MHS Genesis first, then the generic coded-record pass.
    diagnoses = list(ec.parse_diagnoses(text, page_starts, name))
    problems = list(ec.parse_problems(text))
    if not diagnoses:
        if coded_records.looks_narrative(text):
            return None, "narrative — no ICD-10 codes present"
        diagnoses = coded_records.extract(text, page_starts, name)

    records = ec.aggregate(diagnoses, problems)
    return [r for r in records if not r["administrative"]], None


def main():
    folder = sys.argv[1]
    paths = sorted(os.path.join(folder, f) for f in os.listdir(folder)
                   if f.lower().endswith(".pdf"))

    old_codes = set(field_map.RULES)
    total_old = total_new = total_conditions = 0

    print(f"{'file':<46}{'cond':>6}{'old':>6}{'new':>6}")
    print("-" * 64)
    for path in paths:
        conditions, note = conditions_in(path)
        if conditions is None:
            print(f"{os.path.basename(path)[:45]:<46}{note:>18}")
            continue

        old_hits = sum(1 for c in conditions if c["icd10"] in old_codes)
        new_hits = sum(1 for c in conditions if cl.match(c["icd10"], "Male"))
        total_conditions += len(conditions)
        total_old += old_hits
        total_new += new_hits
        print(f"{os.path.basename(path)[:45]:<46}"
              f"{len(conditions):>6}{old_hits:>6}{new_hits:>6}")

    print("-" * 64)
    print(f"{'TOTAL':<46}{total_conditions:>6}{total_old:>6}{total_new:>6}")
    if total_conditions:
        print(f"\ncoverage: {total_old}/{total_conditions} "
              f"({total_old / total_conditions:.0%}) with the old exact-code map")
        print(f"          {total_new}/{total_conditions} "
              f"({total_new / total_conditions:.0%}) with the range library")

    unmatched = []
    for path in paths:
        conditions, note = conditions_in(path)
        if conditions is None:
            continue
        for c in conditions:
            if not cl.match(c["icd10"], "Male"):
                unmatched.append((c["icd10"], c["condition"][:44]))
    if unmatched:
        print(f"\nstill unmatched ({len(unmatched)}) — candidates for new rules:")
        for icd, name in sorted(set(unmatched)):
            print(f"  {icd or '—':<10} {name}")


if __name__ == "__main__":
    main()
