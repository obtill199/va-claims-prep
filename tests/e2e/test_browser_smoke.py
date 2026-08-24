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

Deliberately a smoke test rather than a full walk-through: it does not
upload a record. Booting Pyodide takes most of a minute and a fixture PDF
adds little over what the Python suite already covers. What it proves is
that the page loads, the engine comes up, and the flow is reachable --
which is exactly the class that unit tests cannot see.

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

# Pyodide downloads ~15MB and installs pypdf. Slow runners exist.
BOOT_TIMEOUT_MS = 180_000


@pytest.fixture(scope="module")
def server():
    handler = lambda *a, **k: http.server.SimpleHTTPRequestHandler(
        *a, directory=DOCS, **k)
    with socketserver.TCPServer(("127.0.0.1", 0), handler) as httpd:
        port = httpd.server_address[1]
        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        thread.start()
        yield f"http://127.0.0.1:{port}"
        httpd.shutdown()


@pytest.fixture(scope="module")
def page(server):
    with sync_playwright() as pw:
        try:
            browser = pw.chromium.launch()
        except Exception as exc:
            # Playwright installed but no browser downloaded. Skipping is the
            # honest outcome; launching hangs, which is a worse way to learn.
            pytest.skip(f"no Chromium available: {exc}")
        pg = browser.new_page()
        errors = []
        pg.on("pageerror", lambda e: errors.append(str(e)))
        pg.goto(f"{server}/form/index.html")
        pg.errors = errors
        yield pg
        browser.close()


def test_the_door_is_what_loads_first(page):
    """The disclaimers are on their own screen and must not be skippable by
    accident."""
    page.wait_for_selector("#step-0:not(.hidden)", timeout=30_000)
    text = page.inner_text("#step-0")
    assert "not a VA website" in text
    assert "never leave this computer" in text
    assert "SSN and DoD ID are never asked for" in text
    # No progress bar on a screen with no progress to make.
    assert page.locator(".steps").is_hidden()


def test_the_independence_notice_is_on_every_screen(page):
    """It is the one claim that must never be missable, so it lives in the
    masthead rather than in a dismissible block."""
    assert "not affiliated" in page.inner_text("body").lower()


def test_start_reaches_the_questionnaire(page):
    page.click("#to-intake")
    page.wait_for_selector("#step-1:not(.hidden)", timeout=10_000)
    assert page.locator("#f-full_name").is_visible()
    assert page.locator(".steps").is_visible()


def test_the_questionnaire_matches_the_python_source(page):
    """The JS QUESTIONS array is generated from intake.QUESTIONS. It used to
    be a hand-kept copy, which is how a question came to be asked everywhere
    except the page people use."""
    sys.path.insert(0, REPO)
    import intake
    for key, _label, _kind, _opts, _help in intake.QUESTIONS:
        assert page.locator(f"#f-{key}").count() == 1, \
            f"{key} is in intake.QUESTIONS but not on the page"


def test_the_engine_boots_and_enables_processing(page):
    """The seam nothing else tests: Pyodide up, modules on its filesystem,
    web_pipeline imported. A stale or broken module fails here."""
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


def test_the_page_raised_no_javascript_errors(page):
    assert not page.errors, "uncaught JS errors: " + "; ".join(page.errors[:5])
