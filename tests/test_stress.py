# Copyright (c) 2026 Oliver Tillinghast.
# Licensed under the PolyForm Noncommercial License 1.0.0.
# Free for veterans, VSOs, nonprofits and government. Commercial use
# requires a separate licence -- see LICENSE, NOTICE.md, COMMERCIAL.md.
"""
Hostile input.

The unit fixtures are well-formed by construction, which is the one thing a
real claims file never is. A C-file is assembled over decades by different
systems, refiled with every claim, and padded with billing pages whose
procedure codes are shaped exactly like diagnoses.

These tests exist to break the parsers rather than confirm them. Several of
them encode bugs that a synthetic C-file actually found:

  a diagnosis name truncated at an interior lowercase word, which destroyed
  "Obstructive sleep apnea" -- among the most-claimed VA conditions -- down
  to "Obstructive"

  procedure and form codes that satisfy the ICD-10 shape and must not be
  reported as conditions

Anything here that fails is a condition a veteran does not get credit for,
or one they get credited with falsely. Both are bad; they are not equally
bad, and the tests say which is which.
"""

import os
import sys
import time

import pytest
from conftest import REPO

sys.path.insert(0, os.path.join(REPO, "tools"))

import coded_records as cr
import extract_conditions as ec

# --------------------------------------------------- names must survive

# Real ICD-10 descriptions containing words that also appear as ALL-CAPS
# column values in claims exports. The parser must not truncate at them.
REAL_NAMES = [
    "Obstructive sleep apnea (adult) (pediatric)",
    "Unilateral primary osteoarthritis, right knee",
    "Bilateral primary osteoarthritis of knee",
    "Adjustment disorder with chronic depressed mood",
    "Insomnia due to other mental disorder, sleep disorder",
    "Chronic obstructive pulmonary disease with acute exacerbation",
    "Primary hypertension",
    "Sleep apnea, unspecified",
    "Dental caries on smooth surface, limited to enamel",
    "Other specified postprocedural states",
    "Low back pain, unspecified",
    "Post-traumatic stress disorder, unspecified",
]


@pytest.mark.parametrize("name", REAL_NAMES)
def test_a_diagnosis_name_is_never_truncated_mid_phrase(name):
    """"Obstructive" on a worksheet handed to a VSO is worse than useless:
    it is unsearchable, unratable, and looks like a parser failure -- which
    it is."""
    assert cr._clean_description(" " + name) == name


@pytest.mark.parametrize("tail", ["PRIMARY CARE", "SLEEP LAB", "AUDIOLOGY",
                                  "BEHAVIORAL HEALTH", "ORTHOPEDICS"])
def test_all_caps_department_tails_are_still_stripped(tail):
    """The other direction. These are column values, not part of the name."""
    got = cr._clean_description(f" Low back pain, unspecified {tail}")
    assert got == "Low back pain, unspecified"


# --------------------------------------------- decoys must not be reported

# Every one of these appears in a real claims file and satisfies, or nearly
# satisfies, the ICD-10 shape.
DECOY_LINES = [
    "G0438      ANNUAL WELLNESS VISIT INITIAL                    $168.00",
    "J1885      INJECTION KETOROLAC TROMETHAMINE 15 MG            $12.00",
    "A9270      NON-COVERED ITEM OR SERVICE                        $0.00",
    "Q4101      APLIGRAF PER SQUARE CENTIMETER                   $412.00",
    "R0070      TRANSPORTATION PORTABLE X-RAY EQUIPMENT           $58.00",
    "FORM 21-4138 STATEMENT IN SUPPORT OF CLAIM RECEIVED 03/14/2019",
    "FORM 21-526EZ APPLICATION FOR DISABILITY COMPENSATION",
    "DRG 470 MAJOR JOINT REPLACEMENT LOWER EXTREMITY",
    "NDC 00093-7368-56 SERTRALINE HCL 50MG TAB",
    "CPT 99213 OFFICE OUTPATIENT VISIT ESTABLISHED PATIENT",
    "ACCOUNT M12.345 STATEMENT BALANCE FORWARD",
]


@pytest.mark.parametrize("line", DECOY_LINES)
def test_billing_and_form_codes_are_not_reported_as_diagnoses(line):
    """A false positive puts a condition the veteran does not have onto a
    form carrying a federal false-statement penalty."""
    found = [e["code"] for e in cr.parse_coded_lines(line)]
    assert not found, f"reported {found} from a billing line"


