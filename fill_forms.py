#!/usr/bin/env python3
# Copyright (c) 2026 Oliver Tillinghast.
# Licensed under the PolyForm Noncommercial License 1.0.0.
# Free for veterans, VSOs, nonprofits and government. Commercial use
# requires a separate licence -- see LICENSE, NOTICE.md, COMMERCIAL.md.
"""
fill_forms.py — confirmed.json ONLY -> filled DD 2807-1 + SHA Part A PDFs.

The only module allowed to write to either PDF, and it can only be reached
through confirm_cli.py's output. Nothing here reads conditions.json,
proposals.json, or field_map.py — if a value didn't survive confirm_cli.py's
review, it does not exist as far as this module is concerned
(BUILD_BRIEF.md section 4, decision 1).

Refuses to run if a confirmed target_field isn't present in the live blank
form — fail loud if the form layout ever changes, not silently skip.

Usage:
    python fill_forms.py confirmed.json \
        --dd2807-blank dd2807-1.pdf --sha-blank "SHA_DBQ_Part_A_Self-Assessment.pdf" \
        --out-dir .
"""

import argparse
import io
import os
import re

from pypdf import PdfReader, PdfWriter
from pypdf.generic import BooleanObject, NameObject

from pdf_io import decrypted_bytes
from schema import proposals_from_json


def _dd2807_updates(props):
    """Yes/No checkbox pairs (Yes12C / No12C) rather than a single radio
    group. Only "Yes" is ever proposed by proposals.py, but confirm_cli.py
    lets a member edit to "No" — handled here by deriving the paired
    checkbox's name (they're always siblings under the same parent) rather
    than requiring the schema to carry both field names for every item."""
    updates = {}
    for p in props:
        if p.confirmed_value == "Yes":
            updates[p.target_field] = "/1"
        elif p.confirmed_value == "No":
            twin = re.sub(r"\bYes(\d)", r"No\1", p.target_field)
            if twin == p.target_field:
                raise ValueError(
                    f"{p.id}: can't derive the 'No' checkbox from "
                    f"target_field {p.target_field!r} — expected a "
                    f"'...Yes<item>...' leaf name")
            updates[twin] = "/1"
        else:
            raise ValueError(
                f"{p.id}: DD2807-1 checkbox fields only support "
                f"confirmed_value 'Yes' or 'No', got {p.confirmed_value!r}")
    return updates


def _sha_updates(props):
    updates = {}
    for p in props:
        if p.confirmed_value not in ("Yes", "No"):
            raise ValueError(
                f"{p.id}: SHA radio fields only support confirmed_value "
                f"'Yes' or 'No', got {p.confirmed_value!r}")
        updates[p.target_field] = f"/{p.confirmed_value}"
    return updates


def fill_form(blank_path, updates, output_path):
    reader = PdfReader(io.BytesIO(decrypted_bytes(blank_path)))
    live_fields = reader.get_fields() or {}

    missing = [name for name in updates if name not in live_fields]
    if missing:
        raise ValueError(
            f"{blank_path}: {len(missing)} confirmed field name(s) not found "
            f"in the live form — layout may have changed since field_map.py "
            f"was written: {missing}")

    writer = PdfWriter()
    writer.append(reader)

    # Text fields (identity from intake.py, explanations from explanations.py)
    # carry a viewer-generated appearance. pypdf writes one, but viewers vary
    # in whether they trust it — NeedAppearances tells them to regenerate.
    # Verified either way on the real DD 2807-1 by rendering the filled page
    # and OCRing it back, but this is the safer default across viewers.
    acroform = writer.root_object.get("/AcroForm")
    if acroform is not None:
        acroform.get_object()[NameObject("/NeedAppearances")] = BooleanObject(True)
    for page in writer.pages:
        writer.update_page_form_field_values(page, updates, auto_regenerate=False)

    # DD 2807-1 is a hybrid XFA form (BUILD_BRIEF discovery): some viewers
    # (notably Adobe Acrobat) prefer the /XFA data stream over the AcroForm
    # widgets we just filled, and would show a blank form. Dropping /XFA
    # forces every viewer onto the AcroForm we actually wrote.
    acroform = writer.root_object.get("/AcroForm")
    if acroform is not None:
        acroform = acroform.get_object()
        if "/XFA" in acroform:
            del acroform["/XFA"]

    with open(output_path, "wb") as fh:
        writer.write(fh)
    return len(updates)


def assert_all_confirmed(props, source_label):
    """The gate. Nothing reaches a PDF that a human didn't confirm."""
    not_confirmed = [p for p in props if p.status not in ("confirmed", "edited")]
    if not_confirmed:
        raise ValueError(
            f"{source_label} contains {len(not_confirmed)} entries that were "
            f"never confirmed — this should only ever contain "
            f"schema.confirmed_only() output")


def fill_both(confirmed_props, dd2807_blank, sha_blank, out_dir,
              dd_extra=None, sha_extra=None):
    """Write both forms from confirmed proposals plus optional extra text
    updates (identity from intake.py, explanations from explanations.py).

    Extra updates are kept separate from `confirmed_props` on purpose:
    proposals are record-derived and gated by review, whereas intake answers
    are the member's own direct self-report and explanation drafts are
    confirmed on the review screen before they get here. Merging them into
    one list would blur which gate each value passed.
    """
    assert_all_confirmed(confirmed_props, "confirmed proposals")
    written = {}

    dd_updates = dict(dd_extra or {})
    dd_updates.update(_dd2807_updates(
        [p for p in confirmed_props if p.target_form == "DD2807-1"]))
    if dd_updates:
        path = os.path.join(out_dir, "dd2807-1_FILLED.pdf")
        written["DD2807-1"] = (fill_form(dd2807_blank, dd_updates, path), path)

    sha_updates_ = dict(sha_extra or {})
    sha_updates_.update(_sha_updates(
        [p for p in confirmed_props if p.target_form == "SHA_PART_A"]))
    if sha_updates_:
        path = os.path.join(out_dir, "sha_part_a_FILLED.pdf")
        written["SHA_PART_A"] = (fill_form(sha_blank, sha_updates_, path), path)

    return written


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("confirmed_json")
    ap.add_argument("--dd2807-blank", required=True)
    ap.add_argument("--sha-blank", required=True)
    ap.add_argument("--out-dir", default=".")
    args = ap.parse_args()

    props = proposals_from_json(args.confirmed_json)
    not_confirmed = [p for p in props if p.status not in ("confirmed", "edited")]
    if not_confirmed:
        raise ValueError(
            f"{args.confirmed_json} contains {len(not_confirmed)} entries "
            f"that were never confirmed — this file should only ever "
            f"contain schema.confirmed_only() output")

    dd_props = [p for p in props if p.target_form == "DD2807-1"]
    sha_props = [p for p in props if p.target_form == "SHA_PART_A"]

    if dd_props:
        n = fill_form(
            args.dd2807_blank, _dd2807_updates(dd_props),
            os.path.join(args.out_dir, "dd2807-1_FILLED.pdf"))
        print(f"DD2807-1: {n} field(s) written -> dd2807-1_FILLED.pdf")

    if sha_props:
        n = fill_form(
            args.sha_blank, _sha_updates(sha_props),
            os.path.join(args.out_dir, "sha_part_a_FILLED.pdf"))
        print(f"SHA Part A: {n} field(s) written -> sha_part_a_FILLED.pdf")


if __name__ == "__main__":
    main()
