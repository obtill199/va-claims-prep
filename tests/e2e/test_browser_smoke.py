# Copyright (c) 2026 Oliver Tillinghast.
# Licensed under the PolyForm Noncommercial License 1.0.0.
# Free for veterans, VSOs, nonprofits and government. Commercial use
# requires a separate licence -- see LICENSE, NOTICE.md, COMMERCIAL.md.
"""
The flow, in an actual browser.

Everything else in this suite tests Python. What people use is a page that
loads a 15MB WebAssembly runtime from a CDN, writes fifteen modules into a
virtual filesystem, and runs the same Python there. Nothing in the unit
suite touches that seam, and three bugs have lived in it:

  boot() returned early while a boot was in flight, so the resume path ran
  against a Pyodide that existed but had no modules on its filesystem yet
  a syntax error in a browser-only module shipped green, because nothing
  outside Pyodide imports it
  cached modules from a previous deploy ran against newer HTML

All three were found by hand. This is the automated version.

It also walks the site's own navigation: bare address to /disclaimer, on to
/home, on to /form, plus the /app/ redirect that keeps a link already sent
to a real person working. That chain broke the first time these pages moved,
and nothing outside a browser would have noticed.

It walks the whole flow with a synthetic record and asserts what is on
screen at every step. That part exists because the smoke test alone was not
enough: it stopped at "the engine boots", so a rename that left step 3
rendering an empty checklist survived a week in production with 365 tests
passing. Reaching a screen proves nothing. What has to be checked is that
the screen has content.

The walk is expensive -- Pyodide boot plus extraction is most of two
minutes -- so it runs once per module and snapshots each step. Assertions
are then cheap and can be added freely.

    pip install playwright && playwright install chromium
    pytest tests/e2e -q
"""

import http.server
import os
import socketserver
import sys
import threading

import pytest

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DOCS = os.path.join(REPO, "docs")

pytest.importorskip("playwright.sync_api",
                    reason="playwright not installed; e2e is opt-in")
from playwright.sync_api import sync_playwright  # noqa: E402

# Pyodide boots from vendored files now, but slow runners exist.
BOOT_TIMEOUT_MS = 180_000
# Extraction over the synthetic record, plus building the package.
WORK_TIMEOUT_MS = 120_000

SAMPLE_RECORD = os.path.join(REPO, "tools", "sample_record.pdf")


def _launch(pw):
    """Prefer the bundled Chromium; fall back to an installed Chrome.

    Playwright's headless shell and its driver can disagree about versions
    after an upgrade, which fails at launch rather than at install. A
    machine with Chrome should not lose its e2e coverage to that.
    """
    try:
        return pw.chromium.launch()
    except Exception:
        return pw.chromium.launch(channel="chrome")


@pytest.fixture(scope="module")
def server():
    def handler(*a, **k):
        return http.server.SimpleHTTPRequestHandler(*a, directory=DOCS, **k)
    with socketserver.TCPServer(("127.0.0.1", 0), handler) as httpd:
        port = httpd.server_address[1]
        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        thread.start()
        yield f"http://127.0.0.1:{port}"
        httpd.shutdown()


@pytest.fixture(scope="module")
def browser():
    """One browser for the module.

    The sync API allows a single active context per thread, so every fixture
    that needs a page shares this one. Two fixtures each opening their own
    sync_playwright() passes in isolation and fails the moment both are used
    in the same run -- which is how it presented.
    """
    with sync_playwright() as pw:
        try:
            b = _launch(pw)
        except Exception as exc:
            # Playwright installed but no browser downloaded. Skipping is the
            # honest outcome; launching hangs, which is a worse way to learn.
            pytest.skip(f"no Chromium available: {exc}")
        yield b
        b.close()


@pytest.fixture(scope="module")
def page(browser, server):
    pg = browser.new_page()
    errors = []
    pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.goto(f"{server}/form/index.html")
    pg.errors = errors
    yield pg
    pg.close()


