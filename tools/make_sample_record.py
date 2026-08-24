#!/usr/bin/env python3
# Copyright (c) 2026 Oliver Tillinghast.
# Licensed under the PolyForm Noncommercial License 1.0.0.
# Free for veterans, VSOs, nonprofits and government. Commercial use
# requires a separate licence -- see LICENSE, NOTICE.md, COMMERCIAL.md.
"""
tools/make_sample_record.py — build the synthetic demo record.

Demo mode (BUILD_BRIEF.md decision 4) has to work for anyone who clones
this, and it has to work without exposing a real person. An earlier demo
file was a de-identified copy of the author's own export, which meant it
could not ship: scrubbing is regex-based and carries false-negative risk,
and the conditions in it were still a real person's medical history.

So this generates a wholly fictional record instead, in the same MHS
Genesis text layout the parser expects. Nobody's data, and regenerable.

    python tools/make_sample_record.py
"""

import json
import os

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_TXT = os.path.join(REPO, "tools", "sample_record.txt")

PATIENT = "SAMPLE, ALEX RIVER"

# (name, icd10, provider, [(date, status), ...], on_problem_list)
#
# Chosen to mirror what veterans actually claim rather than an arbitrary
# assortment: tinnitus and hearing loss are consistently the most-claimed VA
# disabilities, followed by lumbosacral and cervical strain, limitation of
# knee flexion, PTSD and other mental-health conditions, migraine, sleep
# apnea, radiculopathy, scars and plantar fasciitis. A sample that reflects
# that distribution exercises the condition library the way real records
# will, and shows a new user output that looks like their own situation.
#
# Every name, date, code pairing and clinician here is invented. It
# describes no real person.
CONDITIONS = [
    # --- the perennial top claims ---
    ("Tinnitus, bilateral", "H93.13", "FICTION, MORGAN K, MD",
     [("4/19/2021", "Active"), ("6/2/2023", "Active")], True),
    ("Sensorineural hearing loss, bilateral", "H90.3", "FICTION, MORGAN K, MD",
     [("4/19/2021", "Active")], True),
    ("Low back pain, unspecified", "M54.50", "SAMPLE, JORDAN B, DO",
     [("9/8/2019", "Active"), ("1/17/2022", "Active"), ("6/3/2025", "Active")], True),
    ("Radiculopathy, lumbar region", "M54.16", "SAMPLE, JORDAN B, DO",
     [("1/17/2022", "Active")], False),
    ("Cervical strain", "S16.1XXA", "DEMO, CASEY L, PA-C",
     [("3/22/2020", "Active")], False),
    ("Pain in right knee", "M25.561", "SAMPLE, JORDAN B, DO",
     [("2/2/2023", "Active"), ("8/14/2025", "Active")], True),
    ("Patellofemoral pain syndrome, left knee", "M22.2X2", "SAMPLE, JORDAN B, DO",
     [("8/14/2025", "Active")], False),

    # --- mental health ---
    ("Post-traumatic stress disorder, chronic", "F43.12", "TESTCASE, AVERY P, LCSW",
     [("8/16/2022", "Active"), ("10/4/2022", "Active"), ("2/7/2024", "Active")], True),
    ("Major depressive disorder, recurrent, moderate", "F33.1",
     "TESTCASE, AVERY P, LCSW", [("10/4/2022", "Active")], True),
    ("Generalized anxiety disorder", "F41.1", "TESTCASE, AVERY P, LCSW",
     [("8/16/2022", "Active")], False),
    ("Insomnia, unspecified", "G47.00", "TESTCASE, AVERY P, LCSW",
     [("10/4/2022", "Active")], True),

    # --- respiratory / sleep ---
    ("Obstructive sleep apnea (adult)", "G47.33", "EXAMPLE, PAT A, MD",
     [("5/9/2024", "Active")], True),
    ("Mild intermittent asthma, uncomplicated", "J45.20", "FICTION, MORGAN K, MD",
     [("5/5/2021", "Active")], False),
    ("Allergic rhinitis, unspecified", "J30.9", "EXAMPLE, PAT A, MD",
     [("3/14/2019", "Active"), ("4/2/2023", "Active")], True),
    ("Chronic sinusitis, unspecified", "J32.9", "EXAMPLE, PAT A, MD",
     [("4/2/2023", "Active")], False),

    # --- neurological ---
    ("Migraine without aura, intractable", "G43.019", "EXAMPLE, PAT A, MD",
     [("2/9/2022", "Active"), ("2/28/2023", "Active")], True),

    # --- digestive ---
    ("Gastro-esophageal reflux disease without esophagitis", "K21.9",
     "SAMPLE, JORDAN B, DO", [("6/12/2023", "Active")], True),
    ("Irritable bowel syndrome, unspecified", "K58.9", "SAMPLE, JORDAN B, DO",
     [("6/12/2023", "Active")], False),

    # --- musculoskeletal, lower extremity ---
    ("Plantar fasciitis, right foot", "M72.2", "DEMO, CASEY L, PA-C",
     [("7/21/2020", "Active")], False),
    ("Sprain of left ankle, initial encounter", "S93.402A", "DEMO, CASEY L, PA-C",
     [("7/21/2020", "Active")], False),
    ("Rotator cuff tendinitis, right shoulder", "M75.31", "SAMPLE, JORDAN B, DO",
     [("11/3/2021", "Active")], False),

    # --- other commonly rated ---
    ("Scar, painful, left lower extremity", "L90.5", "DEMO, CASEY L, PA-C",
     [("7/21/2020", "Active")], False),
    ("Essential (primary) hypertension", "I10", "EXAMPLE, PAT A, MD",
     [("6/3/2025", "Active")], True),
    ("Myopia of both eyes", "H52.13", "PLACEHOLDER, RILEY N, OD",
     [("11/2/2020", "Active"), ("11/8/2024", "Active")], True),
    ("Obesity, unspecified", "E66.9", "EXAMPLE, PAT A, MD",
     [("6/3/2025", "Active")], True),
    ("Hyperlipidemia, unspecified", "E78.5", "EXAMPLE, PAT A, MD",
     [("6/3/2025", "Inactive")], False),
]

