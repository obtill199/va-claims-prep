#!/usr/bin/env python3
# Copyright (c) 2026 Oliver Tillinghast.
# Licensed under the PolyForm Noncommercial License 1.0.0.
# Free for veterans, VSOs, nonprofits and government. Commercial use
# requires a separate licence -- see LICENSE, NOTICE.md, COMMERCIAL.md.
"""
coded_records.py — extract conditions from record formats that aren't MHS Genesis.

extract_conditions.py parses one very specific layout: the MHS Genesis
"Diagnosis: … Diagnosis Date: … Status: … Code:" block. Tested against five
other real-world record formats, it found nothing in any of them, because
none contain those anchor strings. That is a silent, total failure on
records a veteran is quite likely to have.

This module handles the general case: any line that carries an ICD-10 code
next to a description and a date. That covers, from the formats tested:

  - CCD-A / HIE consolidated exports, whose problem lists are column tables:
        M54.50   Low back pain, unspecified    2019-06-11 Active   2026-03-30
  - Payer claims and pharmacy ledgers, where the code sits mid-line among
    claim numbers, CPT codes and billing fields:
        02/19/2019 CLM07100331 99214 OFFICE VISIT ... M54.50 Low back pain ...

It deliberately does NOT attempt narrative records — SF-600 chronological
entries, prose progress notes, imaging reports. Those contain no codes at
all, and pulling a diagnosis out of a sentence is a judgement problem, not a
pattern-matching one. Those files are reported as unsupported rather than
quietly returning nothing.
"""

import re
from collections import defaultdict

# ICD-10-CM: a letter (not U), digit, then alphanumeric, optional subclass.
# Anchored on word boundaries and required to be followed by descriptive
# text, so CPT codes, claim numbers and accession IDs don't match.
# The whitespace window has to be generous: column padding depends entirely
# on which text extractor produced the page. pdfplumber renders this table
# with 3 spaces between code and description, pypdf's layout mode with 16.
# A narrow window silently matched nothing under pypdf, so the browser build
# classified a perfectly readable CCD-A export as "narrative".
# Requiring a letter after the gap still excludes claim numbers and amounts.
ICD10_RE = re.compile(
    r"\b(?P<code>[A-TV-Z][0-9][0-9AB](?:\.[0-9A-TV-Z]{1,4})?)\b"
    r"(?=[ \t]{1,60}[A-Za-z])")

ISO_DATE_RE = re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b")
US_DATE_RE = re.compile(r"\b(\d{1,2})/(\d{1,2})/(\d{4})\b")

# Column headers and billing vocabulary that can trail a description. Used
# to trim, so "Low back pain, unspecified    2019-06-11 Active" doesn't
# become part of the condition name.
# Structural noise: column padding, and runs of billing figures. Neither is
# word-based, so case does not enter into it.
TRAILING_NOISE = re.compile(
    r"\s{2,}.*$|"
    r"\s+\d+\.\d{2}\b.*$",
    re.IGNORECASE)

# Clinic and category tails, which records write as ALL CAPS column values:
# "M54.50 Low back pain PRIMARY CARE", "G47.33 Sleep apnea SLEEP LAB".
#
# Case-SENSITIVE, and that is the entire point. This list was IGNORECASE
# until a synthetic C-file caught what that does: every one of these words
# also occurs lowercase INSIDE real diagnosis names, and the pattern ate the
# name from that word onward. Five of thirteen common diagnoses were being
# destroyed --
#
#     "Obstructive sleep apnea (adult)"      -> "Obstructive"
#     "Unilateral primary osteoarthritis"    -> "Unilateral"
#     "Adjustment disorder with chronic ..." -> "Adjustment disorder with"
#
# -- and sleep apnea is among the most frequently claimed VA conditions.
# A worksheet handed to a VSO listing "Obstructive" is worse than useless.
DEPARTMENT_TAIL = re.compile(
    r"\s+(?:PRIM|PRIMARY|SECONDARY|ACTIVE|CHRONIC|RESOLVED|INACTIVE|"
    r"REHAB|IMAGING|AUDIOLOGY|SLEEP|LAB|PHARMACY|SVCS?|ORTHOPEDICS|"
    r"NEUROLOGY|CARDIOLOGY|BEHAVIORAL|SPECIALTY|LABORATORY|RADIOLOGY|"
    r"DENTAL|OPTOMETRY|ENT)\b.*$")

