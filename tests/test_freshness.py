"""
The parts of this tool that go stale on a calendar.

Three of its data sets are not code and do not rot visibly:

  presumptive lists are law, and change by statute
  ICD-10-CM is revised every 1 October
  the vendored forms get new editions, which rename AcroForm fields

None of those announce themselves. A presumptive list compiled once and
shown undated reads as current, which is worse than showing nothing --
it is wrong with authority. The forms are worse still: a renamed field
does not error, it just quietly stops being written.

These tests fail on a schedule. That is deliberate. A CI job that goes red
every October is the cheapest possible reminder to re-check a list that
people are making decisions from, and the alternative is finding out from
a veteran.
"""

import datetime
import os
import re
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)

import condition_library  # noqa: E402
import presumptives  # noqa: E402

# How long a data set may go unreviewed before this fails.
MAX_AGE_MONTHS = 12


def months_since(stamp):
    year, month = (int(x) for x in stamp.split("-")[:2])
    today = datetime.date.today()
    return (today.year - year) * 12 + (today.month - month)


def test_the_presumptive_list_has_been_reviewed_recently():
    age = months_since(presumptives.REVIEWED)
    assert age <= MAX_AGE_MONTHS, (
        f"presumptives.REVIEWED is {age} months old ({presumptives.REVIEWED}).\n"
        f"Presumptive lists change by statute and this one is shown to "
        f"members as current. Re-check against {presumptives.VA_SOURCE}, "
        f"then update REVIEWED.")


def test_the_condition_library_has_been_reviewed_recently():
    stamp = getattr(condition_library, "REVIEWED", None)
    assert stamp, "condition_library.REVIEWED is missing"
    age = months_since(stamp)
    assert age <= MAX_AGE_MONTHS, (
        f"condition_library.REVIEWED is {age} months old ({stamp}).\n"
        "ICD-10-CM is revised every 1 October. Codes are added, deleted and "
        "reassigned; a deleted code silently stops matching. Re-check the "
        "range rules, then update REVIEWED.")


def test_review_stamps_are_well_formed_and_not_in_the_future():
    today = datetime.date.today().strftime("%Y-%m")
    for name, stamp in [("presumptives", presumptives.REVIEWED),
                        ("condition_library", condition_library.REVIEWED)]:
        assert re.fullmatch(r"\d{4}-\d{2}", stamp), f"{name}: {stamp!r}"
        assert stamp <= today, f"{name} claims to have been reviewed in the future"


def test_the_forms_are_pinned():
    """Covered in detail by test_repo_hygiene; asserted here too so the
    freshness story is in one place."""
    pinned = os.path.join(REPO, "forms", "FORM_VERSIONS.txt")
    assert os.path.exists(pinned)
    entries = [l for l in open(pinned, encoding="utf-8")
               if l.strip() and not l.startswith("#")]
    assert len(entries) >= 2, "both forms should be pinned"
