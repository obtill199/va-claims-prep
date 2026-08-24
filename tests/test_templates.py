"""
Every template must parse, and none may leak internals to the member.

Written after two real failures:
  - A find/replace on review.html matched the inner {% endfor %} of a nested
    loop, leaving an unbalanced block. Jinja compiles templates lazily, so
    nothing failed until the page was actually rendered — at the end of a
    multi-minute OCR run.
  - Proposal text carried "via field_map.py rule for F90.0" and raw AcroForm
    field names into the UI. Module names and PDF field paths are debugging
    detail; a member reviewing a medical form should never see them.
"""

import os
import sys

import pytest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
TEMPLATES = os.path.join(REPO, "app", "templates")

jinja2 = pytest.importorskip("jinja2")

TEMPLATE_NAMES = sorted(
    f for f in os.listdir(TEMPLATES) if f.endswith(".html")
)


@pytest.mark.parametrize("name", TEMPLATE_NAMES)
def test_template_compiles(name):
    env = jinja2.Environment(loader=jinja2.FileSystemLoader(TEMPLATES))
    env.get_template(name)   # raises TemplateSyntaxError on unbalanced blocks


LEAKY = ["field_map.py", "proposals.py", "extract_conditions.py",
         "AcroForm", "form1[0]", "condition_ref", "RULES["]


@pytest.mark.parametrize("name", TEMPLATE_NAMES)
def test_template_shows_no_internals(name):
    body = open(os.path.join(TEMPLATES, name), encoding="utf-8").read()
    found = [t for t in LEAKY if t in body]
    assert not found, f"{name} would render internal detail: {found}"


def test_proposal_rationales_are_human_readable():
    """No module names, rule keys, or filenames in text the member reads."""
    import json
    path = os.path.join(REPO, "proposals.json")
    if not os.path.exists(path):
        pytest.skip("no proposals.json on this machine (gitignored)")
    banned = ["field_map", ".py", "target_field", "AcroForm", ".pdf", "RULES"]
    for p in json.load(open(path, encoding="utf-8")):
        for token in banned:
            assert token not in p["rationale"], (
                f"proposal {p['id']} rationale leaks {token!r}: {p['rationale'][:80]}")
        assert p.get("question_text"), "every proposal needs the form's own question text"
