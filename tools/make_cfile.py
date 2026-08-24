#!/usr/bin/env python3
# Copyright (c) 2026 Oliver Tillinghast.
# Licensed under the PolyForm Noncommercial License 1.0.0.
# Free for veterans, VSOs, nonprofits and government. Commercial use
# requires a separate licence -- see LICENSE, NOTICE.md, COMMERCIAL.md.
"""
tools/make_cfile.py — a synthetic VA claims file, at realistic scale.

A C-file is the veteran's complete claims record: everything VA has ever
held on them. Thousands of pages, assembled over decades by different
systems, and it is the document a representative has to read before an
appeal. That reading is the expensive part of the work.

The existing fixture is a ten-page MHS Genesis export in one clean format.
It is a fine unit-test fixture and a useless proxy for a C-file, which is
none of those things. A C-file is:

  MIXED FORMATS. Service treatment records, a DD-214, VA exam reports,
  rating decisions, private records subpoenaed from four clinics, payer
  claims, pharmacy ledgers, correspondence. Six layouts, not one.

  HEAVILY DUPLICATED. The same STR packet gets refiled with every claim.
  The same diagnosis appears fifty times across twenty years. A tool that
  reports fifty conditions when there are eleven has not helped anybody.

  FULL OF THINGS THAT LOOK LIKE CODES. CPT and HCPCS procedure codes, form
  numbers, claim numbers, DRG codes, page stamps, NDC numbers. Several of
  them are shaped exactly like ICD-10.

  PARTLY NARRATIVE. Progress notes and exam reports carry no codes at all.
  The honest answer for those pages is "unsupported", not a guess.

Nothing here is real. Names, providers and facilities are invented; the
ICD-10 codes are real codes attached to invented encounters.

    python tools/make_cfile.py --pages 3000 --out /tmp/cfile.pdf
"""

import argparse
import os
import random
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)

PAGE_WIDTH = 96
LINES_PER_PAGE = 46

MEMBER = "DOE, JOHN ANTHONY"
FILE_NO = "C 12 345 678"

# (code, description, body system) -- real codes, invented encounters.
TRUTH = [
    ("M54.50", "Low back pain, unspecified", "Musculoskeletal"),
    ("M54.16", "Radiculopathy, lumbar region", "Musculoskeletal"),
    ("M25.561", "Pain in right knee", "Musculoskeletal"),
    ("M75.101", "Rotator cuff tear, right shoulder", "Musculoskeletal"),
    ("H93.13", "Tinnitus, bilateral", "Ears"),
    ("H90.3", "Sensorineural hearing loss, bilateral", "Ears"),
    ("F43.10", "Post-traumatic stress disorder, unspecified", "Mental health"),
    ("F32.1", "Major depressive disorder, single episode, moderate", "Mental health"),
    ("G47.33", "Obstructive sleep apnea (adult)", "Respiratory"),
    ("J30.9", "Allergic rhinitis, unspecified", "Respiratory"),
    ("K21.9", "Gastro-esophageal reflux disease without esophagitis", "Digestive"),
    ("G43.909", "Migraine, unspecified, not intractable", "Neurological"),
    ("M17.11", "Unilateral primary osteoarthritis, right knee", "Musculoskeletal"),
    ("I10", "Essential (primary) hypertension", "Circulatory"),
]

PROVIDERS = [
    "EXAMPLE, PAT A, MD", "SAMPLE, JORDAN B, DO", "FICTION, MORGAN K, MD",
    "DEMO, CASEY L, PA", "TESTCASE, AVERY P, LCSW", "DOE, JANE R, LCSW",
]

FACILITIES = [
    "VA MEDICAL CENTER - EXAMPLETOWN", "88TH MEDICAL GROUP CLINIC",
    "SAMPLE VALLEY ORTHOPEDICS", "FICTION FAMILY PRACTICE",
    "DEMO REGIONAL SLEEP CENTER",
]

