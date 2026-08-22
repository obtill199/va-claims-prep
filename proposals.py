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


def _doctors(condition):
    """Who diagnosed it. DD 2807-1 Item 29 asks for this by name, and a
    member reviewing a proposal should see who it came from."""
    from explanations import provider_names
    return provider_names(condition)


def _fmt_date(iso):
    try:
        y, m, d = iso.split("-")
        months = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN",
                  "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]
        return f"{int(d)} {months[int(m) - 1]} {y}"
    except Exception:
        return iso


def _rationale(condition):
    """Plain English, for the person deciding.

    Deliberately excludes internal identifiers (module names, rule keys,
    AcroForm field names) and the source filename — the filename belongs to
    the citation line at the foot of the card, not in the middle of a
    sentence the member is trying to read.
    """
    icd = f" ({condition['icd10']})" if condition.get("icd10") else ""
    bits = [f"{condition['condition']}{icd}"]

    if condition["first_seen"] == condition["last_seen"]:
        bits.append(f"documented {_fmt_date(condition['first_seen'])}")
    else:
        bits.append(f"documented {_fmt_date(condition['first_seen'])} "
                    f"to {_fmt_date(condition['last_seen'])}")

    encounters = condition.get("encounters", 0)
    bits.append(f"{encounters} encounter{'s' if encounters != 1 else ''}")

    if condition.get("on_problem_list"):
        bits.append("still on your problem list")

    text = ", ".join(bits) + "."

    doctors = _doctors(condition)
    if doctors:
        text += (" Diagnosed by " + "; ".join(doctors) + ".")
    return text


def build_proposals(conditions_path, dd2807_crosswalk_path, sha_fields_path):
    matched, unmatched, record_level = build_mapping(
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
                question_text=(target.get("question_text")
                               or target["target_field"]),
                proposed_value="Yes",
                source_document=cond["source_document"],
                source_page=cond["source_page"],
                # "medium" for inferred targets: the condition is coded, but
                # the link to this particular question is our inference, not
                # something the record states. Decision 3 says never present
                # a weaker extraction as fact.
                confidence="medium" if target.get("inferred") else "high",
                extraction_method="structured",
                rationale=(
                    _rationale(cond)
                    + (" This one is an inference rather than something your "
                       "records state directly: " + target["inferred"] + "."
                       if target.get("inferred") else "")
                ),
            ))
    for rl in record_level:
        proposals.append(Proposal(
            id=_stable_id("RECORD-LEVEL", rl["target_field"],
                          rl["target_form"], rl["target_field"]),
            condition_ref="RECORD-LEVEL",
            target_form=rl["target_form"],
            target_field=rl["target_field"],
            question_text=rl["question_text"],
            proposed_value="Yes",
            source_document=(matched[0]["condition"]["source_document"]
                             if matched else "your records"),
            source_page=None,
            confidence=rl["confidence"],
            extraction_method="structured",
            rationale=(f"This one comes from your records as a whole rather "
                       f"than a single diagnosis: {rl['reason']}."),
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
