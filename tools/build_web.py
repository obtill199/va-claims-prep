#!/usr/bin/env python3
"""
tools/build_web.py — assemble the browser build into docs/app/.

The Python that does the actual work is copied from the repo root rather
than duplicated, so the browser build cannot drift into a second, subtly
different implementation of the parser. Run this after changing any of the
shared modules.

    python tools/build_web.py
"""

import os
import shutil

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
]

DATA = [
    "dd2807_crosswalk.json",
    "field_names_sha.json",
]

FORMS = [
    ("web/forms/dd2807-1.pdf", "forms/dd2807-1.pdf"),
    ("web/forms/sha_part_a.pdf", "forms/sha_part_a.pdf"),
]


def main():
    for sub in ("py", "data", "forms"):
        os.makedirs(os.path.join(OUT, sub), exist_ok=True)

    for mod in SHARED_MODULES:
        src = os.path.join(REPO, mod)
        if not os.path.exists(src):
            raise SystemExit(f"missing shared module: {mod}")
        shutil.copy2(src, os.path.join(OUT, "py", mod))
    print(f"  {len(SHARED_MODULES)} shared modules -> docs/app/py/")

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
    with open(os.path.join(OUT, "py", "MANIFEST.txt"), "w") as fh:
        fh.write("\n".join(manifest) + "\n")
    print(f"  manifest: {len(manifest)} modules")


if __name__ == "__main__":
    main()
