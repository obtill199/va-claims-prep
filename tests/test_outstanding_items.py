# Copyright (c) 2026 Oliver Tillinghast.
# Licensed under the PolyForm Noncommercial License 1.0.0.
# Free for veterans, VSOs, nonprofits and government. Commercial use
# requires a separate licence -- see LICENSE, NOTICE.md, COMMERCIAL.md.
"""
The package tells the member what is still unfinished. Three separate places
name the same placeholder string, and two name the same six blank fields:

  explanations.py   writes  "[Add treatment received]" into Item 29
  docs/form/...     counts  that exact string, and counts it down live
  package_bundle.py tells   the member to search for it in the README

If the wording in one drifts, the other two point at nothing -- and the
failure is silent: the member reads "replace every [Add treatment received]",
searches the form, finds none, and hands over an incomplete DD 2807-1
believing it is done. These tests exist to make that drift loud.
"""

import json
import os
import re
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)

import explanations  # noqa: E402
import intake  # noqa: E402
import package_bundle  # noqa: E402

from conftest import FORM_HTML as APP  # noqa: E402


def app_html():
    return open(APP, encoding="utf-8").read()


# ------------------------------------------------- the placeholder string

def test_readme_names_the_placeholder_explanations_actually_writes():
    assert explanations.TREATMENT_PROMPT in package_bundle.README


def all_prompts():
    """Every "[Add ...]" marker explanations.py can put on a form."""
    return [v for k, v in vars(explanations).items()
            if k.endswith("_PROMPT") and isinstance(v, str) and v.startswith("[")]


def test_there_is_more_than_one_kind_of_prompt():
    """Guards the assumption the next test rests on. A second kind appeared
    the moment self-reported conditions did -- they carry no dates -- and a
    counter that knew about only one would read zero with markers still on
    the form."""
    assert len(all_prompts()) >= 2


def test_the_browser_app_counts_every_prompt_that_can_be_written():
    html = app_html()
    pattern = re.search(r"box\.value\.match\(/(.+?)/g\)", html)
    assert pattern, "the outstanding-items counter regex is gone"
    counter = re.compile(pattern.group(1).replace("\\\\", "\\"))
    for prompt in all_prompts():
        assert counter.search(prompt), (
            f"the app's counter does not match {prompt!r}; it would report "
            "zero while that marker is still on the form")


def test_the_app_tells_the_member_the_same_string_to_search_for():
    """The prose instruction and the regex must name the same thing."""
    html = app_html()
    # Stripped of the markup that bolds it mid-sentence.
    prose = re.sub(r"<[^>]+>", "", html)
    assert explanations.TREATMENT_PROMPT in prose


# --------------------------------------------------- the six blank fields

def test_readme_accounts_for_every_field_left_blank_by_design():
    """BLANK_BY_DESIGN is the source of truth for what the member must fill
    in by hand. The README's checklist claims a specific count -- if a field
    is added or removed, that count has to move with it."""
    boxes = sum(len(v) for v in intake.BLANK_BY_DESIGN.values())
    places = len(intake.BLANK_BY_DESIGN["DD2807-1"]) // 2 + 1  # SSN+DoD ID per place
    assert boxes == 8 and places == 4, (
        f"{boxes} boxes across {places} places are blank by design, but the "
        "README and the app both say eight across four; update all three together")
    assert "EIGHT boxes across FOUR places" in package_bundle.README
    # Matched on substance, not on line breaks: this assertion has broken
    # twice on rewording that changed nothing a member would notice.
    page = " ".join(app_html().split())
    assert "Eight boxes in four places" in page or \
           "eight boxes in four places" in page, \
        "the app no longer tells the member how many boxes to fill by hand"
    assert "eight boxes across four places" in page, \
        "the final checklist no longer says where the blanks are"


def test_readme_marks_the_package_as_unfinished_not_complete():
    """A member who reads 'here is your package' stops. The heading has to
    say the opposite."""
    assert "STILL TO DO" in package_bundle.README
    assert "NOT FINISHED" in package_bundle.README


def test_every_outstanding_item_is_a_checkbox():
    """The list is meant to be worked through, so each item is tickable."""
    section = package_bundle.README.split("STILL TO DO")[1].split("WHAT TO ASK")[0]
    items = re.findall(r"^\[ \] \d+\.", section, re.M)
    assert len(items) >= 5, f"expected a checklist, found {items}"


def test_the_signing_instruction_is_not_contradicted():
    """An earlier build told the member to sign on one screen and to wait for
    their VSO on the next. Only one of those can be on the page."""
    html = app_html()
    assert "unsigned by design — sign and date them" not in html
    assert "Do not sign anything yet" in html
