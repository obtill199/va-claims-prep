# Copyright (c) 2026 Oliver Tillinghast.
# Licensed under the PolyForm Noncommercial License 1.0.0.
# Free for veterans, VSOs, nonprofits and government. Commercial use
# requires a separate licence -- see LICENSE, NOTICE.md, COMMERCIAL.md.
"""
The conditions that are not in the records.

The extractor reads what a clinician wrote down, and that ceiling sits
exactly where the problem is: the conditions people go uncompensated for
are the ones nobody documented. This module asks the member directly,
which introduces a class of data the rest of the tool had never seen --
a condition with no dates, no encounters, no provider and no page.

Most of these tests exist because that shape broke something.
"""

import json
import os
import sys
import tempfile

import pytest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)

import condition_library as cl  # noqa: E402
import explanations  # noqa: E402
import field_map  # noqa: E402
import schema  # noqa: E402
import self_report as sr  # noqa: E402
from proposals import build_proposals  # noqa: E402


@pytest.fixture
def workdir(tmp_path, monkeypatch):
    for f in ("dd2807_crosswalk.json", "field_names_sha.json"):
        (tmp_path / f).write_text(open(os.path.join(REPO, f), encoding="utf-8").read())
    monkeypatch.chdir(tmp_path)
    return tmp_path


def propose(ids, free_text=None, extra=None, birth_sex="Male"):
    clinical = sr.to_conditions(ids, free_text) + list(extra or [])
    json.dump({"clinical": clinical, "administrative": []},
              open("conditions.json", "w", encoding="utf-8"))
    return build_proposals("conditions.json", "dd2807_crosswalk.json",
                           "field_names_sha.json", birth_sex=birth_sex)


# ------------------------------------------- the false-statement hazard

def test_a_symptom_never_answers_a_question_about_treatment(workdir):
    """The near-miss this whole guard exists for.

    "Nightmares, flashbacks, avoiding reminders" routes through F43.10,
    and the library maps that code to "Received counseling of any type"
    and "Been evaluated or treated for a mental condition". For a code
    lifted from a record that is sound -- a clinician put it there, so
    somebody did evaluate them. For a symptom the member typed it is
    false, and false in the worst direction: the reason these conditions
    go unclaimed is that people never sought help. Checking those boxes
    would assert, on a form carrying a five-year false-statement penalty,
    the one thing that did not happen.
    """
    treatment_questions = [q for (_i, _l, _s, q, _c) in cl.match("F43.10", "Male")]
    assert treatment_questions, "fixture assumes F43.10 maps somewhere"
    assert any(not sr.answerable_from_self_report(q) for q in treatment_questions), \
        "fixture assumes at least one of them is a treatment-history question"

    proposals, _ = propose(["ptsd"])
    for p in proposals:
        assert sr.answerable_from_self_report(p.question_text), \
            f"a self-report reached {p.question_text!r}"


@pytest.mark.parametrize("question", [
    "Received counseling of any type",
    "Been evaluated or treated for a mental condition",
    "Have you consulted or been treated by clinics, physicians, healers",
    "Have you ever been treated in an Emergency Room? (If yes, for what?)",
    "Have you ever had, or have you been advised to have any operations or surgery?",
    "Any knee or foot surgery including arthroscopy",
    "Been prescribed or used an inhaler",
    "Attempted suicide",
])
def test_treatment_history_questions_are_all_recognised(question):
    assert not sr.answerable_from_self_report(question)


@pytest.mark.parametrize("question", [
    "Frequent or severe headache",
    "Recurrent back pain or any back problem",
    "A hearing loss or wear a hearing aid",
    "Nervous trouble of any sort (anxiety or panic attacks)",
    "Depression or excessive worry",
    "Severe tooth or gum trouble",
])
def test_symptom_questions_stay_answerable(question):
    assert sr.answerable_from_self_report(question)


def test_a_suppressed_self_report_still_reaches_the_worksheet(workdir):
    """Filtering must not equal discarding. If every form question for a
    self-report is a treatment question, the condition still has to land
    somewhere a VSO will see it -- dropping it silently would lose the one
    thing the member went out of their way to say."""
    proposals, unmapped = propose(["ptsd"])
    assert not proposals
    names = [c["condition"] for c in unmapped]
    assert any("Nightmares" in n for n in names)


def test_free_text_reaches_the_worksheet_too(workdir):
    _, unmapped = propose([], "Jaw clicking when I chew\nNight sweats")
    names = [c["condition"] for c in unmapped]
    assert "Jaw clicking when I chew" in names
    assert "Night sweats" in names


# --------------------------------------------------------- the new tier

def test_self_reports_carry_their_own_tier(workdir):
    proposals, _ = propose(["tinnitus"])
    assert proposals
    assert {p.confidence for p in proposals} == {"self-reported"}


def test_the_tier_is_valid_and_ordered(workdir):
    assert "self-reported" in schema.VALID_CONFIDENCE
    # Not a weak reading of a record -- a statement from the person who knows.
    assert schema.confidence_rank("self-reported") == schema.confidence_rank("high")
    assert schema.confidence_rank("self-reported") < schema.confidence_rank("low")


