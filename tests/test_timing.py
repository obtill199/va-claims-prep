# Copyright (c) 2026 Oliver Tillinghast.
# Licensed under the PolyForm Noncommercial License 1.0.0.
# Free for veterans, VSOs, nonprofits and government. Commercial use
# requires a separate licence -- see LICENSE, NOTICE.md, COMMERCIAL.md.
"""
The filing deadlines.

These are the only numbers in the tool that cost money if they are wrong.
A member told "you are in the BDD window" on day 89 files into a program
that has already closed to them; one told the opposite on day 90 gives up
a window that was still open. So the boundaries are pinned exactly, from
both sides, rather than tested somewhere comfortably in the middle.

Nothing here asserts advice. It asserts which window a date falls in.
"""

import os
import sys
from datetime import date, timedelta

import pytest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)

import timing  # noqa: E402

TODAY = date(2026, 8, 23)


def at(days_out):
    """A separation date `days_out` days from TODAY (negative = already out)."""
    return timing.assess(TODAY + timedelta(days=days_out), today=TODAY)


# --------------------------------------------------------- the boundaries

@pytest.mark.parametrize("days,state", [
    (181, "before_window"),   # one day too early
    (180, "bdd_window"),      # the window opens exactly here
    (91,  "bdd_window"),
    (90,  "bdd_window"),      # and closes exactly here -- still inside
    (89,  "bdd_missed"),      # one day too late
    (1,   "bdd_missed"),
    (0,   "bdd_missed"),      # separating today
])
def test_bdd_window_boundaries(days, state):
    assert at(days)["state"] == state


@pytest.mark.parametrize("days,state", [
    (-1,   "recently_out"),
    (-364, "recently_out"),
    (-365, "recently_out"),   # the last day of the retroactive year
    (-366, "long_out"),       # one day past it
])
def test_retroactive_year_boundaries(days, state):
    assert at(days)["state"] == state


def test_the_window_is_ninety_days_wide():
    inside = [d for d in range(400) if at(d)["state"] == "bdd_window"]
    assert min(inside) == timing.BDD_CLOSES
    assert max(inside) == timing.BDD_OPENS
    assert len(inside) == 91  # inclusive of both ends


# ------------------------------------------------------- what it tells them

def test_every_state_gives_something_to_do():
    for days in (365, 150, 45, -30, -900):
        a = at(days)
        assert a["headline"] and a["detail"]
        assert a["actions"], f"{a['state']} leaves the member with no next step"


def test_the_two_windows_that_close_are_marked_urgent():
    """These are the only two states where waiting costs money that cannot
    be recovered. They must not render as a calm blue note."""
    assert at(150)["state"] == "bdd_window"
    assert at(150)["urgency"] == "critical"
    assert at(-30)["state"] == "recently_out"
    assert at(-30)["urgency"] == "critical"


def test_a_countdown_is_given_while_a_window_is_open():
    for days in (150, -30):
        assert at(days)["days_left_in_window"] >= 0


def test_countdown_reaches_zero_on_the_last_day_not_below():
    assert at(timing.BDD_CLOSES)["days_left_in_window"] == 0
    assert at(-timing.RETRO_WINDOW)["days_left_in_window"] == 0


# ------------------------------------------------------------- bad input

@pytest.mark.parametrize("value", [
    None, "", "   ", "not a date", "2026-13-45", "08/23/2026", 12345,
])
def test_unparseable_input_is_reported_not_raised(value):
    """This runs on a date field a member typed into. It must never be the
    thing that takes the page down."""
    a = timing.assess(value, today=TODAY)
    assert a["state"] == "unknown"
    assert a["actions"] == []


def test_a_real_date_object_works_as_well_as_a_string():
    d = TODAY + timedelta(days=150)
    assert timing.assess(d, today=TODAY)["state"] == \
           timing.assess(d.isoformat(), today=TODAY)["state"]


# ------------------------------------------------- BDD eligibility caveat

def test_guard_and_reserve_are_warned_that_bdd_needs_full_time_duty():
    for component in ("National Guard", "Reserve"):
        note = timing.bdd_eligibility_caveat(component, "Not on active duty")
        assert note and "full-time active duty" in note


def test_regular_component_gets_no_caveat():
    assert timing.bdd_eligibility_caveat("Regular", "Active Component") is None


def test_the_caveat_does_not_echo_the_forms_double_spacing():
    note = timing.bdd_eligibility_caveat(
        "National Guard", "Active Duty  Active Guard Reserve")
    assert "  " not in note, "the form's spacing is being quoted back verbatim"


def test_caveat_survives_missing_answers():
    assert timing.bdd_eligibility_caveat(None, None) is None
    assert timing.bdd_eligibility_caveat("Reserve", None)


# ------------------------------------------------------ it reaches the user

def test_the_deadline_leads_the_readme():
    import package_bundle
    block = package_bundle.format_timing(at(150))
    assert block
    readme = package_bundle.render_readme(
        member_name="DOE, JOHN A", contents="  (files)", timing=at(150))
    assert "BDD WINDOW" in readme
    assert readme.index("BDD WINDOW") < readme.index("WHAT THIS IS"), \
        "the deadline is below the explainer; a member reads the top"


def test_no_date_means_no_empty_banner_in_the_readme():
    import package_bundle
    assert package_bundle.format_timing(timing.assess(None)) == ""


# --------------------------------------------- the questionnaire is generated

def test_the_browser_questionnaire_matches_intake_py():
    """The JS questionnaire used to be a hand-kept copy of intake.QUESTIONS.
    A question added to the Python was simply missing from the page people
    use, and nothing failed to say so -- which is how separation_date came
    to be asked everywhere except the browser. It is generated now; this
    fails if someone edits the generated block by hand or forgets to rebuild."""
    import re

    from conftest import FORM_HTML, read

    import intake
    html = read(FORM_HTML)
    block = re.search(r"const QUESTIONS = \[(.*?)\n\];", html, re.S)
    assert block, "the generated questionnaire block is gone"

    keys = re.findall(r'^\s*\["([a-z_]+)"', block.group(1), re.M)
    assert keys == [q[0] for q in intake.QUESTIONS], (
        "the browser questionnaire has drifted from intake.py -- "
        "run tools/build_web.py")


def test_separation_date_is_asked_but_never_written_to_a_form():
    """It exists to work out deadlines. It is not a field on either form,
    and it must not quietly become one."""
    import intake
    assert "separation_date" in [q[0] for q in intake.QUESTIONS]
    for mapping in (intake.DD_TEXT_FIELDS,
                    getattr(intake, "SHA_TEXT_FIELDS", {})):
        assert "separation_date" not in mapping