# Strings shaped like ICD-10 that are not diagnoses. Every one of these is a
# real thing that appears in a real C-file.
DECOYS = [
    ("99213", "OFFICE/OUTPATIENT VISIT EST"),        # CPT
    ("97110", "THERAPEUTIC EXERCISES"),              # CPT
    ("G0438", "ANNUAL WELLNESS VISIT"),              # HCPCS -- G + digits
    ("J1885", "INJECTION KETOROLAC 15 MG"),          # HCPCS -- J + digits
    ("A9270", "NON-COVERED ITEM OR SERVICE"),        # HCPCS -- A + digits
    ("Q4101", "APLIGRAF PER SQ CM"),                 # HCPCS -- Q + digits
    ("R0070", "TRANSPORT PORTABLE X-RAY"),           # HCPCS -- R + digits
    ("21-4138", "STATEMENT IN SUPPORT OF CLAIM"),    # VA form number
    ("21-526EZ", "APPLICATION FOR DISABILITY COMPENSATION"),
    ("DBQ0740", "DISABILITY BENEFITS QUESTIONNAIRE"),
]


def wrap(text, width=PAGE_WIDTH, indent=""):
    out, line = [], indent
    for word in text.split():
        if len(line) + len(word) + 1 > width:
            out.append(line.rstrip())
            line = indent + word + " "
        else:
            line += word + " "
    if line.strip():
        out.append(line.rstrip())
    return out


def header(rng, title, page_no):
    return [
        f"{'DEPARTMENT OF VETERANS AFFAIRS':<60}{'PAGE ' + str(page_no):>36}",
        f"{'CLAIMS FOLDER — ' + FILE_NO:<60}{MEMBER:>36}",
        "-" * PAGE_WIDTH,
        title,
        "",
    ]


# ---------------------------------------------------------------- sections

def str_packet(rng, facts):
    """Service treatment records, in the real MHS Genesis layout.

    The block format is imported from make_sample_record rather than
    re-typed here. A hand-written approximation would drift from the one
    extract_conditions.py actually parses, and the whole point of this
    fixture is to exercise the parser against the format it claims to
    support -- a fixture that quietly stopped matching would turn every
    result into a measurement of nothing.
    """
    from make_sample_record import diagnosis_block

    out = ["SERVICE TREATMENT RECORD — ENCOUNTER SUMMARY", ""]
    for code, name, _system in facts:
        # US format. extract_conditions.DIAG_RE anchors on
        # "Diagnosis Date: MM/DD/YYYY", which is what a real MHS Genesis
        # export writes -- an ISO date here silently matches nothing, and
        # the fixture would quietly stop exercising the MHS parser at all.
        date = (f"{rng.randint(1,12):02d}/{rng.randint(1,28):02d}/"
                f"{rng.choice(['2011','2013','2016','2019'])}")
        block = diagnosis_block(name, code, rng.choice(PROVIDERS), date,
                                rng.choice(["Active", "Active", "Resolved"]))
        out += block.split("\n")
    return out


def problem_list(rng, facts):
    """CCD-A / HIE consolidated export: a column table."""
    out = ["CONSOLIDATED PROBLEM LIST (C-CDA EXPORT)", "",
           f"{'CODE':<10}{'DESCRIPTION':<52}{'ONSET':<12}{'STATUS':<10}", ""]
    for code, name, _ in facts:
        onset = f"{rng.choice(['2009','2012','2015','2018'])}-{rng.randint(1,12):02d}-{rng.randint(1,28):02d}"
        out.append(f"{code:<10}{name[:50]:<52}{onset:<12}"
                   f"{rng.choice(['Active','Active','Inactive']):<10}")
    return out + [""]


def payer_claims(rng, facts):
    """Claims ledger: the code sits mid-line among billing fields."""
    out = ["PAYER CLAIMS HISTORY", "",
           "SVC DATE   CLAIM NO     CPT   DESCRIPTION                    DX      DIAGNOSIS", ""]
    for code, name, _ in facts:
        d = f"{rng.randint(1,12):02d}/{rng.randint(1,28):02d}/{rng.choice([2014,2017,2020,2023])}"
        cpt, cptname = rng.choice(DECOYS[:2])
        out.append(f"{d}  CLM{rng.randint(10**7, 10**8-1)}  {cpt}  "
                   f"{cptname[:28]:<30} {code:<7} {name[:40]}")
    return out + [""]


