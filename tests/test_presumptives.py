"""
Presumptive service connection.

A presumption removes the need to argue that a condition is connected to
service. It is the biggest shortcut in the system and it turns entirely on
a question the questionnaire never used to ask: where.

These tests cover three things -- that the overlap is found, that the tool
never claims eligibility it cannot determine, and that the list carries its
own age. The last one matters most over time: a stale presumptive list is
worse than no list, because it reads as authoritative.
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
import presumptives as pres  # noqa: E402


def cond(code, name, page=1, **kw):
    d = {"icd10": code, "condition": name, "source_page": page}
    d.update(kw)
    return d


RHINITIS = cond("J30.9", "Allergic rhinitis", 5)
SINUSITIS = cond("J32.9", "Chronic sinusitis", 6)
DIABETES = cond("E11.9", "Type 2 diabetes", 9)
LUMBAGO = cond("M54.5", "Lumbago", 12)
PARKINSONS = cond("G20", "Parkinson's disease", 20)


# ------------------------------------------------------ finding the overlap

def test_burn_pit_service_plus_a_respiratory_condition_lines_up():
    got = pres.find([RHINITIS, SINUSITIS], ["swa", "burnpit"])
    assert got["matches"]
    m = got["matches"][0]
    assert "respiratory" in m["name"]
    assert "Allergic rhinitis" in m["because"]
    assert "PACT Act" in m["presumption"]


def test_vietnam_service_plus_diabetes_lines_up():
    got = pres.find([DIABETES], ["vietnam"])
    assert [m for m in got["matches"] if "herbicide" in m["name"]]


def test_lejeune_plus_parkinsons_lines_up():
    got = pres.find([PARKINSONS], ["lejeune"])
    assert [m for m in got["matches"] if "Lejeune" in m["name"]]


def test_an_unrelated_condition_does_not_line_up():
    got = pres.find([LUMBAGO], ["swa"])
    assert not got["matches"]


def test_exposure_with_no_match_is_still_reported_as_standing():
    """Presumptive lists grow. Service that happened already still counts
    for a condition that appears years from now, so an exposure with no
    current match is not nothing."""
    got = pres.find([LUMBAGO], ["lejeune"])
    assert not got["matches"]
    assert [s for s in got["standing"] if s["id"] == "lejeune"]


def test_nothing_ticked_produces_nothing():
    for exposures in (None, [], ["not-a-real-id"]):
        got = pres.find([RHINITIS], exposures)
        assert got == {"matches": [], "standing": [], "exposures": []}
    assert pres.worksheet_section([RHINITIS], []) == ""
    assert package_bundle.format_presumptives([RHINITIS], []) == ""


def test_matched_exposures_are_not_also_listed_as_standing():
    got = pres.find([RHINITIS], ["swa", "burnpit"])
    matched = {e for m in got["matches"] for e in m["exposure"].split(", ")}
    assert matched
    assert not [s for s in got["standing"] if s["short"] in matched]


# --------------------------------------------- the claim it must not make

def test_it_never_tells_the_member_they_qualify():
    """Eligibility is VA's determination on a full record -- dates, unit,
    discharge, severity. This module reports an overlap and hands it over."""
    banned = re.compile(
        r"\byou qualify\b|\byou are eligible\b|\byou will (?:get|receive|be)\b|"
        r"\bguarantee|\bautomatically (?:granted|approved)\b|\bentitled to\b",
        re.I)
    blobs = [pres.HEADLINE, pres.DISCLAIMER, pres.FRESHNESS]
    blobs += [r["presumption"] for r in pres.RULES]
    blobs += [e["label"] for e in pres.EXPOSURES]
    blobs.append(pres.worksheet_section([RHINITIS, DIABETES], ["swa", "vietnam"]))
    for text in blobs:
        hit = banned.search(text)
        assert not hit, f"claims eligibility: {hit.group(0)!r}"


def test_the_disclaimer_names_who_actually_decides():
    text = pres.worksheet_section([RHINITIS], ["swa"])
    assert "VA's determination" in text
    assert "VSO" in text


def test_the_module_cannot_write_to_a_form():
    src = inspect.getsource(pres)
    for forbidden in ("fill_forms", "target_field", "Proposal", "proposed_value"):
        assert forbidden not in src


def test_exposures_are_asked_but_never_written_to_a_form():
    assert "exposures" in [q[0] for q in intake.QUESTIONS]
    for mapping in (intake.DD_TEXT_FIELDS,
                    getattr(intake, "SHA_TEXT_FIELDS", {})):
        assert "exposures" not in mapping


# ------------------------------------------------------- staying honest

def test_the_list_carries_its_own_age():
    """A presumptive list compiled at a point in time and shown without a
    date reads as current. These change by statute."""
    assert re.fullmatch(r"\d{4}-\d{2}", pres.REVIEWED)
    assert pres.REVIEWED in pres.FRESHNESS
    assert pres.VA_SOURCE.startswith("https://www.va.gov/")
    assert pres.VA_SOURCE in pres.FRESHNESS


def test_the_review_date_is_shown_in_the_browser_too():
    html = open(os.path.join(REPO, "docs", "app", "index.html"),
                encoding="utf-8").read()
    year = pres.REVIEWED.split("-")[0]
    assert "PRESUMPTIVE_REVIEWED" in html
    assert year in re.search(
        r'PRESUMPTIVE_REVIEWED = "([^"]+)"', html).group(1)


def test_the_freshness_note_reaches_the_worksheet_and_readme():
    ws = pres.worksheet_section([RHINITIS], ["swa"])
    rd = package_bundle.format_presumptives([RHINITIS], ["swa"])
    for text in (ws, rd):
        assert pres.VA_SOURCE in text


# --------------------------------------------------------- well-formed

@pytest.mark.parametrize("exposure", pres.EXPOSURES, ids=lambda e: e["id"])
def test_every_exposure_is_well_formed(exposure):
    assert exposure["id"] and exposure["label"] and exposure["short"]
    assert len(exposure["label"]) < 200


@pytest.mark.parametrize("rule", pres.RULES, ids=lambda r: r["id"])
def test_every_rule_points_at_real_exposures(rule):
    assert rule["exposures"]
    for e in rule["exposures"]:
        assert e in pres.EXPOSURE_IDS, f"{rule['id']} names unknown exposure {e}"
    assert callable(rule["match"])
    for junk in ("", None, "junk", "12345"):
        assert rule["match"](junk) in (True, False)


def test_presumptives_lead_the_readme_ahead_of_secondary_questions():
    """A presumption removes the need to argue the connection at all, which
    outranks a question about how two conditions relate."""
    readme = package_bundle.render_readme(
        member_name="DOE, J", conditions=[RHINITIS, DIABETES],
        exposures=["swa", "vietnam"])
    assert "PRESUMPTIVE" in readme
    assert readme.index("PRESUMPTIVE") < readme.index("Ask about")
