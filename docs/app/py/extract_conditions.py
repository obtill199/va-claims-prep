#!/usr/bin/env python3
"""
extract_conditions.py — MHS Genesis / STR condition extraction engine.

Parses the text layer of a DoD health record export into structured
condition records suitable for (a) prefilling DD 2807-1 and the SHA
Part A, and (b) generating a conditions worksheet for VSO review.

Usage:
    python extract_conditions.py record.txt [record2.txt ...] -o conditions.json
"""

import re
import json
import os
import argparse
import bisect
from collections import defaultdict
from datetime import datetime

# ---------------------------------------------------------------- parsing

DIAG_RE = re.compile(
    # Short names sit inline after "Diagnosis:"; long ones wrap to an
    # indented line below it instead, leaving the inline spot blank — same
    # pdfplumber column-layout behavior as PROBLEM_RE's name field below.
    # Capture both candidate lines; parse_diagnoses() picks whichever is
    # non-blank.
    r"Diagnosis:(?P<line1>[^\n]*)\n(?P<line2>[^\n]*)\n"
    # Originally a 0-6 line lookahead (`(?:.*?\n){0,6}?`), which assumed
    # "Diagnosis Date:" always starts at column 0 of its own line. True for
    # poppler's `pdftotext -layout`, not for pdfplumber's layout mode (used
    # here since poppler isn't installable on this machine — see
    # BUILD_BRIEF.md section 6 / pdf_io.py) — pdfplumber left-pads that
    # label with spaces to preserve its table column position, so it never
    # sits at a true line start and the old pattern silently matched zero
    # entries. A bounded DOTALL scan finds it regardless of indentation,
    # capped so a body can't accidentally swallow past its own diagnosis
    # into the next one's date. Only the body crosses newlines (re.DOTALL
    # applies pattern-wide, but `line1`/`line2` are deliberately kept to
    # `[^\n]` so they can't also expand across lines — an earlier version
    # with a newline-crossing lazy name group back to back with the body
    # scan caused catastrophic backtracking on the ~6 "Diagnosis:"
    # occurrences that have no nearby "Diagnosis Date:" to terminate on).
    r"(?P<body>.{0,3000}?)"
    r"Diagnosis Date:\s*(?P<date>\d{1,2}/\d{1,2}/\d{4})\s+Status:\s*(?P<status>\w+)",
    re.DOTALL,
)

CODE_RE = re.compile(r"Code:\s*(?P<code>[A-Z0-9.]+)\s*\((?P<system>[^)]+)\)")
PROV_RE = re.compile(r"Responsible Provider:\s*(?P<prov>.+?)\s*$", re.MULTILINE)

PROBLEM_RE = re.compile(
    # Short names sit inline after "Problem Name:"; long ones wrap to an
    # indented line below it (pdfplumber column layout again), leaving the
    # inline spot blank. Capture the whole span and pick out the real text
    # in parse_problems() instead of assuming a fixed line position.
    r"Problem Name:(?P<name_block>.{0,300}?)"
    r"Life Cycle Status:\s*(?P<status>\w+)",
    re.DOTALL,
)


def _norm_date(s):
    return datetime.strptime(s, "%m/%d/%Y").date().isoformat()


def _page_for(pos, page_starts):
    """1-indexed page number containing character offset `pos`, or None if
    no page-offset map was supplied (e.g. a bare .txt with no PDF sidecar)."""
    if not page_starts:
        return None
    return bisect.bisect_right(page_starts, pos)


def _clean_provider_field(raw):
    """Pick the full provider name out of a column-aligned line.

    pdfplumber's layout mode preserves this record's two-column encounter
    header, so the captured text is an abbreviated name and the full name
    side by side, separated by a run of spaces:
        "7/6/2021 09:27 CDT; DOE,          DOE, JANE R, LCSW"
    Collapsing all whitespace first (the previous behaviour) welded them
    into "DOE, DOE, JANE R, LCSW". Splitting on the column gap
    and keeping the longest segment recovers the real name, which Item 29
    of DD 2807-1 requires by name.
    """
    if not raw:
        return None
    # Drop the encounter timestamp first — otherwise it can make the
    # abbreviated-name column the longest segment and win the pick below.
    raw = re.sub(r"^\s*\d{1,2}/\d{1,2}/\d{4}[^;]*;\s*", "", raw)
    segments = [s.strip() for s in re.split(r"\s{2,}", raw) if s.strip()]
    if not segments:
        return None
    best = max(segments, key=len)
    return re.sub(r"\s+", " ", best).strip() or None


