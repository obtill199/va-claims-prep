#!/usr/bin/env python3
"""
ingest.py — DoD health record PDF -> the .txt format extract_conditions.py
already parses.

extract_conditions.py's regex parser was built and verified against
structured text exports (MHS Genesis). This module gets it there from a raw
PDF: decrypt-if-needed, then layout-aware text extraction. See
BUILD_BRIEF.md section 6.

Not a fit for the scanned/OCR-poor legacy files (AF forms, STRs) — those
are Milestone 3's problem. This module still runs on them so the pipeline
doesn't silently skip a file, but expect near-zero structured yield and
says so.

Usage:
    python ingest.py record.pdf -o record.txt
"""

import argparse

from pdf_io import extract_text


def ingest(pdf_path, output_path):
    text = extract_text(pdf_path)
    with open(output_path, "w", encoding="utf-8") as fh:
        fh.write(text)
    return len(text)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pdf")
    ap.add_argument("-o", "--output", required=True)
    args = ap.parse_args()

    n_chars = ingest(args.pdf, args.output)
    print(f"{args.pdf}: {n_chars} chars -> {args.output}")


if __name__ == "__main__":
    main()
