# Copyright (c) 2026 Oliver Tillinghast.
# Licensed under the PolyForm Noncommercial License 1.0.0.
# Free for veterans, VSOs, nonprofits and government. Commercial use
# requires a separate licence -- see LICENSE, NOTICE.md, COMMERCIAL.md.
"""
Everything that ships to the browser must at least compile.

A regex rewrite once left an unterminated string literal in
web/py/web_pipeline.py. The full suite stayed green -- nothing imports that
module, because it only runs inside Pyodide -- and the break surfaced as
"The engine could not load" in a browser, which is the worst place to find
a syntax error and the only place that was looking.

The browser build has no compiler between the edit and the user. These
tests are it.
"""

import ast
import os
import py_compile
import sys

import pytest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)

from conftest import FORM_DIR as WEB  # noqa: E402
PY_DIR = os.path.join(WEB, "py")


def manifest():
    with open(os.path.join(PY_DIR, "MANIFEST.txt"), encoding="utf-8") as fh:
        return [l.strip() for l in fh if l.strip()]


@pytest.mark.parametrize("module", manifest())
def test_every_shipped_module_compiles(module, tmp_path):
    path = os.path.join(PY_DIR, module)
    assert os.path.exists(path), f"{module} is in the manifest but not shipped"
    try:
        py_compile.compile(path, cfile=str(tmp_path / "out.pyc"), doraise=True)
    except py_compile.PyCompileError as exc:
        pytest.fail(f"{module} would fail to import in the browser:\n{exc}")


def test_the_manifest_matches_what_was_copied():
    listed = set(manifest())
    on_disk = {f for f in os.listdir(PY_DIR) if f.endswith(".py")}
    assert listed == on_disk, (
        f"manifest and directory disagree — only in manifest: "
        f"{listed - on_disk}; only on disk: {on_disk - listed}. "
        "Run tools/build_web.py.")


@pytest.mark.parametrize("module", [m for m in manifest() if m != "web_pipeline.py"])
def test_shipped_copies_match_the_source(module):
    """docs/form/py is generated. A hand-edit there is silently reverted by
    the next build, which is a confusing way to lose an afternoon."""
    shipped = open(os.path.join(PY_DIR, module), encoding="utf-8").read()
    source = open(os.path.join(REPO, module), encoding="utf-8").read()
    assert shipped == source, (
        f"{module} in docs/form/py differs from the repo root. Edit the root "
        "copy and run tools/build_web.py.")


def test_every_import_in_a_shipped_module_is_available_in_the_browser():
    """A module that imports something not in the manifest and not in the
    Pyodide runtime takes the whole engine down at boot."""
    shipped = set(manifest())
    stdlib = set(sys.stdlib_module_names)
    allowed = shipped | {m[:-3] for m in shipped} | stdlib | {
        "pypdf", "micropip", "js", "pyodide"}

    problems = []
    for module in shipped:
        tree = ast.parse(open(os.path.join(PY_DIR, module), encoding="utf-8").read())
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names = [a.name.split(".")[0] for a in node.names]
            elif isinstance(node, ast.ImportFrom):
                names = [(node.module or "").split(".")[0]] if node.level == 0 else []
            else:
                continue
            for name in names:
                if name and name not in allowed:
                    problems.append(f"{module} imports {name}")
    assert not problems, (
        "these would fail at boot inside Pyodide: " + "; ".join(sorted(set(problems))))


def test_the_browser_page_references_a_python_build_id():
    """Without it the modules are fetched by plain name and a returning
    visitor can run a cached, older extractor against a newer page."""
    html = open(os.path.join(WEB, "index.html"), encoding="utf-8").read()
    import re
    m = re.search(r'const PY_BUILD = "([^"]+)";', html)
    assert m, "PY_BUILD marker is gone; module fetches are uncached"
    assert m.group(1) not in ("", "dev", "unknown"), \
        "PY_BUILD was never stamped — run tools/build_web.py"


def test_every_python_call_in_the_page_resolves_to_a_real_function():
    """The page drives Python by name, inside template literals. Nothing in
    JavaScript checks those names, so a rename on one side is invisible until
    a user reaches that screen.

    This is not hypothetical. A British-to-American spelling pass rewrote
    `self_report.summarise(...)` to `summarize` in the HTML and left the
    module defining `summarise`. Step 3 threw AttributeError and rendered an
    empty checklist, in production, and every one of the 365 tests passed --
    because nothing else calls it and the browser test never reached that
    screen with content.
    """
    import ast
    import re

    from conftest import FORM_HTML, FORM_PY, read

    html = read(FORM_HTML)

    # module.function( ... ) inside the runPythonAsync template literals
    calls = set(re.findall(r"\b([a-z_][a-z0-9_]*)\.([a-z_][a-z0-9_]*)\s*\(", html))

    shipped = {}
    for name in os.listdir(FORM_PY):
        if not name.endswith(".py"):
            continue
        tree = ast.parse(read(os.path.join(FORM_PY, name)))
        shipped[name[:-3]] = {
            n.name for n in tree.body
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
        } | {
            n.name for n in tree.body if isinstance(n, ast.ClassDef)
        }

    missing = []
    for module, func in sorted(calls):
        if module not in shipped:
            continue                      # a JS object, not one of our modules
        if func not in shipped[module]:
            missing.append(f"{module}.{func}()")

    assert not missing, (
        "the page calls Python that does not exist: " + ", ".join(missing)
        + ". A rename on one side of the boundary broke the other.")
