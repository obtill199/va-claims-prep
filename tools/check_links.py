#!/usr/bin/env python3
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
PAGES = [os.path.join(REPO, "docs", "index.html"),
         os.path.join(REPO, "docs", "app", "index.html")]

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
      "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36")

# Sites that refuse automated requests but work fine in a real browser.
# Listed explicitly so a 403 here is a known exception, not a silent pass.
BOT_BLOCKED = set()


def links(path):
    html = open(path, encoding="utf-8").read()
    return sorted(set(re.findall(r'href="(https?://[^"]+)"', html)))


def check(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
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
            ok = status == 200 or (status == 403 and url in BOT_BLOCKED)
            print(f"  {str(status):<6} {url}")
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
