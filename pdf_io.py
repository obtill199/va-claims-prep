#!/usr/bin/env python3
"""
pdf_io.py — shared PDF open/decrypt/extract helpers.

Both real record files and dd2807-1.pdf use an empty user password
(BUILD_BRIEF.md section 6). PyMuPDF handles this transparently on open() —
no need for pypdf's decrypt() (which needs the `cryptography` package,
unavailable to build on this machine — see inspect_fields.py).
"""

import io

import fitz  # pymupdf
import pdfplumber


def open_decrypted(path):
    doc = fitz.open(path)
    if doc.needs_pass:
        if not doc.authenticate(""):
            raise ValueError(f"{path}: encrypted with a non-empty password — "
                              f"cannot process without it")
    return doc


def decrypted_bytes(path):
    """Plaintext PDF bytes — safe to hand to pypdf/pdfplumber without them
    needing to understand the encryption themselves."""
    doc = open_decrypted(path)
    return doc.write(encryption=fitz.PDF_ENCRYPT_NONE)


def extract_text(path, pages=None):
    """Text of the given 0-indexed pages (default: all), layout-preserving.

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
    return "\n".join(parts)