# Department and category tails are ALL CAPS ("PRIMARY CARE", "SLEEP LAB").
# Deliberately a separate, case-SENSITIVE pattern: TRAILING_NOISE above is
# IGNORECASE, which would make this strip ordinary lowercase words like
# "unspecified" off the end of a real diagnosis.
CAPS_TAIL = re.compile(r"\s+(?:[A-Z]{3,}\s+){0,3}[A-Z]{3,}\s*$")

STATUS_RE = re.compile(r"\b(Active|Chronic|Resolved|Inactive)\b", re.IGNORECASE)

# A status word sitting at the END of a description is a column value, not
# part of the name: "Low back pain, unspecified   2019-06-11 Active".
#
# Anchored to the end on purpose, and that anchor is the whole design.
# "Chronic" is a status AND the first word of "Chronic obstructive pulmonary
# disease"; "chronic" appears mid-name in "Adjustment disorder with chronic
# depressed mood". Only a trailing occurrence is safely removable.
STATUS_TAIL = re.compile(
    r"\s+(?:Active|Chronic|Resolved|Inactive|Ongoing|Historical)\s*$",
    re.IGNORECASE)

# Codes introduced by an accounting label are account, claim and reference
# numbers that happen to satisfy the ICD-10 shape. "ACCOUNT M12.345
# STATEMENT BALANCE FORWARD" was being reported as a condition named
# "STATEMENT". A false positive is the worse failure of the two available
# here: it puts a condition the veteran does not have onto a form carrying
# a federal false-statement penalty, whereas a miss can still be caught by
# the member on the self-report screen.
ACCOUNTING_LABEL = re.compile(
    r"\b(?:ACCOUNT|ACCT|CLAIM|CLM|INVOICE|REF|REFERENCE|AUTH|AUTHORIZATION|"
    r"POLICY|MEMBER|GROUP|BATCH|CHECK|VOUCHER|DRG|NDC|CPT|HCPCS)"
    r"[\s#:.]*$", re.IGNORECASE)

# Lines that are table headers or legends, not data.
HEADER_RE = re.compile(
    r"\b(ICD-?10|DESCRIPTION|DIAGNOSIS CODE|CODE\s+DESC)\b", re.IGNORECASE)


def _plausible(iso):
    """Reject dates a service record cannot legitimately contain.

    Seen in real test data: a claims ledger carrying dates decades in the
    future. Using one as a condition's onset would put a nonsense date on a
    federal form, so they are dropped rather than trusted.
    """
    from datetime import date
    try:
        y = int(iso[:4])
    except ValueError:
        return False
    return 1940 <= y <= date.today().year


def _dates_on(line):
    """Every date on a line, ISO-normalised, in order of appearance."""
    out = []
    for m in ISO_DATE_RE.finditer(line):
        out.append((m.start(), f"{m.group(1)}-{m.group(2)}-{m.group(3)}"))
    for m in US_DATE_RE.finditer(line):
        mo, d, y = m.group(1), m.group(2), m.group(3)
        out.append((m.start(), f"{y}-{int(mo):02d}-{int(d):02d}"))
    return [d for _, d in sorted(out) if _plausible(d)]