def test_confidence_rank_never_raises_on_an_unknown_tier():
    """Three modules each kept their own copy of this ordering, and adding a
    fourth tier broke two of them with a KeyError at runtime."""
    assert schema.confidence_rank("something-new") >= len(schema.CONFIDENCE_ORDER)


def test_the_rationale_does_not_report_zero_encounters(workdir):
    """"0 documented encounters" reads as a weak finding rather than as the
    member speaking."""
    proposals, _ = propose(["tinnitus"])
    for p in proposals:
        assert "0 documented" not in p.rationale
        assert "encounter" not in p.rationale.lower()
        assert p.source_page is None


# ------------------------------------- the shape that broke things

def test_a_condition_with_no_dates_does_not_break_record_level_rules(workdir):
    """_treated_within_5_years compared None to a string and took down the
    whole review. It must also not COUNT a self-report: "have you been
    treated in five years" is a question about treatment, and a member
    saying their back hurts is not evidence anyone treated it."""
    documented = {
        "condition": "Lumbago", "icd10": "M54.5", "body_system": "Musculoskeletal",
        "first_seen": "2019-04-02", "last_seen": "2023-01-10", "encounters": 4,
        "active": True, "on_problem_list": True, "providers": [],
        "administrative": False, "source_document": "r.pdf", "source_page": 12,
    }
    proposals, _ = propose(["back", "teeth"], extra=[documented])
    assert proposals  # did not raise

    only_self = sr.to_conditions(["back"], None)
    assert field_map._documented(only_self) == []


def test_explanations_handle_a_condition_with_no_dates():
    """Sorting by first_seen raised TypeError inside a lambda, which surfaced
    as Item 29 coming back empty with no error shown to anyone."""
    line = explanations._condition_sentence(sr.to_conditions(["teeth"], None)[0])
    assert "Reported by me" in line
    assert "None" not in line
    assert explanations.DATES_PROMPT in line


def test_undated_conditions_sort_after_dated_ones():
    dated = {"first_seen": "2019-04-02"}
    undated = {"first_seen": None}
    assert explanations._chronological(dated) < explanations._chronological(undated)


# ------------------------------------------------------ the catalog

def test_every_catalog_code_the_library_should_match_does():
    """A code that matches nothing means a prompt that silently reaches no
    form question. That is allowed -- some have no item -- but it must be
    deliberate, marked by a None code rather than a code that misses."""
    for _group, items in sr.CATALOG:
        for (ident, label, code, _hint) in items:
            if code is None:
                continue
            assert cl.match(code, "Male") or cl.match(code, "Female"), \
                f"{ident} carries {code}, which maps to no form question"


def test_catalog_ids_are_unique():
    ids = [i for _g, items in sr.CATALOG for (i, _l, _c, _h) in items]
    assert len(ids) == len(set(ids))


def test_the_catalog_never_leaks_a_code_to_the_ui():
    blob = json.dumps(sr.catalog())
    for _group, items in sr.CATALOG:
        for (_i, _l, code, _h) in items:
            if code:
                assert code not in blob


def test_free_text_is_bounded_and_deduplicated():
    many = "\n".join(f"thing {i}" for i in range(100))
    assert len(sr._split_free_text(many)) <= 25
    assert len(sr._split_free_text("Back pain\nback pain\nBACK PAIN")) == 1
    assert sr._split_free_text("  \n-\n..\n") == []
    assert sr._split_free_text(None) == []


def test_free_text_survives_a_paste_of_semicolons():
    got = sr._split_free_text("jaw clicking; night sweats; ringing")
    assert len(got) == 3


# --------------------------------------------------- buddy letters

def test_self_reported_conditions_get_a_letter_even_with_no_form_question():
    """These are what buddy letters are FOR. The tool used to generate them
    only for conditions already in the record -- the ones that need a lay
    statement least, since a clinician already wrote them down."""
    from buddy_letter import write_letters
    conds = sr.to_conditions(["ptsd"], "Jaw clicking")
    conds.append({"condition": "Lumbago", "icd10": "M54.5",
                  "first_seen": "2019-04-02", "last_seen": "2023-01-10",
                  "encounters": 4, "self_reported": False})
    with tempfile.TemporaryDirectory() as d:
        paths = [os.path.basename(p) for p in write_letters("DOE, J", conds, d)]
    needed = [p for p in paths if "NEEDED_" in p]
    assert len(needed) == 2, paths
    assert not any("NEEDED_" in p and "Lumbago" in p for p in paths)


def test_the_self_reported_letter_says_why_it_matters():
    from docx import Document
    from buddy_letter import build_letter
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, "l.docx")
        build_letter("DOE, J", sr.to_conditions(["teeth"], None)[0]).save(p)
        text = "\n".join(x.text for x in Document(p).paragraphs)
    assert "no medical record" in text
    assert "matters more" in text
