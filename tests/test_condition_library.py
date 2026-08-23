"""
The condition library must not put a wrong answer on a federal form.

DD 2807-1 carries a five-year false-statement warning, so the tier that
pre-checks boxes (high/medium confidence) is held to zero false positives
against the one real completed form available as ground truth. The weak tier
may over-reach, because it defaults to "Leave blank".

The specific cases pinned below were all real false positives found by
running the library against real records.
"""

import os
import sys

import pytest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)

import condition_library as cl  # noqa: E402


def items(code, birth_sex="Male", tiers=("high", "medium", "low")):
    return {f"{i}{l}" for i, l, _, _, conf in cl.match(code, birth_sex)
            if i and conf in tiers}


# ------------------------------------------------- false positives, fixed

def test_sore_throat_is_not_chest_pain():
    """R07.0 is 'pain in throat'; R07.1-R07.9 are chest. The whole-R07
    prefix proposed a chest-pain answer for a sore throat."""
    assert "16c" not in items("R07.0")
    assert "11d" in items("R07.0")
    assert "16c" in items("R07.9")


def test_nicotine_is_not_an_illegal_drug():
    """F17 sits inside F11-F19 but is neither an illegal drug nor
    prescription abuse."""
    assert "17i" not in items("F17.200")
    assert "17i" in items("F11.20"), "genuine substance codes must still match"


def test_acute_symptoms_never_reach_the_prechecked_tier():
    """A single cough is not 'a chronic cough'; one diarrhea encounter is not
    'intestinal trouble'. Both were pre-checking a Yes."""
    strong = ("high", "medium")
    assert "10i" not in items("R05", tiers=strong)
    assert "13b" not in items("R19.7", tiers=strong)
    # still surfaced, just defaulted to blank
    assert "10i" in items("R05")
    assert "13b" in items("R19.7")


def test_ear_pain_reaches_a_question():
    """H92 fell between the hearing-loss and ENT ranges and matched nothing."""
    assert "11d" in items("H92.09")


# --------------------------------------------------------- generalisation

@pytest.mark.parametrize("code,expected", [
    ("M54.5", "12c"), ("M54.50", "12c"), ("M54.9", "12c"),   # any dorsalgia
    ("M25.561", "12i"), ("M25.562", "12i"),                   # either knee
    ("F32.0", "17f"), ("F33.9", "17f"),                       # any depression
    ("F41.1", "17a"), ("F41.9", "17a"),                       # any anxiety
    ("J45.20", "10d"), ("J45.909", "10d"),                    # any asthma
    ("G43.109", "15b"), ("G44.209", "15b"),                   # any headache
    ("I10", "16f"), ("I15.0", "16f"),                         # hypertension
    ("K21.9", "13a"), ("K21.00", "13a"),                      # GERD
])
def test_ranges_generalise_across_subclasses(code, expected):
    """The point of the library: a veteran whose code differs by a subclass
    from anything hand-written still gets a proposal."""
    assert expected in items(code), f"{code} should reach {expected}"


def test_female_only_items_are_gated_on_birth_sex():
    assert items("N92.0", "Female"), "should match for a female member"
    assert not items("N92.0", "Male"), "must never propose item 18 otherwise"


def test_every_sha_slug_resolves_against_the_live_form():
    """A slug that stops resolving means the form changed. That must fail
    loudly rather than silently dropping the mapping."""
    import json
    path = os.path.join(REPO, "field_names_sha.json")
    names = list(json.load(open(path)).keys())
    resolved, unresolved = cl.resolve_sha_fields(names)
    assert not unresolved, f"unresolved SHA slugs: {unresolved}"
    assert len(resolved) == len(cl.SHA_SLUGS)


def test_unknown_and_malformed_codes_do_not_crash():
    for code in (None, "", "not-a-code", "ZZZ", "12345", "U07.1"):
        cl.match(code)


# ------------------------------------------------------ ground-truth check

REAL_YES = set("""10j 11c 11d 11f 11g 12a 12c 12f 12g 12h 12i 12k 12l 12n 13a
14b 14c 14d 15b 16f 17a 17c 17d 17e 17f 17g 17i 20 21 22 23 24""".split())


def test_prechecked_tier_has_no_false_positives_on_real_records():
    """Measured against a real completed DD 2807-1. If this ever fails, a
    rule is proposing a Yes the member did not give."""
    import json
    path = os.path.join(REPO, "conditions.json")
    if not os.path.exists(path):
        pytest.skip("real records not present (gitignored, by design)")

    conditions = json.load(open(path))["clinical"]
    strong = set()
    for c in conditions:
        strong |= items(c["icd10"], "Male", tiers=("high", "medium"))

    false_positives = strong - REAL_YES
    assert not false_positives, (
        f"pre-checked tier would put these on the form, but the member "
        f"answered No: {sorted(false_positives)}")