def parse_diagnoses(text, page_starts=None, source_document=None):
    """Yield one dict per Clinical Diagnoses entry.

    page_starts/source_document (from ingest.py's <file>.pages.json sidecar)
    are optional — every Proposal needs a source citation
    (BUILD_BRIEF.md section 4, decision 1), but this function still works
    standalone (e.g. against a plain .txt with no PDF behind it)."""
    for m in DIAG_RE.finditer(text):
        # Look a few lines past the match for the Code: line
        tail = text[m.end(): m.end() + 400]
        code_m = CODE_RE.search(tail)
        prov_m = PROV_RE.search(m.group("body"))
        name = m.group("line1").strip() or m.group("line2").strip()
        yield {
            "name": re.sub(r"\s+", " ", name).strip(),
            "date": _norm_date(m.group("date")),
            "status": m.group("status"),
            "code": code_m.group("code") if code_m else None,
            "code_system": code_m.group("system") if code_m else None,
            "provider": _clean_provider_field(prov_m.group("prov")) if prov_m else None,
            "page": _page_for(m.start(), page_starts),
            "source_document": source_document,
        }


def parse_problems(text):
    """Yield one dict per Problems-list entry (the clinician-curated list)."""
    for m in PROBLEM_RE.finditer(text):
        name = " ".join(
            line.strip() for line in m.group("name_block").split("\n") if line.strip()
        )
        yield {
            "name": name,
            "status": m.group("status"),
        }


# ------------------------------------------------------------ aggregation

# Codes that describe an administrative encounter rather than a health
# condition. These are noise for claim purposes and are separated out.
ADMIN_PREFIXES = ("Z0", "Z71", "Z23", "Z76", "DOD")


def is_administrative(code, name):
    if code and code.startswith(ADMIN_PREFIXES):
        return True
    admin_words = ("encounter for", "exam/assessment", "counseling",
                   "immunization", "screening for")
    return any(w in name.lower() for w in admin_words)


BODY_SYSTEMS = [
    ("Musculoskeletal", r"^M"),
    ("Injury / trauma", r"^S"),
    ("Mental health", r"^F"),
    ("Neurological", r"^G"),
    ("Eye", r"^H[0-5]"),
    ("Ear / hearing", r"^H[6-9]"),
    ("Respiratory", r"^J"),
    ("Digestive", r"^K"),
    ("Skin", r"^L"),
    ("Endocrine / metabolic", r"^E"),
    ("Circulatory", r"^I"),
    ("Genitourinary", r"^N"),
    ("Infectious", r"^[AB]"),
    ("Symptoms / signs", r"^R"),
    ("External cause", r"^[VWXY]"),
]


def body_system(code):
    if not code:
        return "Uncoded"
    for label, pat in BODY_SYSTEMS:
        if re.match(pat, code):
            return label
    return "Other"


def aggregate(diagnoses, problems):
    """Collapse repeated diagnoses into one record per condition."""
    buckets = defaultdict(list)
    for d in diagnoses:
        key = (d["code"] or "NOCODE", d["name"].lower())
        buckets[key].append(d)

    problem_names = {p["name"].lower() for p in problems}

    out = []
    for (code, _), entries in buckets.items():
        entries.sort(key=lambda e: e["date"])
        name = entries[0]["name"]
        statuses = {e["status"] for e in entries}
        providers = sorted({e["provider"] for e in entries if e["provider"]})
        out.append({
            "condition": name,
            "icd10": code if code != "NOCODE" else None,
            "body_system": body_system(code if code != "NOCODE" else None),
            "first_seen": entries[0]["date"],
            "last_seen": entries[-1]["date"],
            "encounters": len(entries),
            "active": "Active" in statuses,
            "on_problem_list": name.lower() in problem_names,
            "providers": providers,
            "administrative": is_administrative(
                code if code != "NOCODE" else "", name),
            # Citation for the earliest (first_seen) occurrence — what a
            # Proposal built from this condition points a reviewer at.
            "source_document": entries[0].get("source_document"),
            "source_page": entries[0].get("page"),
        })

    out.sort(key=lambda r: (r["administrative"], not r["active"],
                            r["first_seen"]))
    return out


# ------------------------------------------------------------------- main

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("inputs", nargs="+")
    ap.add_argument("-o", "--output", default="conditions.json")
    args = ap.parse_args()

    all_diag, all_prob = [], []
    for path in args.inputs:
        with open(path, encoding="utf-8", errors="replace") as fh:
            text = fh.read()

        # ingest.py's sidecar, if this .txt came from a PDF via ingest.py.
        page_starts, source_document = None, os.path.basename(path)
        pages_path = path + ".pages.json"
        if os.path.exists(pages_path):
            with open(pages_path) as fh:
                sidecar = json.load(fh)
            page_starts = sidecar["page_starts"]
            source_document = sidecar["source_document"]

        d = list(parse_diagnoses(text, page_starts, source_document))
        p = list(parse_problems(text))
        print(f"{path}: {len(d)} diagnosis entries, {len(p)} problem entries")
        all_diag += d
        all_prob += p

    records = aggregate(all_diag, all_prob)
    clinical = [r for r in records if not r["administrative"]]
    admin = [r for r in records if r["administrative"]]

    with open(args.output, "w") as fh:
        json.dump({"clinical": clinical, "administrative": admin},
                  fh, indent=2)

    print(f"\n{len(clinical)} clinical conditions, "
          f"{len(admin)} administrative entries -> {args.output}")


if __name__ == "__main__":
    main()