def test_the_bare_address_lands_on_the_disclaimer(page, server):
    """Nobody should arrive straight in a medical form without knowing whose
    site it is. The redirect is a meta refresh, not JavaScript, so it also
    works with scripting off -- but this checks the path people take."""
    page.goto(f"{server}/")
    page.wait_for_url("**/disclaimer/**", timeout=30_000)
    assert "Before you start" in page.inner_text("h1")


def test_the_disclaimer_says_the_four_things(page, server):
    page.goto(f"{server}/disclaimer/")
    text = page.inner_text("main")
    assert "not a VA website" in text
    assert "never leave your computer" in text
    assert "SSN and DoD ID are never asked for" in text
    assert "false-statement" in text


def test_the_independence_notice_is_on_every_page(page, server):
    """The one claim that must never be missable, so it lives in the masthead
    rather than in a block that can be scrolled past or dismissed."""
    for path in ("disclaimer/", "home/", "form/"):
        page.goto(f"{server}/{path}")
        assert "not affiliated" in page.inner_text("body").lower(), path


def test_the_disclaimer_leads_to_home_and_home_leads_to_the_tool(page, server):
    page.goto(f"{server}/disclaimer/")
    page.click('a[href="../home/"]')
    page.wait_for_url("**/home/**", timeout=15_000)
    assert "Prepare your VA disability claim" in page.inner_text("h1")

    page.click('a[href="../form/"]')
    page.wait_for_url("**/form/**", timeout=15_000)
    assert "About you" in page.inner_text("h1")


def test_the_previously_shared_link_still_works(page, server):
    """/app/ was sent to a real person before the move."""
    page.goto(f"{server}/app/")
    page.wait_for_url("**/form/**", timeout=30_000)
    assert "About you" in page.inner_text("h1")


def test_the_tool_opens_on_the_questionnaire(page, server):
    page.goto(f"{server}/form/index.html")
    page.wait_for_selector("#step-1:not(.hidden)", timeout=30_000)
    assert page.locator("#f-full_name").is_visible()
    assert page.locator(".steps").is_visible()
    # For anyone who was sent this URL directly.
    assert page.locator('a[href="../disclaimer/"]').count() >= 1


def test_the_questionnaire_matches_the_python_source(page, server):
    """The JS QUESTIONS array is generated from intake.QUESTIONS. It used to
    be a hand-kept copy, which is how a question came to be asked everywhere
    except the page people use."""
    page.goto(f"{server}/form/index.html")
    page.wait_for_selector("#step-1:not(.hidden)", timeout=30_000)
    sys.path.insert(0, REPO)
    import intake
    for key, _label, _kind, _opts, _help in intake.QUESTIONS:
        assert page.locator(f"#f-{key}").count() == 1, \
            f"{key} is in intake.QUESTIONS but not on the page"


def test_the_engine_boots_and_enables_processing(page, server):
    """The seam nothing else tests: Pyodide up, modules on its filesystem,
    web_pipeline imported. A stale or broken module fails here."""
    page.goto(f"{server}/form/index.html")
    page.wait_for_selector("#step-1:not(.hidden)", timeout=30_000)
    page.fill("#f-full_name", "DOE, JOHN A")
    page.select_option("#f-branch", "Air Force")
    page.select_option("#f-component", "Regular")
    page.select_option("#f-purpose", "Separation")
    page.click("#to-upload")
    page.wait_for_selector("#step-2:not(.hidden)", timeout=10_000)

    # Enabled only after every module is written and imported.
    page.wait_for_function(
        "() => document.getElementById('process') && "
        "!document.getElementById('process').disabled",
        timeout=BOOT_TIMEOUT_MS)

    boot = page.inner_text("#boot") if page.locator("#boot").is_visible() else ""
    assert "could not load" not in boot, boot[:400]


def test_no_page_raised_a_javascript_error(page):
    assert not page.errors, "uncaught JS errors: " + "; ".join(page.errors[:5])


# ===========================================================================
# The full walk
#
# Everything above proves the pages load and the engine starts. That was the
# whole suite when self_report.summarise was renamed on one side of the
# JS/Python boundary: step 3 rendered an empty checklist in production for a
# week, and 365 tests passed the entire time, because nothing ever reached
# that screen with a record behind it.
#
# One walk, snapshotted. Assertions below are cheap.
# ===========================================================================

