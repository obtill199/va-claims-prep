#!/usr/bin/env python3
# Copyright (c) 2026 Oliver Tillinghast.
# Licensed under the PolyForm Noncommercial License 1.0.0.
# Free for veterans, VSOs, nonprofits and government. Commercial use
# requires a separate licence -- see LICENSE, NOTICE.md, COMMERCIAL.md.
"""
reconcile.py — Milestone 4: cross-source reconciliation.

BUILD_BRIEF.md section 3.2's core finding: sources contradict each other,
and the older evidence is in the file the parser handles worst. A
structured diagnosis date is not "when the condition started" — it's
"when someone first coded it." This surfaces cases where scanned/OCR
evidence (ocr.py + find_evidence.py) describes something relevant *before*
the structured record's first-seen date for a related condition, so a
reviewer sees "your coded record says X, but this scanned page from
earlier suggests Y" instead of silently trusting the cleaner-looking source.

This does not produce Proposals (schema.py) — OCR evidence doesn't map to
a specific form field the way a coded diagnosis does; it's surfaced for a
human (or a later milestone) to act on, not auto-fed into the confirm/fill
pipeline.

Usage:
    python reconcile.py conditions.json ocr_output.json -o reconciliation.json
"""

import argparse
import contextlib
import json
import re
from datetime import date

from find_evidence import search

# body_system -> OCR keywords worth cross-checking that system's conditions
# against. Deliberately narrow and only populated where there's a real
# document class to expect (BUILD_BRIEF.md's stated OCR target is duty
# limitation reports / profiles / handwritten notes) rather than guessed
# at broadly — an unpopulated body_system just means "nothing to
# cross-check yet," not "nothing exists."
BODY_SYSTEM_KEYWORDS = {
    "Musculoskeletal": [
        "duty limiting", "duty limitation", "lifting", "bending",
        "administrative duty", "fitness component",
    ],
    "Injury / trauma": [
        "duty limiting", "duty limitation",
    ],
}

# Bare "profile" was tried and removed: it matched 15 of 106 pages,
# overwhelmingly as a form-section header ("PROFILE" / "Profile Type")
# rather than an actual duty-limiting profile, and buried the one page
# that mattered under near-identical noise rows. The qualified phrases
# above are what actually distinguish a duty limitation document.
MIN_KEYWORDS_FOR_EVIDENCE = 2

# A page whose only "dates" are the same value seen across many pages is
# almost certainly a form revision/print date, not clinical evidence.
# Anything appearing on more than this fraction of matched pages is
# treated as boilerplate and not reported as a predating date.
BOILERPLATE_DATE_PAGE_FRACTION = 0.4

MONTHS = ("january|february|march|april|may|june|july|august|september|"
          "october|november|december|jan|feb|mar|apr|jun|jul|aug|sep|sept|"
          "oct|nov|dec")
DATE_RES = [
    re.compile(rf"\b(\d{{1,2}})\s+({MONTHS})\.?\s+(\d{{4}})\b", re.IGNORECASE),  # 16 May 2022
    re.compile(r"\b(\d{1,2})/(\d{1,2})/(\d{4})\b"),                             # 05/16/2022
]
MONTH_LOOKUP = {m[:3].lower(): i + 1 for i, m in enumerate([
    "january", "february", "march", "april", "may", "june", "july",
    "august", "september", "october", "november", "december"])}


def extract_dates(text):
    """Every date found in a page's OCR text, best-effort, as ISO strings.
    Deliberately permissive (OCR text is noisy) -- callers treat these as
    candidates to show a reviewer, not confirmed facts."""
    found = []
    for m in DATE_RES[0].finditer(text):
        day, month_s, year = m.groups()
        month = MONTH_LOOKUP.get(month_s[:3].lower())
        if month:
            with contextlib.suppress(ValueError):
                found.append(date(int(year), month, int(day)).isoformat())
    for m in DATE_RES[1].finditer(text):
        mm, dd, yyyy = m.groups()
        with contextlib.suppress(ValueError):
            found.append(date(int(yyyy), int(mm), int(dd)).isoformat())
    return sorted(set(found))


def _boilerplate_dates(ocr_results):
    """Dates appearing on a large fraction of pages — form revision/print
    dates, not clinical events. Computed over the whole document, not just
    matched pages, so it's stable regardless of which condition is being
    reconciled."""
    from collections import Counter
    counts = Counter()
    for page in ocr_results:
        for d in set(extract_dates(page["text"])):
            counts[d] += 1
    threshold = max(2, int(len(ocr_results) * BOILERPLATE_DATE_PAGE_FRACTION))
    return {d for d, n in counts.items() if n >= threshold}


def reconcile(conditions, ocr_results):
    boilerplate = _boilerplate_dates(ocr_results)
    page_by_num = {r["page"]: r for r in ocr_results}
    findings = []

    for cond in conditions:
        keywords = BODY_SYSTEM_KEYWORDS.get(cond["body_system"])
        if not keywords:
            continue

        hits = search(ocr_results, keywords)
        evidence = []
        for hit in hits:
            # One generic term alone (e.g. just "lifting") isn't enough to
            # call a page duty-limitation evidence — require corroboration.
            if len(hit["matched_keywords"]) < MIN_KEYWORDS_FOR_EVIDENCE:
                continue

            page_text = page_by_num[hit["page"]]["text"]
            candidate_dates = [d for d in extract_dates(page_text)
                               if d not in boilerplate]
            predates = [d for d in candidate_dates if d < cond["first_seen"]]
            if not predates:
                continue

            evidence.append({
                "page": hit["page"],
                "confidence": hit["confidence"],
                "matched_keywords": hit["matched_keywords"],
                "candidate_dates": candidate_dates,
                "earliest_predating_date": min(predates),
                "years_earlier": round(
                    (date.fromisoformat(cond["first_seen"])
                     - date.fromisoformat(min(predates))).days / 365.25, 1),
            })

        if evidence:
            findings.append({
                "condition": cond["condition"],
                "icd10": cond["icd10"],
                "body_system": cond["body_system"],
                "structured_first_seen": cond["first_seen"],
                "structured_source": cond["source_document"],
                "ocr_evidence": sorted(evidence, key=lambda e: e["earliest_predating_date"]),
            })
    return findings


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("conditions_json")
    ap.add_argument("ocr_json")
    ap.add_argument("-o", "--output", default="reconciliation.json")
    args = ap.parse_args()

    with open(args.conditions_json, encoding="utf-8") as fh:
        conditions = json.load(fh)["clinical"]
    with open(args.ocr_json, encoding="utf-8") as fh:
        ocr_results = json.load(fh)

    findings = reconcile(conditions, ocr_results)

    with open(args.output, "w", encoding="utf-8") as fh:
        json.dump(findings, fh, indent=2)

    print(f"{len(findings)} condition(s) with evidence predating the structured record "
          f"-> {args.output}")
    for f in findings:
        print(f"\n  {f['icd10']} {f['condition']!r}")
        print(f"    structured first_seen: {f['structured_first_seen']} "
              f"({f['structured_source']})")
        for e in f["ocr_evidence"]:
            print(f"    OCR page {e['page']} [{e['confidence']}]: "
                  f"{e['earliest_predating_date']} "
                  f"({e['years_earlier']} years earlier)")
            print(f"      matched: {e['matched_keywords']}")
            print(f"      all dates on page: {e['candidate_dates']}")


if __name__ == "__main__":
    main()
