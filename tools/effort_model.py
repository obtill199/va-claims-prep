#!/usr/bin/env python3
# Copyright (c) 2026 Oliver Tillinghast.
# Licensed under the PolyForm Noncommercial License 1.0.0.
# Free for veterans, VSOs, nonprofits and government. Commercial use
# requires a separate licence -- see LICENSE, NOTICE.md, COMMERCIAL.md.
"""
tools/effort_model.py — how much work the package actually is, with and
without the tool.

Everything countable is counted from the real artifacts: form fields, form
questions, record pages, generated characters. Everything human is an
explicit per-unit rate declared at the top, so the estimate can be argued
with rather than taken on faith. Change a rate and the whole model moves.

    python tools/effort_model.py
"""

import json
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)

# --------------------------------------------------------------- rates
# Seconds. Deliberately conservative: where a range was plausible I took the
# faster end, because overstating the manual side would flatter the tool.
RATE = {
    "read_form_question": 6,      # read a yes/no item and decide
    "tick_box": 3,                # find and mark the box
    "type_identity_field": 12,    # name, address, dates - includes checking
    # Scales with record size: a 10-page sample is not a 529-page export.
    # Modelled as a base cost plus time proportional to pages scanned.
    "search_record_base": 45,
    "search_record_per_100p": 20,
    "write_explanation_line": 120,# compose one Item 29 entry from memory
    "find_page_citation": 60,     # locate and note the page a finding is on
    "write_buddy_letter_template": 300,
    "assemble_and_check": 600,    # collate, re-read, sanity check
}


def count_form_fields():
    from pypdf import PdfReader
    out = {}
    for label, path in [
        ("DD 2807-1", "forms/dd2807-1.pdf"),
        ("SHA Part A", "forms/SHA_DBQ_Part_A_Self-Assessment.pdf"),
    ]:
        reader = PdfReader(os.path.join(REPO, path))
        fields = reader.get_fields() or {}
        buttons = [k for k, v in fields.items() if v.get("/FT") == "/Btn"]
        text = [k for k, v in fields.items() if v.get("/FT") == "/Tx"]
        out[label] = {"total": len(fields), "buttons": len(buttons),
                      "text": len(text)}
    return out


def count_questions():
    """Distinct yes/no questions a human must read and answer."""
    rows = json.load(open(os.path.join(REPO, "dd2807_crosswalk.json"), encoding="utf-8"))
    dd = [r for r in rows if r.get("yes_field") and r.get("question_text")]
    sha_fields = json.load(open(os.path.join(REPO, "field_names_sha.json"), encoding="utf-8"))
    sha = [k for k in sha_fields if k.endswith("_Question_YesNo_Response")]
    return {"DD 2807-1 items": len(dd), "SHA yes/no questions": len(sha)}


def tool_output(record_path=None):
    """What the tool actually produced on a given record."""
    import coded_records  # noqa: F401
    import condition_library as cl
    import extract_conditions as ec
    from pdf_io import extract_text_with_page_offsets

    text, starts = extract_text_with_page_offsets(
        record_path or os.path.join(REPO, "tools", "sample_record.pdf"))
    records = ec.aggregate(list(ec.parse_diagnoses(text, starts, "s.pdf")),
                           list(ec.parse_problems(text)))
    clinical = [r for r in records if not r["administrative"]]

    questions = set()
    for c in clinical:
        for item, letter, _sha_slug, _, conf in cl.match(c["icd10"], "Male"):
            if item:
                questions.add((item, letter, conf))
    return {"pages": len(starts), "conditions": len(clinical),
            "questions_reached": len(questions)}


def hhmm(seconds):
    h, m = divmod(round(seconds / 60), 60)
    return f"{h}h {m:02d}m" if h else f"{m}m"


def main():
    record = sys.argv[1] if len(sys.argv) > 1 else None
    fields = count_form_fields()
    questions = count_questions()
    tool = tool_output(record)
    if record:
        print(f"(modelling against: {os.path.basename(record)})\n")

    print("=" * 70)
    print("WHAT THE TASK ACTUALLY IS  (counted, not estimated)")
    print("=" * 70)
    for label, f in fields.items():
        print(f"  {label:<12} {f['total']:>4} form fields "
              f"({f['buttons']} checkbox/radio, {f['text']} text)")
    for label, n in questions.items():
        print(f"  {label:<28} {n:>4}")
    print(f"  Record pages to search        {tool['pages']:>4}")
    print(f"  Conditions in that record     {tool['conditions']:>4}")
    print(f"  Form questions they reach     {tool['questions_reached']:>4}")

    dd_items = questions["DD 2807-1 items"]
    sha_items = questions["SHA yes/no questions"]
    conditions = tool["conditions"]
    reached = tool["questions_reached"]

    print()
    print("=" * 70)
    print("WITHOUT THE TOOL")
    print("=" * 70)
    manual = []
    manual.append(("Read and answer every DD 2807-1 item",
                   dd_items * (RATE["read_form_question"] + RATE["tick_box"])))
    manual.append(("Read and answer every SHA question",
                   sha_items * (RATE["read_form_question"] + RATE["tick_box"])))
    manual.append(("Type identity fields on both forms (~20, twice over)",
                   20 * RATE["type_identity_field"] * 2))
    per_search = (RATE["search_record_base"]
                  + RATE["search_record_per_100p"] * tool["pages"] / 100)
    manual.append((f"Search the record once per condition ({conditions} x "
                   f"{round(per_search)}s over {tool['pages']}p)",
                   conditions * per_search))
    manual.append(("Find and note a page citation per condition",
                   conditions * RATE["find_page_citation"]))
    manual.append((f"Write an Item 29 explanation per confirmed answer (~{reached})",
                   reached * RATE["write_explanation_line"]))
    manual.append(("Write a buddy-letter template",
                   RATE["write_buddy_letter_template"]))
    manual.append(("Collate, re-read and sanity check",
                   RATE["assemble_and_check"]))
    total_manual = sum(s for _, s in manual)
    for label, s in manual:
        print(f"  {label:<52} {hhmm(s):>8}")
    print(f"  {'TOTAL':<52} {hhmm(total_manual):>8}")

    print()
    print("=" * 70)
    print("WITH THE TOOL")
    print("=" * 70)
    with_tool = [
        ("Fill the questionnaire (15 fields, once)",
         15 * RATE["type_identity_field"]),
        ("Upload records and wait for extraction", 60),
        # The review screen warns about federal penalties for a false
        # statement. Modelling 6s an item would be modelling someone
        # ignoring that warning. 20s is someone actually reading.
        ("Review proposals properly (bulk-confirm, then read each at 20s)",
         reached * 20),
        ("Read and edit the drafted Item 29 text", 8 * 60),
        ("Download and check the package", 5 * 60),
    ]
    total_tool = sum(s for _, s in with_tool)
    for label, s in with_tool:
        print(f"  {label:<52} {hhmm(s):>8}")
    print(f"  {'TOTAL':<52} {hhmm(total_tool):>8}")

    print()
    print("=" * 70)
    saved = total_manual - total_tool
    print(f"  Manual   {hhmm(total_manual)}")
    print(f"  With it  {hhmm(total_tool)}")
    print(f"  SAVED    {hhmm(saved)}   ({saved / total_manual:.0%} less time)")
    print("=" * 70)
    print()
    print("Rates used (seconds), change these to disagree with the model:")
    for k, v in RATE.items():
        print(f"  {k:<28} {v}")


if __name__ == "__main__":
    main()
