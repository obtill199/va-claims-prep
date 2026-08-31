# Copyright (c) 2026 Oliver Tillinghast.
# Licensed under the PolyForm Noncommercial License 1.0.0.
# Free for veterans, VSOs, nonprofits and government. Commercial use
# requires a separate license -- see LICENSE, NOTICE.md, COMMERCIAL.md.
"""
Increase claims: what the next rating level requires.

A different problem from an initial claim. Service connection is settled;
the question is severity, and 38 CFR Part 4 decides that on a specific
measurement rather than on how bad it feels. A veteran who does not know
which measurement says "my back is worse" and gets denied.

The same line applies here as everywhere else in this tool: report the
published criteria, report what the records contain, and let VA and a VSO
decide. These tests hold that line, and hold two others -- that the
reduction risk is stated before anything encouraging, and that a condition
already at its maximum is called out rather than left to waste somebody's
time.
"""

import inspect
import re

import pytest

import increase
import rating_criteria as rc


def cond(code, name, last_seen="2026-05-01", encounters=3, page=7):
    return {"icd10": code, "condition": name, "last_seen": last_seen,
            "encounters": encounters, "source_page": page}


BACK = cond("M54.50", "Low back pain, unspecified", "2019-09-08", 6, 12)
APNEA = cond("G47.33", "Obstructive sleep apnea", "2026-05-01", 3, 5)
TINNITUS = cond("H93.13", "Tinnitus, bilateral", "2025-06-02", 2, 4)
PTSD = cond("F43.10", "Post-traumatic stress disorder", "2026-02-11", 9, 20)


# ------------------------------------------------- the line it must not cross

def test_it_never_says_anybody_qualifies():
    """Whether a rating goes up is VA's determination on a full record and
    an examination."""
    banned = re.compile(
        r"\byou qualify\b|\byou are entitled\b|\byou will (?:get|receive)\b|"
        r"\bguarantee|\bshould be rated\b|\byou deserve\b|\bwe recommend claiming\b",
        re.I)
    text = increase.worksheet([BACK, APNEA, TINNITUS],
                              {"M54.50": 10, "G47.33": 30, "H93.13": 10})
    hit = banned.search(text)
    assert not hit, f"claims an outcome: {hit.group(0)!r}"


def test_it_cannot_reach_a_form():
    for module in (increase, rc):
        src = inspect.getsource(module)
        for forbidden in ("fill_forms", "target_field", "Proposal",
                          "proposed_value"):
            assert forbidden not in src, f"{module.__name__} references {forbidden}"


def test_the_reduction_risk_is_stated_before_anything_else():
    """Filing invites a fresh examination, and an examination showing
    improvement can lower an existing rating. A veteran who learns that
    afterwards was badly served no matter how good the rest was."""
    text = increase.worksheet([BACK], {"M54.50": 10})
    assert "lower the rating" in text
    first_section = text.index("## Read this first")
    assert first_section < text.index("## What each one would need")
    assert text.index("lower the rating") < text.index("## What each one would need")


# --------------------------------------------------------- what it works out

def test_a_capped_condition_is_called_out_not_encouraged():
    """Tinnitus maxes at 10 percent. Telling somebody not to spend time on
    it is often the most useful thing on the page."""
    result = increase.plan([TINNITUS], {"H93.13": 10})
    assert [i for i in result["capped"] if "Tinnitus" in i["name"]]
    assert not result["actionable"]
    text = increase.worksheet([TINNITUS], {"H93.13": 10})
    assert "do not spend time here" in text.lower()


def test_it_names_the_next_level_and_what_it_measures():
    result = increase.plan([BACK], {"M54.50": 10})
    item = result["actionable"][0]
    assert item["next"]["percent"] == 20
    assert "degrees" in item["next"]["requires"]
    assert "flexion" in item["measures"].lower()


def test_the_apnea_jump_turns_on_the_prescription_not_the_symptoms():
    """30 to 50 is decided by a prescribed breathing device. People rated
    at 30 who use a CPAP routinely do not know that."""
    item = increase.plan([APNEA], {"G47.33": 30})["actionable"][0]
    assert item["next"]["percent"] == 50
    assert "breathing assistance device" in item["next"]["requires"].lower()
    assert "prescri" in item["measures"].lower()


def test_stale_evidence_is_flagged_as_needing_a_current_exam():
    """An increase claim with nothing recent has very little to work with."""
    item = increase.plan([BACK], {"M54.50": 10})["actionable"][0]
    assert item["evidence"]["recent"] is False
    assert "new examination" in item["evidence"]["line"]


def test_recent_evidence_is_reported_as_recent():
    item = increase.plan([APNEA], {"G47.33": 30})["actionable"][0]
    assert item["evidence"]["recent"] is True


def test_a_documented_but_unrated_condition_is_a_different_claim():
    """Not an increase. Saying so stops somebody filing the wrong thing."""
    result = increase.plan([PTSD], {})
    assert [i for i in result["unrated"] if "stress" in i["condition"].lower()]
    text = increase.worksheet([PTSD], {})
    assert "a new one, not an increase" in text


def test_every_actionable_entry_names_a_questionnaire():
    """The DBQ is the form built to capture what the rating turns on, and a
    private doctor can complete one. It is the most actionable thing here."""
    result = increase.plan([BACK, APNEA], {"M54.50": 10, "G47.33": 30})
    for item in result["actionable"]:
        assert item["dbq"], f"{item['name']} names no DBQ"


def test_hearing_loss_points_at_the_test_instead_of_summarising_a_table():
    """Rated from an audiogram against a combining table. A summary would
    mislead; the action is simply to get the exam."""
    item = increase.plan([cond("H90.3", "Hearing loss")], {"H90.3": 10})
    entry = [i for i in item["actionable"] if "Hearing" in i["name"]][0]
    assert "pointer" in entry
    assert "audiogram" in entry["pointer"].lower()


# ------------------------------------------------------------- staying honest

def test_the_criteria_carry_their_own_age_and_a_source():
    """Part 4 is revised -- the digestive schedule changed substantially in
    2024. A summary shown undated reads as current."""
    assert re.fullmatch(r"\d{4}-\d{2}", rc.REVIEWED)
    assert rc.CFR_PART_4.startswith("https://www.ecfr.gov/")
    text = increase.worksheet([BACK], {"M54.50": 10})
    assert rc.REVIEWED in text and rc.CFR_PART_4 in text
    assert "not decisions" in text


@pytest.mark.parametrize("entry", rc.CRITERIA, ids=lambda e: e["id"])
def test_every_criterion_is_well_formed(entry):
    assert entry["name"] and entry["dc"] and entry["dbq"]
    assert entry["measures"], f"{entry['id']} does not say what to measure"
    assert entry["levels"], f"{entry['id']} lists no levels"
    percents = [p for p, _ in entry["levels"]]
    assert percents == sorted(percents), f"{entry['id']} levels out of order"
    for _pct, text in entry["levels"]:
        assert len(text) > 10
    for junk in ("", None, "junk"):
        assert entry["match"](junk) in (True, False)


def test_nothing_fires_on_an_empty_record():
    assert increase.plan([], {}) == {"capped": [], "actionable": [], "unrated": []}
    assert increase.worksheet([], {}) == ""
