# Copyright (c) 2026 Oliver Tillinghast.
# Licensed under the PolyForm Noncommercial License 1.0.0.
# Free for veterans, VSOs, nonprofits and government. Commercial use
# requires a separate licence -- see LICENSE, NOTICE.md, COMMERCIAL.md.
"""
Golden-output regression test for extract_conditions.py, per BUILD_BRIEF.md
section 8: the developer's own records are the test fixture, so accuracy
can be measured, not eyeballed.

The real record files (and the .txt/.json derived from them) are gitignored
and only exist on the developer's own machine — this test skips cleanly
everywhere else instead of failing.

Run: cd ~/va-claims-prep && .venv/bin/python -m pytest tests/ -v
"""

import json
import os
import re
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MHS_TXT = os.path.join(REPO, "mhs_genesis.txt")
WORKSHEET = os.path.join(REPO, "conditions_worksheet.md")

pytestmark = pytest.mark.skipif(
    not (os.path.exists(MHS_TXT) and os.path.exists(WORKSHEET)),
    reason="real record fixture not present on this machine (gitignored, by design)",
)


def _parse_worksheet_rows():
    text = open(WORKSHEET, encoding="utf-8").read()
    return re.findall(
        r"^\| (\S+) \| ([^|]+) \| ([^|]+) \| (\d{4}-\d\d-\d\d) \| (\d{4}-\d\d-\d\d) "
        r"\| (\d+) \| (\w+) \| ([^|]+) \|$",
        text, re.MULTILINE,
    )


def test_diagnosis_and_problem_counts():
    from extract_conditions import parse_diagnoses, parse_problems
    text = open(MHS_TXT, encoding="utf-8", errors="replace").read()
    assert len(list(parse_diagnoses(text))) == 50
    assert len(list(parse_problems(text))) == 10


def test_clinical_and_administrative_counts():
    from extract_conditions import parse_diagnoses, parse_problems, aggregate
    text = open(MHS_TXT, encoding="utf-8", errors="replace").read()
    records = aggregate(list(parse_diagnoses(text)), list(parse_problems(text)))
    clinical = [r for r in records if not r["administrative"]]
    admin = [r for r in records if r["administrative"]]
    assert len(clinical) == 21
    assert len(admin) == 11


def test_every_field_matches_golden_worksheet():
    """Field-by-field diff against conditions_worksheet.md — the same check
    used to verify this pipeline against BUILD_BRIEF.md's claimed output."""
    from extract_conditions import parse_diagnoses, parse_problems, aggregate
    text = open(MHS_TXT, encoding="utf-8", errors="replace").read()
    records = aggregate(list(parse_diagnoses(text)), list(parse_problems(text)))
    by_key = {(r["icd10"], r["condition"]): r for r in records}

    rows = _parse_worksheet_rows()
    assert len(rows) == 21, "worksheet parsing itself is broken — fix the test, not the code"

    for icd, cond, body, first, last, enc, status, problist in rows:
        key = (icd, cond.strip())
        got = by_key.get(key)
        assert got is not None, f"missing from extractor output: {key}"
        assert got["first_seen"] == first
        assert got["last_seen"] == last
        assert got["encounters"] == int(enc)
        assert got["active"] == (status.strip() == "Active")
        assert got["on_problem_list"] == (problist.strip() == "Yes")
        assert got["body_system"] == body.strip()


def test_no_empty_condition_names():
    from extract_conditions import parse_diagnoses, parse_problems, aggregate
    text = open(MHS_TXT, encoding="utf-8", errors="replace").read()
    records = aggregate(list(parse_diagnoses(text)), list(parse_problems(text)))
    assert all(r["condition"] for r in records)
