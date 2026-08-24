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

WEB = os.path.join(REPO, "docs", "app")
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
    """docs/app/py is generated. A hand-edit there is silently reverted by
    the next build, which is a confusing way to lose an afternoon."""
    shipped = open(os.path.join(PY_DIR, module), encoding="utf-8").read()
    source = open(os.path.join(REPO, module), encoding="utf-8").read()
    assert shipped == source, (
        f"{module} in docs/app/py differs from the repo root. Edit the root "
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