@pytest.fixture(scope="module")
def walked(browser, server):
    """Drive the entire flow once with a synthetic record.

    Returns a dict of snapshots taken at each step, plus the live page at
    step 6 for tests that need to interact further.
    """
    if not os.path.exists(SAMPLE_RECORD):
        pytest.skip("tools/sample_record.pdf missing; run tools/make_sample_record.py")

    pg = browser.new_page(viewport={"width": 1280, "height": 900})
    errors = []
    pg.on("pageerror", lambda e: errors.append(str(e)))
    snap = {"errors": errors}

    pg.goto(f"{server}/form/index.html")
    pg.wait_for_selector("#step-1:not(.hidden)", timeout=30_000)

    pg.fill("#f-full_name", "DOE, JOHN A")
    for field, value in (("branch", "Air Force"), ("component", "Regular"),
                         ("duty_status", "Active Component"),
                         ("purpose", "Separation"), ("birth_sex", "Male")):
        pg.select_option(f"#f-{field}", value)
    pg.click("#to-upload")

    # Enabled only once every module is on the Pyodide filesystem.
    pg.wait_for_function(
        "() => document.getElementById('process') && "
        "!document.getElementById('process').disabled",
        timeout=BOOT_TIMEOUT_MS)

    pg.set_input_files("#files", SAMPLE_RECORD)
    pg.click("#process")

    # ---- step 3: what is not in the records
    pg.wait_for_selector("#step-3:not(.hidden)", timeout=WORK_TIMEOUT_MS)
    pg.wait_for_selector("#sr-catalog fieldset", timeout=60_000)
    snap["step3"] = {
        "summary": pg.inner_text("#found-summary"),
        "groups": pg.locator("#sr-catalog fieldset").count(),
        "prompts": pg.locator("#sr-catalog input[type=checkbox]").count(),
        "free_text": pg.locator("#sr-other").count(),
    }

    pg.click("#skip-missing")

    # ---- step 4: review
    pg.wait_for_selector("#step-4:not(.hidden)", timeout=WORK_TIMEOUT_MS)
    pg.wait_for_selector(".proposal", timeout=60_000)
    first = pg.locator(".proposal").first
    snap["step4"] = {
        "proposals": pg.locator(".proposal").count(),
        "file_table": pg.inner_text("#file-table"),
        "warning": pg.inner_text("#step-4"),
        "first_card": first.inner_text(),
        "citations": pg.locator(".proposal__cite").count(),
        "leave_blank": pg.locator("input[type=radio][value=reject]").count(),
    }

    pg.click("#rv-confirm-strong")
    pg.click("#to-explain")

    # ---- step 5: explanations
    pg.wait_for_selector("#step-5:not(.hidden)", timeout=WORK_TIMEOUT_MS)
    pg.wait_for_function(
        "() => document.getElementById('item29').value.length > 50",
        timeout=60_000)
    snap["step5"] = {
        "item29": pg.input_value("#item29"),
        "todo": pg.inner_text("#item29-todo"),
    }

    pg.click("#to-package")

    # ---- step 6: the package
    pg.wait_for_selector("#step-6:not(.hidden)", timeout=WORK_TIMEOUT_MS)
    pg.wait_for_selector("#downloads a", timeout=WORK_TIMEOUT_MS)
    snap["step6"] = {
        "files": [pg.locator("#downloads a").nth(i).get_attribute("download")
                  for i in range(pg.locator("#downloads a").count())],
        "next_steps": pg.inner_text("#step-6"),
        "increase_rows": pg.locator("#increase-rows select").count(),
    }
    snap["page"] = pg

    yield snap
    pg.close()


# ------------------------------------------------------------------ step 3

def test_step_three_shows_what_the_records_found(walked):
    """The contrast is the point: a checklist with nothing in front of it is
    a quiz. This box was empty in production for a week."""
    summary = walked["step3"]["summary"]
    assert summary.strip(), "the found-summary box rendered empty"
    assert "condition" in summary.lower()