def test_a_page_of_pure_billing_yields_nothing():
    page = "\n".join(DECOY_LINES * 6)
    assert not list(cr.parse_coded_lines(page))


# ------------------------------------------------------------ degenerate

# Named ids, because pytest writes the test id into PYTEST_CURRENT_TEST and
# Windows caps an environment variable at 32,767 characters. Ten thousand
# em dashes inline become a sixty-thousand-character id and every test in
# the session errors at setup -- on Windows only, silently green everywhere
# else. CI caught it; three local runs did not.
@pytest.mark.parametrize("text", [
    pytest.param("", id="empty"),
    pytest.param(" ", id="one-space"),
    pytest.param("\n" * 5000, id="blank-pages"),
    pytest.param("\x00\x01\x02", id="control-bytes"),
    pytest.param("M54.50", id="bare-code"),
    pytest.param("M54.50 " * 5000, id="code-repeated-5000x"),
    pytest.param("—" * 10000, id="separator-rule"),
    pytest.param("Diagnosis:", id="anchor-alone"),
    pytest.param("Diagnosis: " * 2000, id="anchor-repeated-2000x"),
    pytest.param("Diagnosis Date: " * 2000, id="date-anchor-repeated-2000x"),
])
def test_degenerate_input_returns_rather_than_raises(text):
    """These reach the parsers from real PDFs: empty pages, separator rules,
    OCR noise, and blocks cut in half by a page boundary."""
    list(cr.parse_coded_lines(text))
    list(ec.parse_diagnoses(text, None, "x"))
    list(ec.parse_problems(text))


def test_a_truncated_block_does_not_hang():
    """A diagnosis block split by a page boundary leaves an anchor with no
    terminator. The scan after it is bounded, so cost stays linear -- an
    unbounded one is how this parser hung for two minutes once before."""
    orphan = ("    Diagnosis: Low back pain, unspecified\n"
              "    Secondary Description:\n" + "filler\n" * 8)
    start = time.time()
    list(ec.parse_diagnoses(orphan * 400, None, "x"))
    assert time.time() - start < 10, "superlinear on orphaned anchors"


def test_extraction_cost_stays_linear_in_input_size():
    """Doubling the input must roughly double the time. A regex that
    backtracks turns a large claims file into a hang, and a hang on a
    veteran's own records reads as 'this tool is broken'."""
    unit = ("M54.50 Low back pain, unspecified 2019-06-11 Active\n"
            "G0438  ANNUAL WELLNESS VISIT $168.00\n"
            "Diagnosis: Tinnitus, bilateral\n    Secondary Description:\n")
    timings = {}
    for mult in (200, 400, 800):
        text = unit * mult
        start = time.time()
        list(cr.parse_coded_lines(text))
        list(ec.parse_diagnoses(text, None, "x"))
        timings[mult] = time.time() - start
    # Generous: catastrophic backtracking is orders of magnitude, not 4x.
    if timings[200] > 0.01:
        assert timings[800] < timings[200] * 12, timings


# ------------------------------------------------------- duplication

def test_the_same_condition_repeated_collapses_to_one():
    """The defining feature of a C-file. Reporting a condition fifty times
    because it was refiled fifty times is not extraction, it is echo."""
    line = "M54.50 Low back pain, unspecified 2019-06-11 Active\n"
    entries = list(cr.parse_coded_lines(line * 300))
    assert len(entries) == 300
    collapsed = cr.collapse(entries)
    assert len(collapsed) == 1


def test_collapsing_keeps_the_full_date_span():
    """The span is evidence -- it is what shows a condition is chronic
    rather than a single visit. Collapsing must not lose the ends."""
    text = ("M54.50 Low back pain, unspecified 2011-03-04 Active\n"
            "M54.50 Low back pain, unspecified 2019-06-11 Active\n"
            "M54.50 Low back pain, unspecified 2023-12-02 Active\n")
    collapsed = cr.collapse(list(cr.parse_coded_lines(text)))
    assert len(collapsed) == 1
    dates = collapsed[0].get("all_dates") or collapsed[0].get("dates") or []
    joined = " ".join(str(d) for d in dates) + str(collapsed[0])
    assert "2011" in joined and "2023" in joined