def decoy_page(rng):
    """Billing and administrative pages: dense with code-shaped strings that
    are not diagnoses. This is the page that generates false positives."""
    out = ["EXPLANATION OF BENEFITS — PROCEDURE DETAIL", "",
           f"{'CODE':<10}{'MODIFIER':<10}{'DESCRIPTION':<46}{'ALLOWED':>10}", ""]
    for _ in range(14):
        code, desc = rng.choice(DECOYS)
        out.append(f"{code:<10}{rng.choice(['', 'LT', 'RT', '59']):<10}"
                   f"{desc[:44]:<46}{'$' + str(rng.randint(20, 900)):>10}")
    out += ["", "FORM 21-4138 RECEIVED 03/14/2019    FORM 21-526EZ RECEIVED 01/09/2018",
            "DRG 470 MAJOR JOINT REPLACEMENT      NDC 00093-7368-56"]
    return out + [""]


def narrative_page(rng, facts):
    """A progress note. Carries no codes -- the honest answer for this page
    is that it is unsupported, not a guess pulled out of prose."""
    code, name, _ = rng.choice(facts)
    body = (
        f"Veteran presents for follow-up. Reports ongoing symptoms consistent "
        f"with previously documented {name.lower()}. Describes the problem as "
        f"moderate and intermittent, worse with activity and in cold weather. "
        f"Denies new injury. Reviewed prior imaging and current medications. "
        f"Discussed conservative management, activity modification and "
        f"follow-up in three months. Veteran voiced understanding and agrees "
        f"with the plan. No acute distress noted on examination today."
    )
    return (["CHRONOLOGICAL RECORD OF MEDICAL CARE (SF 600)", ""]
            + wrap(body) + ["", f"    /s/ {rng.choice(PROVIDERS)}", ""])


def rating_decision(rng, facts):
    out = ["RATING DECISION — NARRATIVE", ""]
    for code, name, _ in facts[:3]:
        out += wrap(f"Service connection for {name.lower()} is granted with an "
                    f"evaluation of {rng.choice([10,20,30,50])} percent effective "
                    f"{rng.choice(['2019','2021','2023'])}-"
                    f"{rng.randint(1,12):02d}-{rng.randint(1,28):02d}.") + [""]
    return out


SECTION_BUILDERS = [
    (str_packet, 4), (problem_list, 3), (payer_claims, 3),
    (decoy_page, 4), (narrative_page, 5), (rating_decision, 1),
]


def build(pages, seed=7):
    rng = random.Random(seed)
    builders = [b for b, weight in SECTION_BUILDERS for _ in range(weight)]

    lines, page_no = [], 1
    while page_no <= pages:
        builder = rng.choice(builders)
        # Duplication is the defining feature of a C-file: the same packet is
        # refiled with every claim. A subset of the truth, repeated often.
        subset = rng.sample(TRUTH, rng.randint(2, min(6, len(TRUTH))))
        body = (builder(rng) if builder is decoy_page
                else builder(rng, subset))

        page = header(rng, f"SECTION {rng.randint(1, 12)} — "
                            f"{builder.__name__.replace('_', ' ').upper()}", page_no)
        page += body
        page += [""] * max(0, LINES_PER_PAGE - len(page))
        lines += page[:LINES_PER_PAGE]
        page_no += 1

    return "\n".join(lines)


def write_pdf(text, path, title="Synthetic C-File"):
    import fitz
    doc = fitz.open()
    page_lines = text.split("\n")
    per = LINES_PER_PAGE
    for i in range(0, len(page_lines), per):
        page = doc.new_page(width=612, height=792)
        chunk = "\n".join(page_lines[i:i + per])
        page.insert_text((36, 40), chunk, fontsize=7.2, fontname="cour")
    doc.set_metadata({"title": title})
    doc.save(path, deflate=True)
    doc.close()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pages", type=int, default=3000)
    ap.add_argument("--out", default=os.path.join(REPO, "tools", "cfile.pdf"))
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--text-only", action="store_true")
    args = ap.parse_args()

    text = build(args.pages, args.seed)
    if args.text_only:
        with open(args.out, "w", encoding="utf-8") as fh:
            fh.write(text)
    else:
        write_pdf(text, args.out)

    size = os.path.getsize(args.out)
    print(f"  {args.pages} pages -> {args.out}  ({size/1_048_576:.1f} MB)")
    print(f"  ground truth: {len(TRUTH)} distinct conditions")
    print(f"  decoys in play: {len(DECOYS)} code-shaped non-diagnoses")


if __name__ == "__main__":
    main()