ADMIN = [
    ("Encounter for immunization", "Z23", "1/8/2022"),
    ("Encounter for general adult medical examination", "Z00.00", "6/3/2025"),
    ("Advice given about weight management", "Z71.3", "6/3/2025"),
    ("Encounter for other specified surgical aftercare", "Z48.89", "8/2/2021"),
]

PAGE_WIDTH = 84


def pad(left, right, width=PAGE_WIDTH):
    """Reproduce the two-column layout pdfplumber preserves, including the
    abbreviated-then-full provider name that _clean_provider_field() splits."""
    left = left[:width - 2]
    gap = max(2, width - len(left) - len(right))
    return f"{left}{' ' * gap}{right}"


def diagnosis_block(name, code, provider, date, status):
    surname = provider.split(",")[0]
    lines = [
        f"    Diagnosis: {name}",
        "    Secondary Description:",
        pad("    Last Reviewed Date:", "Responsible Provider:"),
        pad(f"                  {date} 09:15 CDT; {surname},", provider),
        "",
        pad(f"    Diagnosis Date: {date}", f"Status: {status}"),
        f"    Encounter Type: ; Clinic: Family Medicine; Code: {code} (ICD-10-CM); Onset: ; Comments: ;",
        "    Severity: ; Provider:",
        "",
    ]
    return "\n".join(lines)


def problem_block(name, status="Active"):
    return "\n".join([
        pad(f"    Problem Name: {name}", ""),
        pad(f"    Life Cycle Status: {status}", "Onset:"),
        "",
    ])


def build():
    pages, page = [], []

    def flush():
        if page:
            pages.append("\n".join(page))
            page.clear()

    header = [
        "                         MHS GENESIS  --  SAMPLE HEALTH RECORD EXPORT",
        f"    Patient: {PATIENT}",
        "    SSN: XXX-XX-0000                      DOD ID (EDIPI): 0000000000",
        "    THIS IS A FICTIONAL RECORD. Every name, date and diagnosis below is",
        "    invented for demonstration. It does not describe a real person.",
        "",
    ]
    page.extend(header)
    page.append("    ===== PROBLEM LIST =====")
    page.append("")
    for name, code, prov, dates, on_list in CONDITIONS:
        if on_list:
            page.append(problem_block(name))
    flush()

    page.append("    ===== CLINICAL DIAGNOSES =====")
    page.append("")
    for name, code, prov, dates, on_list in CONDITIONS:
        for date, status in dates:
            page.append(diagnosis_block(name, code, prov, date, status))
            if len("\n".join(page)) > 2200:
                flush()
                page.append("    ===== CLINICAL DIAGNOSES (continued) =====")
                page.append("")
    flush()

    page.append("    ===== ADMINISTRATIVE ENCOUNTERS =====")
    page.append("")
    for name, code, date in ADMIN:
        page.append(diagnosis_block(name, code, "EXAMPLE, PAT A, MD", date, "Active"))
    flush()

    text_parts, page_starts, offset = [], [], 0
    for p in pages:
        page_starts.append(offset)
        text_parts.append(p)
        offset += len(p) + 1
    return "\n".join(text_parts), page_starts


def write_pdf(text, path):
    """Also emit a PDF, so the sample can go through the ordinary upload path.

    The app has no demo mode -- only real records go in -- so this exists
    purely to generate documentation screenshots and to give tests a
    realistic fixture that exercises the same code a real record does.
    """
    import fitz

    doc = fitz.open()
    lines = text.split("\n")
    per_page = 46
    for i in range(0, len(lines), per_page):
        page = doc.new_page(width=612, height=792)
        page.insert_text((40, 50), "\n".join(lines[i:i + per_page]),
                         fontname="cour", fontsize=8)
    n_pages = doc.page_count
    doc.save(path)
    doc.close()
    return n_pages


def main():
    text, page_starts = build()
    os.makedirs(os.path.dirname(OUT_TXT), exist_ok=True)
    with open(OUT_TXT, "w", encoding="utf-8") as fh:
        fh.write(text)
    with open(OUT_TXT + ".pages.json", "w", encoding="utf-8") as fh:
        json.dump({"source_document": "SAMPLE_RECORD (fictional demo).pdf",
                   "page_starts": page_starts}, fh, indent=2)
    pdf_path = OUT_TXT.replace(".txt", ".pdf")
    n = write_pdf(text, pdf_path)
    print(f"{OUT_TXT}: {len(page_starts)} pages, {len(text)} chars")
    print(f"{pdf_path}: {n} pages")


if __name__ == "__main__":
    main()
