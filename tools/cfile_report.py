#!/usr/bin/env python3
# Copyright (c) 2026 Oliver Tillinghast.
# Licensed under the PolyForm Noncommercial License 1.0.0.
# Free for veterans, VSOs, nonprofits and government. Commercial use
# requires a separate licence -- see LICENSE, NOTICE.md, COMMERCIAL.md.
"""
tools/cfile_report.py — run the real pipeline over a C-file and score it.

Scored against known ground truth, because a demo that reports "found 47
conditions" is unfalsifiable. The synthetic file is built from a fixed list,
so recall and false positives are both countable, and the decoy pages exist
specifically to generate false positives if the parser is careless.

Runs the same entry point the browser uses -- web_pipeline.process_files --
rather than calling parsers directly, so the numbers describe the product
rather than a favourable subset of it.

    python tools/make_cfile.py --pages 3000 --out /tmp/cfile.pdf
    python tools/cfile_report.py /tmp/cfile.pdf
"""

import argparse
import os
import sys
import time

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
sys.path.insert(0, os.path.join(REPO, "web", "py"))
sys.path.insert(0, os.path.join(REPO, "tools"))


def run(path, truth_codes=None):
    import web_pipeline
    from make_cfile import DECOYS, TRUTH

    truth = truth_codes or {c for c, _, _ in TRUTH}
    decoys = {c for c, _ in DECOYS}

    with open(path, "rb") as fh:
        data = fh.read()

    t0 = time.time()
    per_file, conditions, corpus = web_pipeline.process_files(
        [(os.path.basename(path), data)])
    elapsed = time.time() - t0

    clinical = conditions["clinical"]
    admin = conditions["administrative"]
    found = {c["icd10"] for c in clinical if c.get("icd10")}

    hits = found & truth
    misses = truth - found
    false_pos = found - truth
    decoy_hits = found & decoys

    return {
        "pages": per_file[0]["pages"],
        "chars": per_file[0]["chars"],
        "tier": per_file[0]["tier"],
        "seconds": elapsed,
        "clinical": len(clinical),
        "administrative": len(admin),
        "distinct": len(found),
        "truth": len(truth),
        "hits": sorted(hits),
        "misses": sorted(misses),
        "false_pos": sorted(false_pos),
        "decoy_hits": sorted(decoy_hits),
        "conditions": clinical,
    }


def report(r, path):
    print("=" * 72)
    print(f"  C-FILE EXTRACTION — {os.path.basename(path)}")
    print("=" * 72)
    print(f"  {r['pages']:,} pages   {r['chars']:,} characters   "
          f"read as: {r['tier']}")
    print(f"  processed in {r['seconds']:.1f}s "
          f"({r['pages'] / max(r['seconds'], .01):.0f} pages/sec)")
    print()
    print(f"  Distinct conditions found     {r['distinct']:>4}")
    print(f"  Ground truth in the file      {r['truth']:>4}")
    print(f"  Correctly identified          {len(r['hits']):>4}"
          f"   ({len(r['hits']) / r['truth']:.0%} recall)")
    print(f"  Missed                        {len(r['misses']):>4}"
          f"   {r['misses'] if r['misses'] else ''}")
    print(f"  False positives               {len(r['false_pos']):>4}"
          f"   {r['false_pos'] if r['false_pos'] else ''}")
    print(f"    of those, billing decoys    {len(r['decoy_hits']):>4}"
          f"   {r['decoy_hits'] if r['decoy_hits'] else ''}")
    print()

    # Duplication is the whole problem with a C-file: the same diagnosis
    # appears dozens of times. Collapsing it is most of the value.
    total_mentions = sum(c.get("encounters", 1) for c in r["conditions"])
    if r["distinct"]:
        print(f"  {total_mentions:,} encounters collapsed into {r['distinct']} "
              f"conditions ({total_mentions / r['distinct']:.0f}x duplication)")
    print()
    print("  CONDITION                                        CODE      SEEN         PAGE")
    print("  " + "-" * 70)
    for c in sorted(r["conditions"], key=lambda x: x.get("first_seen") or ""):
        span = c.get("first_seen") or "?"
        if c.get("last_seen") and c["last_seen"] != c.get("first_seen"):
            span = f"{c['first_seen'][:7]}–{c['last_seen'][:7]}"
        print(f"  {c['condition'][:46]:<48} {(c.get('icd10') or '—'):<9} "
              f"{span:<12} {c.get('source_page') or '—'}")
    print()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pdf")
    args = ap.parse_args()
    r = run(args.pdf)
    report(r, args.pdf)


if __name__ == "__main__":
    main()
