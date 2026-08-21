#!/usr/bin/env python3
"""
dd2807_crosswalk.py — builds the item-number/letter <-> field-name <-> question-text
crosswalk for DD 2807-1.

DD 2807-1 is an Adobe LiveCycle/XFA form: field names are positional
(e.g. "Yes12C"/"No12C" for item 12, sub-item c), not semantic slugs like the
SHA form. There is no PHI risk in reading this crosswalk from the blank form
itself — it's a public DoD form with no member data in it.

Two independent sources are joined on (item_number, letter):
  1. Field names, parsed from inspect_fields.py's dump (positional).
  2. Question text, parsed from the blank PDF's own visible page text.

Usage:
    python dd2807_crosswalk.py dd2807-1.pdf field_names_dd2807.json -o dd2807_crosswalk.json
"""

import argparse
import json
import re

import fitz  # pymupdf

# Item numbers 10-28 are the yes/no medical-history block. 1-9 are identity/
# service fields, 29 is a free-text explanation field — both out of scope
# for condition-based proposals (Milestone 1 only maps extracted conditions).
NUMBER_WORDS = {
    10: "Ten", 11: "Eleven", 12: "Twelve", 13: "Thirteen", 14: "Fourteen",
    15: "Fifteen", 16: "Sixteen", 17: "Seventeen", 18: "Eighteen",
    19: "Nineteen", 20: "Twenty", 21: "TwentyOne", 22: "TwentyTwo",
    23: "TwentyThree", 24: "TwentyFour", 25: "TwentyFive", 26: "TwentySix",
    27: "TwentySeven", 28: "TwentyEight",
}

ITEM_LETTER_RE = re.compile(r"^(\d{1,2})\.([a-z])\.\s*(.*)$")
ITEM_ONLY_RE = re.compile(r"^(\d{1,2})\.\s+(.*)$")
LETTER_ONLY_RE = re.compile(r"^([a-z])\.\s*(.*)$")

# Lines that are boilerplate/headers, not question text — never item content
# and never a continuation of the previous item's text.
SKIP_LINES = {
    "YES NO", "HAVE YOU EVER HAD OR DO YOU NOW HAVE:", "(Continued)",
}
SKIP_PREFIXES = (
    "Mark each item", "CUI ", "PREVIOUS EDITION", "Page ", "DD FORM",
    "NOTE:", "LAST NAME,", "SOCIAL SECURITY", "DoD ID NUMBER", "(Updated",
)


def _extract_page_text(pdf_path, pages=(0, 1)):
    doc = fitz.open(pdf_path)
    return "\n".join(doc[p].get_text() for p in pages)


def parse_question_text(pdf_path):
    """Return {(item:int, letter:str|None): question_text}."""
    text = _extract_page_text(pdf_path)
    out = {}
    current_item = None
    last_key = None

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line in SKIP_LINES or line.startswith(SKIP_PREFIXES):
            continue

        m = ITEM_LETTER_RE.match(line)
        if m:
            item, letter, rest = int(m.group(1)), m.group(2), m.group(3)
            if item < 10 or item > 28:
                current_item, last_key = None, None
                continue
            current_item = item
            key = (item, letter)
            out[key] = rest
            last_key = key
            continue

        m = LETTER_ONLY_RE.match(line)
        if m and current_item is not None:
            letter, rest = m.group(1), m.group(2)
            key = (current_item, letter)
            out[key] = rest
            last_key = key
            continue

        m = ITEM_ONLY_RE.match(line)
        if m:
            item, rest = int(m.group(1)), m.group(2)
            if item < 10 or item > 28:
                current_item, last_key = None, None
                continue
            current_item = item
            key = (item, None)
            out[key] = rest
            last_key = key
            continue

        # No item marker on this line: a wrapped continuation of the
        # previous item's text (e.g. "...pollens,\netc." across two lines).
        if last_key is not None:
            out[last_key] = (out[last_key] + " " + line).strip()

    return out


FIELD_NAME_RE = re.compile(r"^(Yes|No)(\d{1,2})([A-Za-z]*)\[0\]$")


def parse_field_names(field_dump_json):
    """Return {(item:int, letter:str|None): {"yes_field": leaf_path, "no_field": leaf_path}}."""
    with open(field_dump_json) as fh:
        dump = json.load(fh)

    by_key = {}
    for full_path, meta in dump.items():
        if meta.get("field_type") != "/Btn":
            continue
        leaf = full_path.rsplit(".", 1)[-1]
        m = FIELD_NAME_RE.match(leaf)
        if not m:
            continue
        kind, item_s, letter = m.group(1), m.group(2), m.group(3)
        item = int(item_s)
        if item < 10 or item > 28:
            continue
        # Field names use uppercase letters (Yes12C); page text uses
        # lowercase (12.c). Normalize to lowercase so the two sources join.
        letter = letter.lower() or None
        key = (item, letter)
        entry = by_key.setdefault(key, {})
        entry["yes_field" if kind == "Yes" else "no_field"] = full_path
    return by_key


def build_crosswalk(pdf_path, field_dump_json):
    text_map = parse_question_text(pdf_path)
    field_map = parse_field_names(field_dump_json)

    keys = sorted(set(text_map) | set(field_map),
                   key=lambda k: (k[0], k[1] or ""))
    rows = []
    for key in keys:
        item, letter = key
        fields = field_map.get(key, {})
        rows.append({
            "item": item,
            "letter": letter,
            "question_text": text_map.get(key),
            "yes_field": fields.get("yes_field"),
            "no_field": fields.get("no_field"),
        })
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pdf")
    ap.add_argument("field_dump_json")
    ap.add_argument("-o", "--output", default="dd2807_crosswalk.json")
    args = ap.parse_args()

    rows = build_crosswalk(args.pdf, args.field_dump_json)
    with open(args.output, "w") as fh:
        json.dump(rows, fh, indent=2)

    unmatched = [r for r in rows if not r["question_text"] or not (r["yes_field"] or r["no_field"])]
    print(f"{len(rows)} items -> {args.output}")
    if unmatched:
        print(f"  {len(unmatched)} incomplete (missing text or field name):")
        for r in unmatched:
            print(f"    item {r['item']}{r['letter'] or ''}: "
                  f"text={r['question_text']!r} yes={r['yes_field']} no={r['no_field']}")


if __name__ == "__main__":
    main()