def test_step_three_renders_the_whole_catalog(walked):
    """The exact failure that shipped: the screen appeared, the checklist
    did not."""
    import self_report

    expected = sum(len(g["items"]) for g in self_report.catalog())
    assert walked["step3"]["prompts"] == expected, (
        f"{walked['step3']['prompts']} prompts on screen, "
        f"{expected} in self_report.CATALOG")
    assert walked["step3"]["groups"] == len(self_report.CATALOG)
    assert walked["step3"]["free_text"] == 1, "no free-text box for anything else"


# ------------------------------------------------------------------ step 4

def test_step_four_renders_proposals_from_the_record(walked):
    assert walked["step4"]["proposals"] > 0, "extraction produced no proposals"
    assert walked["step4"]["file_table"].strip(), "the file summary is empty"


def test_every_proposal_carries_a_citation(walked):
    """A proposal without provenance is a guess. The member has to be able
    to check it against their own record."""
    assert walked["step4"]["citations"] == walked["step4"]["proposals"]
    assert "page" in walked["step4"]["first_card"].lower() or \
           "told us" in walked["step4"]["first_card"].lower()


def test_the_false_statement_warning_is_on_the_review_screen(walked):
    text = walked["step4"]["warning"].lower()
    assert "sworn statement" in text
    assert "federal" in text


def test_leave_blank_is_offered_on_every_decision(walked):
    """Skipping a decision must leave the box empty rather than make a
    claim."""
    assert walked["step4"]["leave_blank"] == walked["step4"]["proposals"]


# ------------------------------------------------------------------ step 5

def test_step_five_drafts_item_29_from_the_record(walked):
    item29 = walked["step5"]["item29"]
    assert len(item29) > 100, "Item 29 draft is empty or trivial"
    assert "Item" in item29, "entries are not labelled with their form item"


def test_outstanding_placeholders_are_counted(walked):
    """The form asks for treatment the records do not state. Uncounted, a
    member could submit with the markers still in."""
    import re

    pending = len(re.findall(r"\[Add [^\]]+\]", walked["step5"]["item29"]))
    todo = walked["step5"]["todo"]
    if pending:
        assert todo.strip(), f"{pending} placeholders but no warning shown"
        assert str(pending) in todo, f"warning does not say how many: {todo[:80]}"
    else:
        assert not todo.strip()


# ------------------------------------------------------------------ step 6

def test_the_package_contains_what_it_promises(walked):
    files = walked["step6"]["files"]
    assert any(f and f.endswith("dd2807-1_FILLED.pdf") for f in files)
    assert any(f and "sha_part_a" in f for f in files)
    assert any(f and f == "conditions_worksheet.html" for f in files)
    assert any(f and f == "README.txt" for f in files)
    assert any(f and f.endswith(".rtf") for f in files), "no buddy letters"


def test_the_package_ships_no_markdown(walked):
    """Double-clicking a .md on a government desktop opens Notepad and shows
    pipe characters where a table should be."""
    md = [f for f in walked["step6"]["files"] if f and f.endswith(".md")]
    assert not md, f"markdown in the package: {md}"


def test_the_package_screen_says_what_happens_next(walked):
    text = walked["step6"]["next_steps"].lower()
    assert "do not sign" in text
    assert "vso" in text


def test_the_increase_panel_offers_every_coded_condition(walked):
    """Built and shipped without ever being opened in a browser. It happened
    to work."""
    assert walked["step6"]["increase_rows"] > 0, \
        "the increase panel rendered no rating selectors"


def test_the_increase_panel_builds_a_plan(walked):
    pg = walked["page"]
    pg.locator("#increase-block summary").click()
    pg.locator("#increase-rows select").first.select_option("10")
    pg.click("#increase-go")
    pg.wait_for_function(
        "() => document.getElementById('increase-status').textContent.trim()"
        " && !document.getElementById('increase-status').textContent.includes('Working')",
        timeout=60_000)
    status = pg.inner_text("#increase-status")
    assert "Could not" not in status, status
    assert "increase plan" in status.lower() or "criteria" in status.lower()


# ------------------------------------------------------------------ overall

def test_the_whole_walk_raised_no_javascript_errors(walked):
    assert not walked["errors"], \
        "uncaught JS during the flow: " + "; ".join(walked["errors"][:5])
