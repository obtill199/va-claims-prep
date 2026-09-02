# Copyright (c) 2026 Oliver Tillinghast.
# Licensed under the PolyForm Noncommercial License 1.0.0.
# Free for veterans, VSOs, nonprofits and government. Commercial use
# requires a separate licence -- see LICENSE, NOTICE.md, COMMERCIAL.md.
"""
How hard the tool is to read.

The audience is not a general one. It includes people with traumatic brain
injury, people reading on a phone in a parking lot, people who are tired
and stressed and doing this because they have to be. Plain-language
guidance for federal health material lands around 6th-8th grade, and
VA.gov targets the same. Prose written at college level is a barrier
dressed up as thoroughness.

Reading level drifts upward on its own. Every clarification adds a clause,
every caveat adds a subordinate, and nobody notices until the review screen
reads like a policy memo. These tests make the drift fail the build.
"""

import os
import sys

import pytest
from conftest import REPO

sys.path.insert(0, os.path.join(REPO, "tools"))

import readability

# The step screens are what a member reads while making decisions, so they
# are held tighter than the reference pages.
STEP_LIMIT = 8.0
PAGE_LIMIT = 9.0


def measured():
    return {label: readability.grade(text)
            for label, text in readability.screens()}


@pytest.mark.parametrize("label", [s[0] for s in readability.screens()])
def test_every_screen_is_readable(label):
    text = dict(readability.screens())[label]
    fk, words, sents = readability.grade(text)
    assert fk is not None, f"{label} has no measurable prose"
    limit = STEP_LIMIT if label[0].isdigit() else PAGE_LIMIT
    assert fk <= limit, (
        f"{label} reads at grade {fk} (limit {limit}). Shorter sentences and "
        f"commoner words -- not fewer facts.")


def test_the_review_screen_is_the_plainest_of_all():
    """The screen where somebody decides what goes on a sworn form. If any
    screen has to be readable when tired, it is this one."""
    fk, _w, _s = dict(measured())["4 Review"]
    assert fk <= 6.0, f"the review screen reads at grade {fk}"


def test_no_unexplained_jargon_reaches_a_member():
    """A word that is precise internally and opaque to a member is a word
    that stops them. Specialist terms are allowed where they are explained
    -- "presumptive" is VA's own vocabulary and they will meet it again."""
    GLOSSED = {
        "presumptive": ("without you having to prove", "without having to prove"),
        "secondary service connection": ("caused or made worse", "caused by"),
    }
    offenders = []
    for label, text in readability.screens():
        low = text.lower()
        for term in readability.JARGON:
            if term.lower() not in low:
                continue
            gloss = GLOSSED.get(term.lower())
            if gloss and any(g in low for g in gloss):
                continue
            offenders.append(f"{label}: {term}")
    assert not offenders, (
        "unexplained jargon on a member-facing screen: " + "; ".join(offenders))


def test_the_word_proposal_never_reaches_a_member():
    """Internally these are proposals and the code says so. To somebody
    filing a claim it is a word that explains nothing about what they are
    being asked to do."""
    for label, text in readability.screens():
        assert "proposal" not in text.lower(), (
            f"{label} shows the member the word 'proposal'")


def test_the_false_statement_warning_stays_short():
    """The one paragraph that must land. A long sentence about a federal
    penalty is a sentence people skim."""
    text = dict(readability.screens())["4 Review"]
    warned = [s for s in readability.sentences_of(text)
              if "federal" in s.lower() or "prison" in s.lower()]
    assert warned, "the false-statement warning is gone from the review screen"
    for s in warned:
        assert len(s.split()) <= 26, f"warning sentence is {len(s.split())} words: {s}"


def test_spelling_is_american():
    """This is a tool for US veterans, filling US federal forms. British
    spelling on a page about legal terms reads as though it were written
    for somewhere else -- which, on a page whose whole job is to say who
    this is for and what it is not, is the wrong impression to give."""
    import glob
    import re

    BRITISH = [
        r"\blicence", r"\boffence", r"\borganis", r"\bsummaris",
        r"\brecognised\b", r"\banalys[ei]", r"\bbehaviour", r"\bcolour",
        r"\bdefence\b", r"\bcentre\b", r"\bprogramme\b", r"\bapologis",
        r"\bprioritis", r"\bminimis", r"\butilis", r"\brealis",
    ]
    # User-facing only. Developer documentation (CLAUDE.md, ARCHITECTURE.md,
    # CONTRIBUTING.md) legitimately quotes identifiers and the old names of
    # renamed symbols, and a veteran never reads it.
    USER_FACING_MD = ("README.md", "NOTICE.md", "COMMERCIAL.md",
                      "LICENSE-HISTORY.md")
    targets = (glob.glob(os.path.join(REPO, "docs", "*.html"))
               + glob.glob(os.path.join(REPO, "docs", "*", "index.html"))
               + [os.path.join(REPO, n) for n in USER_FACING_MD
                  if os.path.exists(os.path.join(REPO, n))])
    offenders = []
    for path in targets:
        text = open(path, encoding="utf-8").read()
        for pattern in BRITISH:
            for hit in re.findall(pattern, text, re.I):
                offenders.append(f"{os.path.basename(path)}: {hit}")
    assert not offenders, "British spelling in user-facing text: " + \
        "; ".join(sorted(set(offenders)))
