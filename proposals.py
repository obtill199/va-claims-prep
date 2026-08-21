#!/usr/bin/env python3
"""
proposals.py — conditions.json + field_map.py -> proposals.json.

Pure function of extracted conditions and the field-mapping rules; no PDF
I/O happens here. This is the reviewable intermediate BUILD_BRIEF.md section
4 requires: every value is a *proposal* with its source citation and
confidence, never something written to a form. confirm_cli.py is the only
thing allowed to turn a Proposal into something fill_forms.py can act on.

Usage:
    python proposals.py conditions.json dd2807_crosswalk.json field_names_sha.json -o proposals.json
"""

import argparse
import hashlib

from field_map import build_mapping
from schema import Proposal, proposals_to_json


def _stable_id(condition_ref, condition_name, target_form, target_field):
    """Includes the condition *name*, not just its code.

    Distinct conditions can share an ICD-10 code — the real record has two
    J01.91 sinusitis entries with different names and dates — and
    condition_ref is that code. Keying on the code alone gave both the same
    id, which collapsed them into one radio-button group in the review UI
    and made a single click silently decide both.
    """
    raw = f"{condition_ref}|{condition_name}|{target_form}|{target_field}"
    return hashlib.sha256(raw.encode()).hexdigest()[:12]


def _rationale(condition):
    bits = [
        f"{condition['condition']} ({condition['icd10']}) in "
        f"{condition['source_document']}",
        f"first documented {condition['first_seen']}",
        f"{condition['encounters']} encounter"
        f"{'s' if condition['encounters'] != 1 else ''}",
    ]
    if condition["on_problem_list"]:
        bits.append("on clinician-curated problem list")
    return "; ".join(bits) + "."


def build_proposals(conditions_path, dd2807_crosswalk_path, sha_fields_path):
    matched, unmatched = build_mapping(
        conditions_path, dd2807_crosswalk_path, sha_fields_path)

    proposals = []
    for m in matched:
        cond = m["condition"]
        condition_ref = cond["icd10"] or cond["condition"]
        for target in m["targets"]:
            proposals.append(Proposal(
                id=_stable_id(condition_ref, cond["condition"],
                              target["target_form"], target["target_field"]),
                condition_ref=condition_ref,
                target_form=target["target_form"],
                target_field=target["target_field"],
                proposed_value="Yes",
                source_document=cond["source_document"],
                source_page=cond["source_page"],
                confidence="high",  # curated rule + structured (regex, not OCR) extraction
                extraction_method="structured",
                rationale=(
                    f"{_rationale(cond)} Matched to "
                    f"{target['question_text'] or target['target_field']!r} "
                    f"via field_map.py rule for {cond['icd10']}."
                ),
            ))
    return proposals, unmatched


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("conditions_json")
    ap.add_argument("dd2807_crosswalk_json")
    ap.add_argument("sha_fields_json")
    ap.add_argument("-o", "--output", default="proposals.json")
    args = ap.parse_args()

    proposals, unmatched = build_proposals(
        args.conditions_json, args.dd2807_crosswalk_json, args.sha_fields_json)

    proposals_to_json(proposals, args.output)
    print(f"{len(proposals)} proposals (all status=pending) -> {args.output}")
    print(f"{len(unmatched)} active conditions had no rule and produced no proposal")


if __name__ == "__main__":
    main()
