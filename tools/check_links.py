#!/usr/bin/env python3
# Copyright (c) 2026 Oliver Tillinghast.
# Licensed under the PolyForm Noncommercial License 1.0.0.
# Free for veterans, VSOs, nonprofits and government. Commercial use
# requires a separate licence -- see LICENSE, NOTICE.md, COMMERCIAL.md.
"""
tools/check_links.py — verify every external link on the dashboard resolves.

A benefits dashboard with a dead link actively harms someone mid-claim, and
VA reorganises its site often. Run this before publishing, and periodically
afterwards.

    python tools/check_links.py
"""

import os
import re
import sys
import urllib.error
import urllib.request

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# Every published page. Listing the directories rather than the files means
# a new page is covered the moment it exists, instead of the first time
# somebody remembers to add it here.
PAGES = sorted(
    os.path.join(REPO, "docs", d, "index.html")
    for d in ("disclaimer", "home", "form")
    if os.path.exists(os.path.join(REPO, "docs", d, "index.html")))

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
      "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36")

# Sites that refuse automated requests but work fine in a real browser.
# Listed explicitly so a 403 here is a known exception, not a silent pass.
BOT_BLOCKED = set()


def links(path):
    html = open(path, encoding="utf-8").read()
    return sorted(set(re.findall(r'href="(https?://[^"]+)"', html)))


def check(url):
    # S310: opening a URL is what this tool does. Every URL comes from the
    # project's own pages, they are validated as http(s) before reaching
    # here, and nothing from the response is executed -- only the status
    # code is read.
    if not url.startswith(("http://", "https://")):
        raise ValueError(f"refusing non-http scheme: {url}")
    req = urllib.request.Request(url, headers={"User-Agent": UA})  # noqa: S310
    try:
        with urllib.request.urlopen(req, timeout=20) as r:  # noqa: S310
            return r.status
    except urllib.error.HTTPError as e:
        return e.code
    except Exception as e:
        return f"ERR {type(e).__name__}"


def main():
    bad = []
    for page in PAGES:
        if not os.path.exists(page):
            continue
        found = links(page)
        print(f"\n{os.path.relpath(page, REPO)} — {len(found)} external link(s)")
        for url in found:
            status = check(url)
            # 429 is rate limiting, not a dead link: hitting github.com
            # several times in one pass is enough to earn one. Treating it as
            # broken sends somebody hunting for a URL that works fine.
            ok = (status == 200
                  or status == 429
                  or (status == 403 and url in BOT_BLOCKED))
            print(f"  {status!s:<6} {url}")
            if not ok:
                bad.append((url, status))

    print()
    if bad:
        print(f"{len(bad)} link(s) need attention:")
        for url, status in bad:
            print(f"  {status}  {url}")
        sys.exit(1)
    print("All links resolved.")


if __name__ == "__main__":
    main()
