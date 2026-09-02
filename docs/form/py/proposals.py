#!/usr/bin/env python3
# Copyright (c) 2026 Oliver Tillinghast.
# Licensed under the PolyForm Noncommercial License 1.0.0.
# Free for veterans, VSOs, nonprofits and government. Commercial use
# requires a separate licence -- see LICENSE, NOTICE.md, COMMERCIAL.md.
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

import self_report
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


def _self_reported_rationale(condition):
    """No dates, no encounter count, no problem list -- none of that exists
    for something the member typed. Saying "0 encounters" would read as a
    weak finding rather than what it is: a statement from the person who
    would know."""
    return ("You told us about this on the previous screen. It was not "
            "found anywhere in the records you uploaded, so there is no "
            "page to cite \u2014 which does not make it less true, and this "
            "form asks you rather than your records. Confirm the wording "
            "below is a fair description of what you meant.")


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


def build_proposals(conditions_path, dd2807_crosswalk_path, sha_fields_path,
                    birth_sex=None):
    matched, unmatched, record_level = build_mapping(
        conditions_path, dd2807_crosswalk_path, sha_fields_path, birth_sex)

    proposals = []
    unmatched = list(unmatched)
    for m in matched:
        cond = m["condition"]
        condition_ref = cond["icd10"] or cond["condition"]
        produced = 0
        for target in m["targets"]:
            question = target.get("question_text") or target["target_field"]
            # A symptom the member typed answers "do you have X". It cannot
            # answer "did someone treat you for X" -- see self_report.py.
            if cond.get("self_reported") and \
                    not self_report.answerable_from_self_report(question):
                continue
            proposals.append(Proposal(
                id=_stable_id(condition_ref, cond["condition"],
                              target["target_form"], target["target_field"]),
                condition_ref=condition_ref,
                target_form=target["target_form"],
                target_field=target["target_field"],
                question_text=question,
                proposed_value="Yes",
                source_document=cond["source_document"],
                source_page=cond["source_page"],
                # "medium" for inferred targets: the condition is coded, but
                # the link to this particular question is our inference, not
                # something the record states. Decision 3 says never present
                # a weaker extraction as fact.
                # A library rule carries its own confidence: acute symptom
                # codes mapped to chronic-condition questions are "low" and
                # therefore default to Leave blank on the review screen.
                confidence=("self-reported" if cond.get("self_reported")
                            else (target.get("library_confidence")
                                  or ("medium" if target.get("inferred") else "high"))),
                extraction_method="structured",
                rationale=(
                    _self_reported_rationale(cond) if cond.get("self_reported")
                    else _rationale(cond)
                    + (" This one is an inference rather than something your "
                       "records state directly: " + target["inferred"] + "."
                       if target.get("inferred") else "")
                ),
            ))
            produced += 1

        # Every target was suppressed -- a self-report whose only form
        # questions asked about treatment it never had. It must still reach
        # the worksheet: dropping it here would lose the one thing the
        # member went out of their way to tell us, and lose it silently.
        if not produced:
            unmatched.append(cond)
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


def proposals_from_prompts(prompts):
    """Turn keyword mentions into reviewable proposals.

    These used to be a separate "check these by hand" list, which meant the
    member had to open a PDF, find the page, decide, and mark the form
    themselves -- for the majority of the questions they would end up
    answering Yes. Measured against a real completed 2807-1, every one of
    these pointed at a question the member really did answer Yes.

    They are proposals now so the answer is one click instead of a manual
    edit, but they are deliberately the weakest tier:
      - confidence "low": a word appearing near a question is not a
        diagnosis, and must never be presented as one;
      - the review screen defaults them to "Leave blank", so skipping the
        decision leaves the box empty rather than making a claim.
    """
    out = []
    for pr in prompts:
        terms = ", ".join(pr["matched_terms"][:4])
        pages = ", ".join(str(x) for x in pr["pages"][:3])
        out.append(Proposal(
            id=_stable_id("MENTION", pr["item"], "DD2807-1", pr["target_field"]),
            condition_ref="MENTION",
            target_form="DD2807-1",
            target_field=pr["target_field"],
            question_text=pr["question_text"],
            proposed_value="Yes",
            source_document=pr.get("source_document") or "your records",
            source_page=pr["pages"][0] if pr.get("pages") else None,
            confidence="low",
            extraction_method=pr.get("method", "structured"),
            rationale=(
                f"No diagnosis in your records is coded to this question, so "
                f"this is not a finding — but the words \"{terms}\" do appear "
                f"{pr['mentions']} time{'s' if pr['mentions'] != 1 else ''}"
                + (f" (pages {pages})" if pages else "")
                + ". Worth checking; left blank unless you say otherwise."),
        ))
    return out


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
