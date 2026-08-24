#!/usr/bin/env python3
# Copyright (c) 2026 Oliver Tillinghast.
# Licensed under the PolyForm Noncommercial License 1.0.0.
# Free for veterans, VSOs, nonprofits and government. Commercial use
# requires a separate licence -- see LICENSE, NOTICE.md, COMMERCIAL.md.
"""
tools/prep_web_forms.py — decrypt the blank forms for the browser build.

Both blank forms ship AES-encrypted with an empty password. pypdf needs the
`cryptography` package to open those, and `cryptography` is a compiled
extension that the browser build cannot rely on. Decrypting once here, at
build time, removes the dependency entirely: the browser only ever sees
plaintext PDFs and only ever needs pure-Python pypdf.

    python tools/prep_web_forms.py
"""

import io
import os

import fitz  # pymupdf, build-time only
from pypdf import PdfReader

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

PAIRS = [
    ("forms/dd2807-1.pdf", "web/forms/dd2807-1.pdf"),
    ("forms/SHA_DBQ_Part_A_Self-Assessment.pdf", "web/forms/sha_part_a.pdf"),
]


def main():
    os.makedirs(os.path.join(REPO, "web", "forms"), exist_ok=True)
    for src, dst in PAIRS:
        doc = fitz.open(os.path.join(REPO, src))
        if doc.needs_pass and not doc.authenticate(""):
            raise SystemExit(f"{src}: unexpected non-empty password")
        data = doc.write(encryption=fitz.PDF_ENCRYPT_NONE)
        doc.close()

        with open(os.path.join(REPO, dst), "wb") as fh:
            fh.write(data)

        reader = PdfReader(io.BytesIO(data))
        fields = reader.get_fields() or {}
        filled = [k for k, v in fields.items()
                  if v.get("/V") not in (None, "", "/Off", "/")]
        print(f"{dst}: encrypted={reader.is_encrypted} "
              f"fields={len(fields)} filled={len(filled)}")
        if filled:
            raise SystemExit(f"{dst}: refusing to ship a form with data in it")


if __name__ == "__main__":
    main()
