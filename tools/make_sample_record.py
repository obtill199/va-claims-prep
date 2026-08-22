#!/usr/bin/env python3
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
CONDITIONS = [
    ("Seasonal allergic rhinitis", "J30.2", "EXAMPLE, PAT A, MD",
     [("3/14/2022", "Active"), ("4/2/2023", "Active")], True),
    ("Lumbago", "M54.5", "SAMPLE, JORDAN B, DO",
     [("9/8/2023", "Active"), ("1/17/2024", "Active"), ("6/3/2025", "Active")], True),
    ("Sprain of left ankle", "S93.402A", "DEMO, CASEY L, PA-C",
     [("7/21/2021", "Active")], False),
    ("Tension-type headache", "G44.209", "EXAMPLE, PAT A, MD",
     [("2/9/2023", "Active"), ("2/28/2023", "Active")], False),
    ("Mild intermittent asthma", "J45.20", "FICTION, MORGAN K, MD",
     [("5/5/2022", "Active")], True),
    ("Myopia of both eyes", "H52.13", "PLACEHOLDER, RILEY N, OD",
     [("11/2/2022", "Active"), ("11/8/2024", "Active")], True),
    ("Adjustment disorder with anxiety", "F43.22", "TESTCASE, AVERY P, LCSW",
     [("8/16/2023", "Active"), ("9/6/2023", "Active"), ("10/4/2023", "Active")], True),
    ("Tinnitus, bilateral", "H93.13", "FICTION, MORGAN K, MD",
     [("4/19/2024", "Active")], False),
    ("Gastro-esophageal reflux disease", "K21.9", "SAMPLE, JORDAN B, DO",
     [("6/12/2024", "Active")], False),
    ("Right knee pain", "M25.561", "SAMPLE, JORDAN B, DO",
     [("2/2/2025", "Active"), ("8/14/2025", "Active")], False),
    ("Acute cough", "R05.1", "DEMO, CASEY L, PA-C",
     [("1/30/2023", "Active")], False),
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
    with open(OUT_TXT, "w") as fh:
        fh.write(text)
    with open(OUT_TXT + ".pages.json", "w") as fh:
        json.dump({"source_document": "SAMPLE_RECORD (fictional demo).pdf",
                   "page_starts": page_starts}, fh, indent=2)
    pdf_path = OUT_TXT.replace(".txt", ".pdf")
    n = write_pdf(text, pdf_path)
    print(f"{OUT_TXT}: {len(page_starts)} pages, {len(text)} chars")
    print(f"{pdf_path}: {n} pages")


if __name__ == "__main__":
    main()
