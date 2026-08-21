#!/usr/bin/env python3
"""
inspect_fields.py — dump AcroForm field names/types from a blank PDF form.

Dev utility used once (per form) while authoring field_map.py. Confirms the
naming convention documented in BUILD_BRIEF.md section 2 against the real
files before field_map.py depends on it.

Usage:
    python inspect_fields.py dd2807-1.pdf -o field_names_dd2807.json
    python inspect_fields.py "SHA_DBQ_Part_A_Self-Assessment.pdf" -o field_names_sha.json
"""

import argparse
import io
import json

import fitz  # pymupdf
from pypdf import PdfReader
from pypdf.generic import IndirectObject


def _decrypted_bytes(path):
    """Return plaintext PDF bytes, decrypting with an empty password if needed.

    Uses PyMuPDF rather than pypdf's own decrypt() — pypdf needs the
    `cryptography` package for AES, which fails to build from source on this
    machine (no Homebrew/OpenSSL/pkg-config). PyMuPDF has no such dependency
    and both real record files plus dd2807-1.pdf use an empty user password
    per BUILD_BRIEF.md section 6, so this is transparent.
    """
    doc = fitz.open(path)
    if doc.needs_pass:
        if not doc.authenticate(""):
            raise ValueError(f"{path}: encrypted with a non-empty password")
    return doc.write(encryption=fitz.PDF_ENCRYPT_NONE)


def _clean(value, depth=0):
    """Make pypdf field metadata JSON-serializable. Shallow — AcroForm field
    trees can contain /Parent <-> /Kids cycles, so this does not walk them."""
    if depth > 2:
        return None
    if isinstance(value, IndirectObject):
        return _clean(value.get_object(), depth + 1)
    if isinstance(value, dict):
        return {str(k): _clean(v, depth + 1) for k, v in value.items()
                if k not in ("/Kids", "/P")}
    if isinstance(value, (list, tuple)):
        return [_clean(v, depth + 1) for v in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def _parent_name(field):
    """Just the parent field's /T (name), not its full subtree."""
    parent = field.get("/Parent")
    if not parent:
        return None
    obj = parent.get_object() if isinstance(parent, IndirectObject) else parent
    t = obj.get("/T")
    return str(t) if t is not None else None


def dump_fields(path):
    reader = PdfReader(io.BytesIO(_decrypted_bytes(path)))
    fields = reader.get_fields() or {}
    out = {}
    for name, field in fields.items():
        out[name] = {
            "field_type": _clean(field.get("/FT")),
            "value": _clean(field.get("/V")),
            "states": _clean(field.get("/_States_")),
            "parent": _parent_name(field),
        }
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pdf")
    ap.add_argument("-o", "--output", required=True)
    args = ap.parse_args()

    fields = dump_fields(args.pdf)
    with open(args.output, "w") as fh:
        json.dump(fields, fh, indent=2)

    print(f"{args.pdf}: {len(fields)} fields -> {args.output}")
    radio_groups = [n for n, f in fields.items() if f["field_type"] == "/Btn" and f["states"]]
    print(f"  {len(radio_groups)} look like radio/checkbox groups")


if __name__ == "__main__":
    main()
