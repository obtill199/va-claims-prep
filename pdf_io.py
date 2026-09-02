#!/usr/bin/env python3
# Copyright (c) 2026 Oliver Tillinghast.
# Licensed under the PolyForm Noncommercial License 1.0.0.
# Free for veterans, VSOs, nonprofits and government. Commercial use
# requires a separate licence -- see LICENSE, NOTICE.md, COMMERCIAL.md.
"""
pdf_io.py — shared PDF open/decrypt/extract helpers.

Both real record files and dd2807-1.pdf use an empty user password
(BUILD_BRIEF.md section 6). PyMuPDF handles this transparently on open(, encoding="utf-8") —
no need for pypdf's decrypt() (which needs the `cryptography` package,
unavailable to build on this machine — see inspect_fields.py).
"""

import io

import fitz  # pymupdf
import pdfplumber


def open_decrypted(path):
    doc = fitz.open(path)
    if doc.needs_pass and not doc.authenticate(""):
            raise ValueError(f"{path}: encrypted with a non-empty password — "
                              f"cannot process without it")
    return doc


def decrypted_bytes(path):
    """Plaintext PDF bytes — safe to hand to pypdf/pdfplumber without them
    needing to understand the encryption themselves."""
    doc = open_decrypted(path)
    return doc.write(encryption=fitz.PDF_ENCRYPT_NONE)


def extract_text(path, pages=None):
    """Text of the given 0-indexed pages (default: all), layout-preserving."""
    text, _ = extract_text_with_page_offsets(path, pages)
    return text


def extract_text_with_page_offsets(path, pages=None):
    """Like extract_text(), but also returns page_starts: a list where
    page_starts[i] is the character offset in the returned text where the
    (i+1)-th page begins (1-indexed page numbers). Lets a downstream match
    position be turned into a page citation via bisect — required for every
    Proposal's source_page (BUILD_BRIEF.md section 4, decision 1).

    Uses pdfplumber's layout mode (pure-Python equivalent of poppler's
    `pdftotext -layout`) rather than PyMuPDF's default extraction —
    verified on the real MHS Genesis export that PyMuPDF's own text order
    scrambles this document's column-aligned diagnosis blocks badly enough
    to break extract_conditions.py's regex; pdfplumber's layout mode does
    not. See BUILD_BRIEF.md section 6.
    """
    with pdfplumber.open(io.BytesIO(decrypted_bytes(path))) as pdf:
        page_indices = range(len(pdf.pages)) if pages is None else pages
        parts = [pdf.pages[i].extract_text(layout=True) or "" for i in page_indices]

    page_starts = []
    offset = 0
    for part in parts:
        page_starts.append(offset)
        offset += len(part) + 1  # +1 for the "\n" join separator
    return "\n".join(parts), page_starts