def _clean_description(text):
    # Strip the column padding between code and description FIRST. Without
    # this, TRAILING_NOISE's leading `\s{2,}.*$` matched at position 0 and
    # deleted the entire description on any column-aligned table.
    text = text.lstrip()
    text = TRAILING_NOISE.sub("", text)
    text = DEPARTMENT_TAIL.sub("", text)
    stripped = CAPS_TAIL.sub("", text)
    # Never let tail-trimming empty a description that is legitimately an
    # acronym ("GERD", "PTSD").
    if len(stripped.strip()) >= 3:
        text = stripped
    text = ISO_DATE_RE.sub("", text)
    text = US_DATE_RE.sub("", text)
    text = re.sub(r"\s+", " ", text).strip(" .,-|")
    # After the date is gone the status word is the new tail, so this runs
    # last -- and twice, because "2019-06-11 Active Resolved" happens.
    for _ in range(2):
        stripped = STATUS_TAIL.sub("", text)
        if stripped == text:
            break
        text = stripped
    return text.strip(" .,-|")


def parse_coded_lines(text, page_starts=None, source_document=None):
    """Yield one entry per ICD-10 code occurrence, shaped like
    extract_conditions.parse_diagnoses() output so aggregate() can consume
    both interchangeably."""
    import bisect

    for line_start, line in _lines_with_offsets(text):
        if HEADER_RE.search(line):
            continue

        dates = _dates_on(line)
        status_m = STATUS_RE.search(line)

        for m in ICD10_RE.finditer(line):
            code = m.group("code")
            # What comes immediately before decides whether this is a
            # diagnosis code or an account number that looks like one.
            if ACCOUNTING_LABEL.search(line[:m.start()]):
                continue
            description = _clean_description(line[m.end():])
            if len(description) < 3:
                continue

            page = (bisect.bisect_right(page_starts, line_start + m.start())
                    if page_starts else None)
            yield {
                "name": description,
                "date": dates[0] if dates else None,
                "status": (status_m.group(1).title() if status_m else "Active"),
                "code": code,
                "code_system": "ICD-10-CM",
                "provider": None,
                "page": page,
                "source_document": source_document,
                "all_dates": dates,
            }


def _lines_with_offsets(text):
    offset = 0
    for line in text.split("\n"):
        yield offset, line
        offset += len(line) + 1


def collapse(entries):
    """One record per code. Descriptions in ledgers are column-truncated
    ("Low back pain, lu"), so the longest seen for a code wins."""
    by_code = defaultdict(list)
    for e in entries:
        by_code[e["code"]].append(e)

    out = []
    for code, group in by_code.items():
        dates = sorted({d for e in group for d in (e.get("all_dates") or [])
                        if d})
        best_name = max((e["name"] for e in group), key=len)
        statuses = {e["status"] for e in group}
        pages = [e["page"] for e in group if e["page"]]
        out.append({
            "name": best_name,
            "date": dates[0] if dates else None,
            "last_date": dates[-1] if dates else None,
            "status": "Inactive" if statuses == {"Resolved"} else "Active",
            "code": code,
            "code_system": "ICD-10-CM",
            "provider": None,
            "page": min(pages) if pages else None,
            "source_document": group[0]["source_document"],
            "occurrences": len(group),
        })
    return out


def to_diagnosis_entries(collapsed):
    """Expand collapsed records into the per-encounter shape
    extract_conditions.aggregate() expects, so downstream code needs no
    changes: one entry for the first date, one for the last."""
    entries = []
    for r in collapsed:
        if not r["date"]:
            continue
        base = {"name": r["name"], "status": r["status"], "code": r["code"],
                "code_system": r["code_system"], "provider": r["provider"],
                "page": r["page"], "source_document": r["source_document"]}
        entries.append({**base, "date": r["date"]})
        if r["last_date"] and r["last_date"] != r["date"]:
            entries.append({**base, "date": r["last_date"]})
    return entries


def extract(text, page_starts=None, source_document=None):
    """Full pass. Returns entries ready for extract_conditions.aggregate()."""
    raw = list(parse_coded_lines(text, page_starts, source_document))
    return to_diagnosis_entries(collapse(raw))


def looks_narrative(text):
    """True when a record carries no ICD-10 codes at all.

    Worth reporting explicitly: it is the difference between "we read this
    and it contained nothing relevant" and "we cannot read this kind of
    record", and the member needs to know which they are looking at.
    """
    return not ICD10_RE.search(text)
