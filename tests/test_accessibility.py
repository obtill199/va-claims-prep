"""
Accessibility, checked rather than asserted.

The stylesheet has claimed AA conformance since the first commit and the
audience is explicitly stated to include people with visual, motor and
cognitive disabilities -- veterans with TBI, tremor, low vision. That
combination makes an unverified claim worse than no claim.

This is not a substitute for testing with a real screen reader, which this
project has not had. It catches the structural failures that are
mechanically detectable, which is the class that tends to creep back in
every time somebody adds a field.
"""

import os
import re
import sys

import pytest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)

PAGES = ["docs/index.html", "docs/app/index.html"]


def html(rel):
    return open(os.path.join(REPO, rel), encoding="utf-8").read()


def css():
    return open(os.path.join(REPO, "docs", "assets", "base.css"),
                encoding="utf-8").read()


# --------------------------------------------------------------- naming

@pytest.mark.parametrize("rel", PAGES)
def test_every_control_has_an_accessible_name(rel):
    """A control with no label is announced as "edit text, blank". On a form
    where a wrong answer carries a federal penalty, that is not survivable."""
    page = html(rel)
    labelled = set(re.findall(r'<label[^>]*\sfor="([^"]+)"', page))
    problems = []
    for m in re.finditer(r'<(input|select|textarea)\b([^>]*)>', page):
        attrs = m.group(2)
        if 'type="hidden"' in attrs:
            continue
        if "aria-label" in attrs:
            continue
        before = page[max(0, m.start() - 400):m.start()]
        if before.rfind("<label") > before.rfind("</label>"):
            continue  # nested inside its own label
        ident = re.search(r'\sid="([^"]+)"', attrs)
        if ident and ident.group(1) in labelled:
            continue
        problems.append(m.group(0)[:90])
    assert not problems, f"{rel}: controls with no accessible name: {problems}"


@pytest.mark.parametrize("rel", PAGES)
def test_no_label_points_at_a_field_that_does_not_exist(rel):
    """A `for=` with no matching id is a label that silently does nothing.
    One of these shipped: the SHA explanation boxes carried a <label> with
    no `for` at all, so every one of them was unnamed."""
    page = html(rel)
    ids = set(re.findall(r'\sid="([^"]+)"', page))
    # Template ids are built at runtime; skip anything interpolated.
    for target in re.findall(r'<label[^>]*\sfor="([^"${}]+)"', page):
        assert target in ids, f"{rel}: <label for={target}> matches no element"


@pytest.mark.parametrize("rel", PAGES)
def test_every_image_has_alt_text(rel):
    for tag in re.findall(r"<img\b[^>]*>", html(rel)):
        assert "alt=" in tag, f"{rel}: {tag[:80]}"


# ---------------------------------------------------------- orientation

@pytest.mark.parametrize("rel", PAGES)
def test_the_page_declares_a_language(rel):
    """Without it a screen reader may read English in another language's
    phoneme set, which is not merely awkward -- it is unintelligible."""
    assert re.search(r'<html[^>]*\slang="[a-z]{2}', html(rel)) or \
        "lang=" in html(rel)[:600], f"{rel} has no lang attribute"


@pytest.mark.parametrize("rel", PAGES)
def test_there_is_one_h1_per_visible_screen(rel):
    page = html(rel)
    if rel.endswith("app/index.html"):
        # One <h1> per step section; only one section is visible at a time.
        sections = re.findall(r'<section id="step-\d".*?</section>', page, re.S)
        assert sections
        for sec in sections:
            assert sec.count("<h1") == 1, "a step has zero or multiple h1"
    else:
        assert page.count("<h1") == 1


def test_a_skip_link_exists_on_the_app():
    assert "skip-link" in html("docs/app/index.html")


# ------------------------------------------------------ motor and vision

def test_focus_is_always_visible():
    """Keyboard users must be able to see where they are. Removing the
    outline without replacing it is the single most common a11y regression."""
    style = css()
    assert ":focus-visible" in style
    assert re.search(r":focus-visible\s*\{[^}]*outline:\s*\d", style), \
        "focus-visible exists but sets no visible outline"
    for block in re.findall(r"\{[^}]*\}", style):
        if "outline: none" in block or "outline:none" in block:
            assert "focus" not in block, "focus outline removed somewhere"


def test_hit_targets_are_large_enough_to_use_with_a_tremor():
    style = css()
    button = re.search(r"\.btn\s*\{([^}]*)\}", style)
    assert button and "min-height: 44px" in button.group(1), \
        "buttons must be at least 44px tall"
    row = re.search(r"\.checkrow\s*\{([^}]*)\}", style)
    assert row and "min-height: 44px" in row.group(1), \
        "tick-list rows must be at least 44px tall"


def test_reduced_motion_is_respected():
    assert "prefers-reduced-motion" in css()


def test_colour_is_never_the_only_signal():
    """Confidence tiers drive a colour AND a word. If the badge ever became
    a bare coloured dot, the whole review screen would stop working for a
    colour-blind user."""
    page = html("docs/app/index.html")
    assert "confidence</span>" in page or 'esc(g.confidence)' in page, \
        "the confidence badge no longer carries text"
