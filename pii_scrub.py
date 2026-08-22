#!/usr/bin/env python3
"""
pii_scrub.py — Milestone 2: produce a de-identified copy of a record's
extracted text, so a demo file can exist without anyone handling real PHI
(BUILD_BRIEF.md section 4, decision 4; section 5, Milestone 2).

Operates on the .txt this pipeline already works in (ingest.py's output),
not the source PDF — visually redacting a scanned PDF (blacking out image
regions, not just overlaying text) is a much bigger, separate problem and
out of scope here. Every module downstream of ingest.py only ever sees
.txt anyway, so a scrubbed .txt is sufficient to build and demo the whole
pipeline end to end.

Two layers, both applied:
  1. Generic structural rules for things with a reliable shape: SSN, DoD
     ID/EDIPI (both always appear in a labeled "LABEL: <digits>" form in
     this document family — verified against the real MHS Genesis file),
     phone numbers, and provider names (reusing extract_conditions.py's
     own PROV_RE rather than re-deriving that pattern).
  2. A literal-value list *you* supply and fill in yourself — your exact
     name variants, SSN, address, phone. This script never needs those
     values typed into it or shown to it by anyone else; you provide the
     file, this just does case-insensitive whole-string replacement.
     See pii_literals.example.txt for the format. Your real file
     (pii_literals.txt by convention) is gitignored and never printed.

Usage:
    python pii_scrub.py mhs_genesis.txt -o demo_record.txt --literals pii_literals.txt
"""

import argparse
import re

from extract_conditions import PROV_RE

SSN_RE = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
# Case-insensitive: the real document uses "DOD ID (EDIPI):", not "DoD ID"
# — matching case-sensitively let bare "EDIPI" (matching mid-parenthetical,
# right before a ")" the separator can't cross) win over the fuller
# alternative, silently missing most instances. Bounded DOTALL gap for the
# same pdfplumber wrap-to-next-line layout behavior as DIAG_RE/PROBLEM_RE
# in extract_conditions.py — the value doesn't always stay on the label's
# own line.
EDIPI_LABELED_RE = re.compile(
    r"(?P<label>DoD ID(?: \(EDIPI\))?|EDIPI)(?P<gap>.{0,80}?)(?P<digits>\d{10})",
    re.IGNORECASE | re.DOTALL)
PHONE_RE = re.compile(r"\(\d{3}\)\s?\d{3}-\d{4}|\b\d{3}-\d{3}-\d{4}\b")
# Best-effort only — a real street-address parser is out of scope here.
# Catches "123 Main St", "456 Oak Avenue", etc.
ADDRESS_RE = re.compile(
    r"\b\d{1,6}\s+[A-Za-z0-9.'\- ]{2,40}\s"
    r"(?:St|Street|Ave|Avenue|Rd|Road|Dr|Drive|Ln|Lane|Blvd|Boulevard|Ct|Court|Way|Pl|Place)\b",
    re.IGNORECASE)


def _redact_provider(text):
    n = len(PROV_RE.findall(text))
    return PROV_RE.sub("Responsible Provider: [REDACTED-PROVIDER]", text), n


def scrub_generic(text, redact_providers=False):
    """Structural PII rules.

    redact_providers defaults to False. A clinician's name is not the
    member's identity, and DD 2807-1 Item 29 asks for "name of doctor(s)
    and/or hospital(s)" by name -- stripping them makes the output worse at
    the job it exists to do. Pass True only when producing a file you intend
    to hand to someone else, where a third party's name is not yours to
    share.
    """
    counts = {}

    text, n = SSN_RE.subn("[REDACTED-SSN]", text)
    counts["ssn"] = n

    def edipi_repl(m):
        return f"{m.group('label')}{m.group('gap')}[REDACTED-EDIPI]"
    text, n = EDIPI_LABELED_RE.subn(edipi_repl, text)
    counts["edipi"] = n

    text, n = PHONE_RE.subn("[REDACTED-PHONE]", text)
    counts["phone"] = n

    text, n = ADDRESS_RE.subn("[REDACTED-ADDRESS]", text)
    counts["address"] = n

    if redact_providers:
        text, n = _redact_provider(text)
        counts["provider"] = n

    return text, counts


def load_literals(path):
    with open(path) as fh:
        lines = [ln.strip() for ln in fh if ln.strip() and not ln.startswith("#")]
    # Longest first so e.g. a full name is replaced before a substring of it.
    return sorted(set(lines), key=len, reverse=True)


def scrub_literals(text, literals):
    count = 0
    for lit in literals:
        pattern = re.compile(re.escape(lit), re.IGNORECASE)
        text, n = pattern.subn("[REDACTED]", text)
        count += n
    return text, count


def scrub_paged(text, page_starts, literals_path=None,
                redact_providers=False):
    """Scrub page-by-page and recompute page offsets.

    Redactions change text length, so scrubbing the whole document at once
    invalidates ingest.py's .pages.json offsets and every page citation
    derived from them. Scrubbing each page's slice independently keeps the
    page boundaries meaningful, which matters because the demo record has
    to exercise the same citation path the real one does.
    """
    counts_total = {}
    out_parts, new_starts, offset = [], [], 0

    bounds = list(page_starts) + [len(text)]
    for i in range(len(page_starts)):
        page_text = text[bounds[i]:bounds[i + 1]]
        scrubbed, counts = scrub(page_text, literals_path,
                                 redact_providers=redact_providers)
        for key, n in counts.items():
            counts_total[key] = counts_total.get(key, 0) + n
        new_starts.append(offset)
        out_parts.append(scrubbed)
        offset += len(scrubbed)

    return "".join(out_parts), new_starts, counts_total


def scrub(text, literals_path=None, redact_providers=False):
    text, counts = scrub_generic(text, redact_providers=redact_providers)
    if literals_path:
        literals = load_literals(literals_path)
        text, n = scrub_literals(text, literals)
        counts["literal_matches"] = n
        counts["literal_values_supplied"] = len(literals)
    return text, counts


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("input_txt")
    ap.add_argument("-o", "--output", required=True)
    ap.add_argument("--literals", help="path to your own literal-value list (gitignored)")
    ap.add_argument("--redact-providers", action="store_true",
                    help="also strip clinician names. Off by default: the "
                         "member needs those names on the form. Use only for "
                         "a file you plan to share with someone else.")
    args = ap.parse_args()

    with open(args.input_txt, encoding="utf-8", errors="replace") as fh:
        text = fh.read()

    scrubbed, counts = scrub(text, args.literals,
                             redact_providers=args.redact_providers)

    with open(args.output, "w", encoding="utf-8") as fh:
        fh.write(scrubbed)

    print(f"{args.input_txt} -> {args.output}")
    for label, n in counts.items():
        print(f"  {label}: {n}")
    if not args.literals:
        print("\n  NOTE: no --literals file given — your name/address/phone were "
              "NOT scrubbed unless they matched a generic rule above. "
              "See pii_literals.example.txt.")


if __name__ == "__main__":
    main()
