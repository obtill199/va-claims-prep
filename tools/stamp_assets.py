#!/usr/bin/env python3
"""
tools/stamp_assets.py — cache-bust the stylesheet links.

GitHub Pages serves assets with `cache-control: max-age=600`, so a visitor
who has been on the site keeps the old stylesheet for up to ten minutes —
and browsers frequently hold it longer than that. The symptom is a deploy
that looks like it silently failed: new markup, old styling.

Appending a content hash to the href makes each build a distinct URL, so a
changed stylesheet is always fetched and an unchanged one is still cached.
Run after editing any CSS, before committing.

    python tools/stamp_assets.py
"""

import hashlib
import os
import re

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# (html file, href as written in that file, the css file it points at)
TARGETS = [
    ("docs/index.html", "assets/base.css", "docs/assets/base.css"),
    ("docs/app/index.html", "../assets/base.css", "docs/assets/base.css"),
]


def short_hash(path):
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()[:10]


def main():
    changed = 0
    for html_rel, href, css_rel in TARGETS:
        html_path = os.path.join(REPO, html_rel)
        css_path = os.path.join(REPO, css_rel)
        if not (os.path.exists(html_path) and os.path.exists(css_path)):
            print(f"  skip {html_rel} (missing)")
            continue

        digest = short_hash(css_path)
        html = open(html_path, encoding="utf-8").read()

        # Replace href="<href>" or href="<href>?v=..." with the current hash.
        pattern = re.compile(r'href="' + re.escape(href) + r'(?:\?v=[0-9a-f]+)?"')
        new_html, n = pattern.subn(f'href="{href}?v={digest}"', html)
        if n == 0:
            print(f"  WARNING: no link to {href} found in {html_rel}")
            continue

        if new_html != html:
            open(html_path, "w", encoding="utf-8").write(new_html)
            changed += 1
        print(f"  {html_rel}: {href}?v={digest}  ({n} link{'s' if n != 1 else ''})")

    print(f"\n{changed} file(s) updated.")


if __name__ == "__main__":
    main()
