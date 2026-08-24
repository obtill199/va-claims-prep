#!/usr/bin/env python3
"""
tools/build_web.py — assemble the browser build into docs/app/.

The Python that does the actual work is copied from the repo root rather
than duplicated, so the browser build cannot drift into a second, subtly
different implementation of the parser. Run this after changing any of the
shared modules.

    python tools/build_web.py
"""

import hashlib
import json
import os
import re
import shutil
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(REPO, "docs", "app")

# Pure-Python and WebAssembly-safe. Anything importing PyMuPDF, pdfplumber
# or python-docx cannot come along; web/py/web_pipeline.py covers that
# ground with pypdf instead.
SHARED_MODULES = [
    "extract_conditions.py",
    "field_map.py",
    "proposals.py",
    "explanations.py",
    "intake.py",
    "prompts.py",
    "schema.py",
    "package_bundle.py",
    "condition_library.py",
    "coded_records.py",
    "timing.py",
    "self_report.py",
    "secondary.py",
    "presumptives.py",
]

DATA = [
    "dd2807_crosswalk.json",
    "field_names_sha.json",
]

FORMS = [
    ("web/forms/dd2807-1.pdf", "forms/dd2807-1.pdf"),
    ("web/forms/sha_part_a.pdf", "forms/sha_part_a.pdf"),
]


sys.path.insert(0, REPO)
import intake  # noqa: E402  (after REPO is on the path)

QUESTIONS_BEGIN = "// <<< GENERATED QUESTIONS -- edit intake.py, not this"
QUESTIONS_END = "// >>> END GENERATED QUESTIONS"


def render_questions():
    """The browser build needs the questionnaire in JS. It used to be a hand-
    kept copy of intake.QUESTIONS, which is a copy that drifts: a question
    added to the Python was simply absent from the page people actually use,
    with nothing failing to say so. Generate it instead."""
    rows = []
    for key, label, kind, opts, help_text in intake.QUESTIONS:
        rows.append("  " + json.dumps(
            [key, label, kind, opts, help_text, key in intake.REQUIRED],
            ensure_ascii=False))
    return (QUESTIONS_BEGIN + "\nconst QUESTIONS = [\n"
            + ",\n".join(rows) + "\n];\n" + QUESTIONS_END)


def sync_questions():
    path = os.path.join(OUT, "index.html")
    html = open(path, encoding="utf-8").read()
    block = render_questions()

    if QUESTIONS_BEGIN in html:
        start = html.index(QUESTIONS_BEGIN)
        end = html.index(QUESTIONS_END) + len(QUESTIONS_END)
        new = html[:start] + block + html[end:]
    else:
        # First run: replace the hand-written array with the generated one.
        start = html.index("const QUESTIONS = [")
        end = html.index("\n];", start) + len("\n];")
        new = html[:start] + block + html[end:]

    if new != html:
        open(path, "w", encoding="utf-8").write(new)
        print(f"  questionnaire -> {len(intake.QUESTIONS)} questions "
              "generated from intake.py")
    else:
        print(f"  questionnaire already in sync "
              f"({len(intake.QUESTIONS)} questions)")


PY_VERSION_MARK = "const PY_BUILD ="


def stamp_presumptive_date():
    """Keep the date shown in the browser tied to the list it describes."""
    import datetime
    import presumptives
    y, m = presumptives.REVIEWED.split("-")
    pretty = datetime.date(int(y), int(m), 1).strftime("%B %Y")

    path = os.path.join(OUT, "index.html")
    html = open(path, encoding="utf-8").read()
    if not re.search(r'const PRESUMPTIVE_REVIEWED = "[^"]*";', html):
        print("  WARNING: no PRESUMPTIVE_REVIEWED marker in index.html")
        return
    new = re.sub(r'const PRESUMPTIVE_REVIEWED = "[^"]*";',
                 f'const PRESUMPTIVE_REVIEWED = "{pretty}";', html)
    if new != html:
        open(path, "w", encoding="utf-8").write(new)
    print(f"  presumptive list reviewed -> {pretty}")


def stamp_python_build():
    """Cache-bust the Python module fetches.

    The stylesheet has been cache-busted since the first deploy; the Python
    modules never were. They are fetched by plain name at boot, so a
    returning visitor could run last week's extractor against this week's
    page -- which is exactly what happened in testing: new HTML calling a
    stale field_map that still assumed every condition carried a date, and
    a TypeError with a traceback pointing at a line that no longer exists.

    Hash every module that ships, and hang that on the fetch URLs.
    """
    h = hashlib.sha256()
    for mod in sorted(SHARED_MODULES) + ["web_pipeline.py"]:
        path = os.path.join(OUT, "py", mod)
        if os.path.exists(path):
            with open(path, "rb") as fh:
                h.update(fh.read())
    digest = h.hexdigest()[:10]

    path = os.path.join(OUT, "index.html")
    html = open(path, encoding="utf-8").read()
    # Test for the marker, not for a change: an unchanged hash is the normal
    # case and used to warn that caching was broken when it was not.
    if not re.search(r'const PY_BUILD = "[^"]*";', html):
        print("  WARNING: no PY_BUILD marker in index.html; modules uncached")
        return
    new = re.sub(r'const PY_BUILD = "[^"]*";',
                 f'const PY_BUILD = "{digest}";', html)
    if new != html:
        open(path, "w", encoding="utf-8").write(new)
    print(f"  python modules -> ?v={digest}")


def main():
    for sub in ("py", "data", "forms"):
        os.makedirs(os.path.join(OUT, sub), exist_ok=True)

    for mod in SHARED_MODULES:
        src = os.path.join(REPO, mod)
        if not os.path.exists(src):
            raise SystemExit(f"missing shared module: {mod}")
        shutil.copy2(src, os.path.join(OUT, "py", mod))
    print(f"  {len(SHARED_MODULES)} shared modules -> docs/app/py/")
    sync_questions()

    shutil.copy2(os.path.join(REPO, "web", "py", "web_pipeline.py"),
                 os.path.join(OUT, "py", "web_pipeline.py"))
    print("  web_pipeline.py -> docs/app/py/")

    for name in DATA:
        shutil.copy2(os.path.join(REPO, name), os.path.join(OUT, "data", name))
    print(f"  {len(DATA)} data files -> docs/app/data/")

    for src, dst in FORMS:
        s = os.path.join(REPO, src)
        if not os.path.exists(s):
            raise SystemExit(f"missing {src} — run tools/prep_web_forms.py first")
        shutil.copy2(s, os.path.join(OUT, dst))
    print(f"  {len(FORMS)} blank forms -> docs/app/forms/")

    manifest = SHARED_MODULES + ["web_pipeline.py"]
    with open(os.path.join(OUT, "py", "MANIFEST.txt"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(manifest) + "\n")
    stamp_presumptive_date()
    stamp_python_build()
    print(f"  manifest: {len(manifest)} modules")


if __name__ == "__main__":
    main()
