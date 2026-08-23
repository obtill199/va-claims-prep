"""
The coded-record parser, and the two text extractors agreeing.

Written after two real failures:

  The MHS Genesis parser found nothing in five other real record formats,
  because none contain its "Diagnosis:" anchor. Silent, total, and on
  records a veteran is quite likely to have.

  Once fixed, the desktop build (pdfplumber) and the browser build (pypdf)
  disagreed: the same CCD-A export yielded 9 conditions on the desktop and
  was classified "narrative" in the browser. Column padding differs between
  the two extractors — 3 spaces versus 16 — and the code/description
  lookahead was capped at 4. Any whitespace assumption in this module must
  hold under both.
"""

import os
import sys

import pytest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)

import coded_records as cr  # noqa: E402
import extract_conditions as ec  # noqa: E402


def conditions_from(text):
    records = ec.aggregate(cr.extract(text, None, "test.pdf"), [])
    return [r for r in records if not r["administrative"]]


# ------------------------------------------------- extractor independence

TIGHT = "M54.50   Low back pain, unspecified    2019-06-11 Active    2026-03-30"
WIDE = ("   M54.50                Low back pain, unspecified            "
        "        2019-06-11    Active")


@pytest.mark.parametrize("text,label", [(TIGHT, "pdfplumber spacing"),
                                        (WIDE, "pypdf layout spacing")])
def test_column_padding_does_not_change_the_result(text, label):
    got = conditions_from(text)
    assert len(got) == 1, f"{label}: expected one condition, got {got}"
    assert got[0]["icd10"] == "M54.50"
    assert "Low back pain" in got[0]["condition"]


def test_narrative_detection_agrees_across_spacing():
    assert not cr.looks_narrative(TIGHT)
    assert not cr.looks_narrative(WIDE)
    assert cr.looks_narrative(
        "The patient returns today for reassessment of persistent lumbar "
        "discomfort we have been following since the spring.")


# -------------------------------------------------------- format coverage

CLAIMS_LINE = ("02/19/2019 CLM07100331 99214 OFFICE VISIT EST PT LEVEL "
               "M54.50 Low back pain, unspecified PRIMARY CARE 210.00 154.30")


def test_claims_ledger_line():
    got = conditions_from(CLAIMS_LINE)
    assert len(got) == 1
    assert got[0]["icd10"] == "M54.50"
    assert got[0]["first_seen"] == "2019-02-19"
    assert "PRIMARY" not in got[0]["condition"], "billing tail must be trimmed"
    assert "210.00" not in got[0]["condition"], "amounts must be trimmed"


def test_cpt_and_claim_numbers_are_not_mistaken_for_diagnoses():
    """99214 and CLM07100331 must not parse as ICD-10 codes."""
    got = conditions_from(CLAIMS_LINE)
    assert {c["icd10"] for c in got} == {"M54.50"}


def test_table_headers_are_skipped():
    header = "ICD-10   DESCRIPTION                   ONSET      STATUS"
    assert not conditions_from(header)


def test_truncated_descriptions_prefer_the_longest_seen():
    """Ledger columns truncate: the same code appears as 'Low back pain, lu'
    on one line and in full on another."""
    text = ("01/02/2020 M54.50   Low back pain, lu\n"
            "02/03/2020 M54.50   Low back pain, unspecified")
    got = conditions_from(text)
    assert len(got) == 1
    assert got[0]["condition"] == "Low back pain, unspecified"


# -------------------------------------------------------- data hygiene

def test_implausible_future_dates_are_rejected():
    """Seen in a real claims ledger: service dates decades in the future.
    Putting one on a federal form as an onset date would be a false
    statement."""
    text = "01/11/2040 M51.36   Other disc degeneration, lumbar"
    got = conditions_from(text)
    assert not got or all(c["first_seen"] < "2030-01-01" for c in got)


def test_malformed_input_does_not_crash():
    for text in ("", "   ", "no codes here at all", "M5", "....", "\n\n\n"):
        conditions_from(text)


# ------------------------------------------------ real fixtures, if present

# Point this at a folder of record PDFs to run the cross-extractor check
# against real formats. Absent by default so the suite runs anywhere.
FIXTURES = os.environ.get("VACP_FORMAT_FIXTURES", "")


@pytest.mark.skipif(not (FIXTURES and os.path.isdir(FIXTURES)),
                    reason="set VACP_FORMAT_FIXTURES to a folder of record PDFs")
def test_both_extractors_agree_on_every_fixture():
    """The regression that classified a readable export as narrative."""
    pytest.importorskip("pypdf")
    from pypdf import PdfReader
    from pdf_io import extract_text_with_page_offsets

    for name in sorted(os.listdir(FIXTURES)):
        if not name.endswith(".pdf"):
            continue
        path = os.path.join(FIXTURES, name)
        plumber_text, _ = extract_text_with_page_offsets(path)
        reader = PdfReader(path)
        pypdf_text = "\n".join(
            p.extract_text(extraction_mode="layout") or "" for p in reader.pages)

        a = len(conditions_from(plumber_text))
        b = len(conditions_from(pypdf_text))
        assert a == b, (f"{name}: pdfplumber found {a} conditions, "
                        f"pypdf found {b} — the builds have diverged")
