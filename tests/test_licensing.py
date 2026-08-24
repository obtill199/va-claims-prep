# Copyright (c) 2026 Oliver Tillinghast.
# Licensed under the PolyForm Noncommercial License 1.0.0.
# Free for veterans, VSOs, nonprofits and government. Commercial use
# requires a separate licence -- see LICENSE, NOTICE.md, COMMERCIAL.md.
"""
The licence, kept consistent.

The project moved from MIT to PolyForm Noncommercial. A relicence is only
worth anything if it is applied everywhere and stays applied: one file left
carrying the old notice is exactly the ambiguity a copier would point at.

The published pages are part of this. The browser build serves its own
Python source to every visitor -- that is what running in the tab means --
so the licence header in those files is not decoration. For anyone reading
the code at the live URL, it is the only notice they will see.
"""

import glob
import os
import re

import pytest

from conftest import DISCLAIMER_HTML, FORM_HTML, HOME_HTML, REPO, read

LICENCE_NAME = "PolyForm Noncommercial License 1.0.0"
SOURCE_GLOBS = ["*.py", "app/*.py", "tools/*.py", "web/py/*.py",
                "hosted/*.py", "tests/*.py", "tests/e2e/*.py"]


def sources():
    out = []
    for pattern in SOURCE_GLOBS:
        out.extend(glob.glob(os.path.join(REPO, pattern)))
    return sorted(out)


# ------------------------------------------------------------- the licence

def test_the_licence_file_is_the_real_thing():
    """Verbatim, not paraphrased. A reworded licence is a licence nobody can
    rely on, including the person trying to enforce it."""
    text = read(os.path.join(REPO, "LICENSE"))
    assert LICENCE_NAME in text
    for section in ("Acceptance", "Copyright License", "Distribution License",
                    "Notices", "Changes and New Works License",
                    "Patent License", "Noncommercial Purposes",
                    "Personal Uses", "Noncommercial Organizations",
                    "Fair Use", "No Other Rights", "Patent Defense",
                    "Violations", "No Liability", "Definitions"):
        assert section in text, f"LICENSE is missing the {section!r} section"


def test_the_licence_carries_a_required_notice():
    """PolyForm propagates any 'Required Notice:' line to every copy. It is
    the attribution hook, and it only works if it is there."""
    text = read(os.path.join(REPO, "LICENSE"))
    line = [l for l in text.splitlines() if l.startswith("Required Notice:")]
    assert line, "no Required Notice line, so copies carry no attribution"
    assert "Oliver Tillinghast" in line[0]


def test_every_source_file_carries_the_notice():
    missing = [os.path.relpath(p, REPO) for p in sources()
               if LICENCE_NAME not in read(p)]
    assert not missing, f"no licence header: {missing}"


def test_no_file_still_claims_to_be_mit():
    """The one thing that must not survive the change: a file that says MIT.
    LICENSE-HISTORY.md is the exception -- it exists to record the change."""
    allowed = {"LICENSE-HISTORY.md", "NOTICE.md", "README.md",
               "requirements.txt"}
    offenders = []
    for pattern in SOURCE_GLOBS + ["*.md"]:
        for path in glob.glob(os.path.join(REPO, pattern)):
            rel = os.path.relpath(path, REPO)
            if rel in allowed:
                continue
            body = read(path)
            if re.search(r"\bMIT License\b", body) or \
                    re.search(r"licen[sc]ed under.{0,20}\bMIT\b", body, re.I):
                offenders.append(rel)
    assert not offenders, f"still claim MIT: {offenders}"


# ------------------------------------------------- what the browser serves

def test_the_served_python_carries_the_notice():
    """The browser build ships its own source. Making the repository private
    would not hide it -- this header is the notice a reader actually gets."""
    from conftest import FORM_PY
    shipped = glob.glob(os.path.join(FORM_PY, "*.py"))
    assert shipped, "no modules in the browser build"
    for path in shipped:
        assert LICENCE_NAME in read(path), os.path.basename(path)


def test_the_disclaimer_page_tells_a_veteran_it_is_free_for_them():
    """A licence called 'Noncommercial' is not self-explanatory to somebody
    who just wants to file a claim. The page has to say so."""
    body = read(DISCLAIMER_HTML)
    assert "PolyForm" in body
    assert "NOTICE.md" in body, "no link to the plain-English terms"
    assert re.search(r"free for you|free, forever|accredited VSO", body), \
        "the page does not tell a veteran the tool is free for them"


# ------------------------------------------------------ the plain English

@pytest.mark.parametrize("name", ["NOTICE.md", "COMMERCIAL.md",
                                  "LICENSE-HISTORY.md", "CONTRIBUTING.md"])
def test_the_supporting_documents_exist(name):
    assert os.path.exists(os.path.join(REPO, name))


def test_the_history_is_recorded_honestly():
    """An MIT grant already given cannot be withdrawn. Saying so is both
    accurate and the thing that stops it becoming a dispute later."""
    text = read(os.path.join(REPO, "LICENSE-HISTORY.md"))
    assert "MIT" in text
    assert "irrevocable" in text.lower()


def test_the_notice_names_who_is_free_and_who_is_not():
    text = read(os.path.join(REPO, "NOTICE.md"))
    for who in ("veteran", "Veterans Service Officer", "nonprofit"):
        assert who.lower() in text.lower(), f"{who} not addressed"
    assert "5901" in text, "the accreditation limit on charging is not mentioned"


def test_contributing_takes_an_inbound_commercial_grant():
    """Without it every contributor holds a veto over the project's own
    licensing, and a commercial licence becomes impossible to offer."""
    text = read(os.path.join(REPO, "CONTRIBUTING.md"))
    assert "commercially" in text.lower()
