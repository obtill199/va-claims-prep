# Copyright (c) 2026 Oliver Tillinghast.
# Licensed under the PolyForm Noncommercial License 1.0.0.
# Free for veterans, VSOs, nonprofits and government. Commercial use
# requires a separate licence -- see LICENSE, NOTICE.md, COMMERCIAL.md.
"""
Secondary service connection: the questions, and the line they must not cross.

VA can service-connect a condition caused or aggravated by another one.
It is worth as much as any other grant and is routinely missed on a first
claim. Surfacing it is valuable; asserting it would be practising medicine.

Most of these tests are about the second half of that sentence. The module
is allowed to say "your records contain X and Y, ask whether they connect".
It is not allowed to say they connect, and nothing it produces may reach a
form field.
"""

import inspect
import os
import re
import sys

import pytest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)

import intake  # noqa: E402
import package_bundle  # noqa: E402
import secondary  # noqa: E402


def cond(code, name, page=1, **kw):
    d = {"icd10": code, "condition": name, "source_page": page}
    d.update(kw)
    return d


RHINITIS = cond("J30.9", "Allergic rhinitis", 5)
LUMBAGO = cond("M54.5", "Lumbago", 12)
DEPRESSION = cond("F32.9", "Major depressive disorder", 40)
APNEA = cond("G47.33", "Obstructive sleep apnea", 61)
HEARING = cond("H91.93", "Hearing loss", 7)


# ------------------------------------------------ the line it must not cross

def test_every_output_is_phrased_as_a_question():
    """Structural, not editorial. A nexus is a medical opinion; this module
    reports pairings and hands them to somebody qualified to judge."""
    for link in secondary.LINKS:
        assert link["question"].rstrip().endswith("?"), link["id"]


def test_no_rule_asserts_causation():
    banned = re.compile(
        r"\bis caused by\b|\bwas caused by\b|\bcauses\b|\bis due to\b|"
        r"\byou have\b|\byou should claim\b|\bwill be\b|\bis secondary to\b",
        re.I)
    for link in secondary.LINKS:
        hit = banned.search(link["question"])
        assert not hit, f"{link['id']} asserts rather than asks: {hit.group(0)!r}"


def test_the_module_cannot_write_to_a_form():
    """No output of this module may reach an AcroForm field. The guarantee
    is that it has no vocabulary for it -- it never imports the form layer
    and never mentions a field name."""
    src = inspect.getsource(secondary)
    for forbidden in ("fill_forms", "target_field", "Proposal", "proposed_value",
                      "AcroForm", "confirmed"):
        assert forbidden not in src, f"secondary.py references {forbidden}"


def test_no_field_name_from_either_form_appears_in_any_rule():
    fields = {f for group in intake.BLANK_BY_DESIGN.values() for f in group}
    src = inspect.getsource(secondary)
    for f in fields:
        assert f not in src


def test_the_worksheet_section_says_these_are_not_findings():
    text = secondary.worksheet_section([RHINITIS, APNEA])
    assert "questions, not findings" in text.lower()
    assert "medical opinion" in text.lower()
    assert "clinician" in text.lower()


# ---------------------------------------------------------- what it finds

def test_it_notices_a_pairing_that_is_already_fully_documented():
    """The strongest case: both sides are in the file already, so the
    question is how to claim them, not whether the member has them."""
    got = secondary.find([RHINITIS, APNEA])
    apnea = [i for i in got if "apnea" in i["ask"]]
    assert apnea and apnea[0]["both_present"]
    assert "p. 5" in apnea[0]["because"]
    assert "p. 61" in apnea[0]["partner_because"]


def test_it_asks_about_a_partner_that_is_not_documented_yet():
    got = secondary.find([RHINITIS])
    apnea = [i for i in got if "apnea" in i["ask"]]
    assert apnea and not apnea[0]["both_present"]
    assert apnea[0]["partner_because"] is None


def test_nothing_fires_on_an_empty_or_uncoded_record():
    assert secondary.find([]) == []
    assert secondary.find([{"icd10": "", "condition": "Something"}]) == []


def test_a_single_condition_is_not_paired_with_itself():
    """A back condition matches both sides of the spine rule. That is one
    thing in the record, not two things to ask about."""
    got = secondary.find([cond("M54.1", "Radiculopathy")])
    assert not [i for i in got if i["id"] == "radiculopathy-spine"]


# ------------------------------------------------- keeping it short enough

def test_one_entry_per_topic():
    """Sleep apnea is reachable from an airway condition and again from a
    mental health condition. Printing both spends a short VSO appointment
    twice on one topic."""
    got = secondary.find([RHINITIS, DEPRESSION])
    asks = [i["ask"] for i in got]
    assert len(asks) == len(set(asks))
    apnea = [i for i in got if "apnea" in i["ask"]]
    assert len(apnea) == 1
    # Both routes are still cited, so the VSO sees every way in.
    assert "Allergic rhinitis" in apnea[0]["because"]
    assert "Major depressive disorder" in apnea[0]["because"]


def test_documented_pairings_sort_above_speculative_ones():
    got = secondary.find([RHINITIS, LUMBAGO, DEPRESSION, APNEA, HEARING])
    flags = [i["both_present"] for i in got]
    assert flags == sorted(flags, reverse=True)


def test_a_busy_record_does_not_produce_an_unreadable_list():
    many = [RHINITIS, LUMBAGO, DEPRESSION, APNEA, HEARING,
            cond("E11.9", "Type 2 diabetes", 22),
            cond("M17.11", "Osteoarthritis, right knee", 30),
            cond("K21.9", "GERD", 33),
            cond("S06.0X0A", "Concussion", 44)]
    assert len(secondary.find(many)) <= 12


# -------------------------------------------------- it reaches the member

def test_the_questions_reach_the_readme():
    block = package_bundle.format_secondary_questions([RHINITIS, APNEA])
    assert "apnea" in block
    readme = package_bundle.render_readme(
        member_name="DOE, J", contents="  (files)",
        conditions=[RHINITIS, APNEA])
    assert "medication" in readme.lower()
    assert "does not try" in readme


def test_an_empty_result_leaves_no_dangling_heading():
    assert package_bundle.format_secondary_questions([]) == ""
    assert secondary.worksheet_section([]) == ""


def test_self_reported_conditions_are_cited_as_such():
    import self_report as sr
    apnea_report = sr.to_conditions(["apnea"], None)[0]
    got = secondary.find([RHINITIS, apnea_report])
    apnea = [i for i in got if "apnea" in i["ask"]][0]
    assert apnea["both_present"]
    assert "you told us" in apnea["partner_because"]


@pytest.mark.parametrize("link", secondary.LINKS, ids=lambda l: l["id"])
def test_every_rule_is_well_formed(link):
    for key in ("id", "question", "ask", "match", "partner"):
        assert link.get(key), f"{link['id']} missing {key}"
    assert callable(link["match"]) and callable(link["partner"])
    # A prompt id, when given, must exist in the self-report catalog.
    if link.get("prompt"):
        import self_report as sr
        ids = {i for _g, items in sr.CATALOG for (i, _l, _c, _h) in items}
        assert link["prompt"] in ids, f"{link['id']} points at a missing prompt"


def test_matchers_never_raise_on_junk():
    for link in secondary.LINKS:
        for junk in ("", None, "not-a-code", "12345", "Z"):
            assert link["match"](junk) in (True, False)
            assert link["partner"](junk) in (True, False)
