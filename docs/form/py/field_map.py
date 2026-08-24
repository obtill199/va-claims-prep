#!/usr/bin/env python3
# Copyright (c) 2026 Oliver Tillinghast.
# Licensed under the PolyForm Noncommercial License 1.0.0.
# Free for veterans, VSOs, nonprofits and government. Commercial use
# requires a separate licence -- see LICENSE, NOTICE.md, COMMERCIAL.md.
"""
field_map.py — condition -> form-field mapping tables.

Deliberately a curated allow-list, not a fuzzy/keyword matcher. Given a DD
2807-1 answer carries a 5-year false-statement warning (BUILD_BRIEF.md
section 3.3), a wrong "Yes" proposed with false confidence is worse than a
condition that gets no proposal at all and falls to the member/VSO to
notice by hand. Every rule here was checked by hand against the real
conditions_worksheet.md and both forms' own question text.

Two more defaults worth stating explicitly (BUILD_BRIEF.md decisions 1 & 3):
  - Only "Yes" is ever proposed. A condition with no rule below produces
    no proposal for that item — never a proposed "No". Silence isn't
    evidence of absence.
  - A rule only fires for conditions marked active in conditions.json.
    Resolved/inactive findings aren't proposed as current "Yes" answers.

Usage:
    python field_map.py conditions.json dd2807_crosswalk.json field_names_sha.json
"""

import argparse
import json

_SHA_RESOLVED = None

# icd10 -> targets. Each target is high confidence: an exact or
# near-exact textual match between the condition and the question, checked
# by hand. Conditions not listed here (single-encounter acute symptoms,
# resolved/inactive findings, anything without a clean item match) are
# intentionally left unmapped rather than forced into a loose match.
RULES = {
    "H92.09": {  # Ear pain
        "dd2807": (11, "d"),  # "Ear, nose, or throat trouble"
        "sha_field": "CO_19_RG_21Earnoseorthroattrouble_Question_YesNo_Response",
        "sha_label": "Ear, nose, or throat trouble",
    },
    "J01.91": {  # Sinusitis (both dedup variants share this code)
        "dd2807": (10, "j"),  # "Sinusitis"
        "sha_field": "CO_17_RG_19Sinusitis_Question_YesNo_Response",
        "sha_label": "Sinusitis",
    },
    "H52.13": {  # Myopia
        "dd2807": (11, "c"),  # "Eye disorder or trouble"
        "dd2807_inferred": [((11, "f"), "corrective lenses are the standard "
                             "treatment for this refractive error")],
        "sha_field": "CO_79_RG_2Eyedisorderortrouble_Question_YesNo_Response",
        "sha_label": "Eye disorder or trouble",
    },
    "H52.223": {  # Astigmatism
        "dd2807": (11, "c"),
        "dd2807_inferred": [((11, "f"), "corrective lenses are the standard "
                             "treatment for this refractive error")],
        "sha_field": "CO_79_RG_2Eyedisorderortrouble_Question_YesNo_Response",
        "sha_label": "Eye disorder or trouble",
    },
    "F90.0": {  # ADHD
        "dd2807": (17, "g"),  # "Been evaluated or treated for a mental condition"
        "sha_field": "CO_37_RG_38MentalhealthproblemsforexampledepressionanxietyP_Question_YesNo_Response",
        "sha_label": "Mental health problems (e.g., depression, anxiety, PTSD, etc.)",
    },
    "M54.9": {  # Back pain
        "dd2807": (12, "c"),  # "Recurrent back pain or any back problem"
        "sha_field": "CO_60_RG_2BackandChest_Question_YesNo_Response",
        "sha_label": "Back and chest",
    },
    "M25.561": {  # Right knee pain
        "dd2807": (12, "i"),  # "Knee trouble"
        "dd2807_inferred": [((12, "h"), "the knee is a joint, so documented "
                             "knee pain answers the painful-joint item too")],
        "sha_field": "CO_65_RG_7LegKnee_Question_YesNo_Response",
        "sha_label": "Leg/knee",
    },
    "F17.200": {  # Nicotine dependence — no clean DD 2807-1 item (10-28
                  # doesn't ask about tobacco use directly); SHA only.
        "sha_field": "CO_67_RG_1Doyoucurrentlyusetobaccoproductscigarettescigarsp_Question_YesNo_Response",
        "sha_label": "Do you currently use tobacco products (cigarettes, cigars, pipes, etc.)?",
    },
    "E78.5": {  # Hyperlipidemia — no clean DD 2807-1 item (13.i is
                # "high/low blood sugar", a different axis); SHA only.
        "sha_field": "CO_9_RG_11Highorbadcholesterol_Question_YesNo_Response",
        "sha_label": "High or bad cholesterol",
    },
    "G47.00": {  # Insomnia — no clean SHA item found; DD 2807-1 only.
        "dd2807": (17, "d"),  # "Frequent trouble sleeping"
    },
}


# Rules that depend on the record as a whole rather than one condition.
# Each predicate gets (clinical, administrative) and returns a reason string
# when it fires, or None. These are the items a member almost always answers
# Yes to but that no single ICD-10 code maps onto.

def _documented(conditions):
    """Only conditions with a date behind them.

    Self-reported entries carry no dates, and they must not feed these
    rules anyway: "have you been treated in the last five years" is a
    question about treatment, and a member telling us their back hurts is
    not evidence that anyone treated it. Answering Yes on their behalf
    from a symptom report would be the tool making a claim they did not.
    """
    return [c for c in conditions
            if c.get("last_seen") and not c.get("self_reported")]


def _treated_within_5_years(clinical, administrative):
    from datetime import date, timedelta
    cutoff = (date.today() - timedelta(days=5 * 365)).isoformat()
    recent = [c for c in _documented(clinical) if c["last_seen"] >= cutoff]
    if not recent:
        return None
    return (f"{len(recent)} condition(s) in your records were seen by a "
            f"provider within the last 5 years, the most recent on "
            f"{max(c['last_seen'] for c in recent)}")


def _surgical_aftercare_present(clinical, administrative):
    hits = [a for a in administrative if (a.get("icd10") or "").startswith("Z48")]
    if not hits:
        return None
    return ("your records contain a surgical-aftercare encounter code "
            f"({hits[0]['icd10']}, {hits[0]['first_seen']}), which normally "
            "means a procedure was performed")


RECORD_LEVEL_RULES = [
    {"dd2807": (24, None), "predicate": _treated_within_5_years,
     "confidence": "high"},
    {"dd2807": (22, None), "predicate": _surgical_aftercare_present,
     "confidence": "medium"},
]


def load_dd2807_crosswalk(path):
    with open(path, encoding="utf-8") as fh:
        rows = json.load(fh)
    return {(r["item"], r["letter"]): r for r in rows}


def load_sha_fields(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def _library_targets(cond, crosswalk, sha_fields, sha_resolved, birth_sex):
    """Range-based matches from condition_library.py.

    RULES above stays as the curated, exact-code layer; this adds coverage
    for every code nobody hand-wrote a rule for, which is the difference
    between the tool working for one person and working for anyone.
    """
    import condition_library as cl

    targets = []
    for item, letter, sha_slug, label, confidence in cl.match(cond["icd10"], birth_sex):
        if item is not None:
            row = crosswalk.get((item, letter))
            if row and row.get("yes_field"):
                targets.append({
                    "target_form": "DD2807-1",
                    "target_field": row["yes_field"],
                    "question_text": row["question_text"],
                    "library_confidence": confidence,
                })
        if sha_slug and sha_slug in sha_resolved:
            field = sha_resolved[sha_slug]
            if field in sha_fields:
                targets.append({
                    "target_form": "SHA_PART_A",
                    "target_field": field,
                    "question_text": label,
                    "library_confidence": confidence,
                })
    return targets


def build_mapping(conditions_path, dd2807_crosswalk_path, sha_fields_path,
                  birth_sex=None):
    """Returns (matched, unmatched) where matched is a list of dicts ready
    for proposals.py, and unmatched lists conditions with no rule (printed
    for visibility, not an error — see module docstring)."""
    with open(conditions_path, encoding="utf-8") as fh:
        conditions = json.load(fh)["clinical"]

    crosswalk = load_dd2807_crosswalk(dd2807_crosswalk_path)
    sha_fields = load_sha_fields(sha_fields_path)

    global _SHA_RESOLVED
    if _SHA_RESOLVED is None:
        import condition_library as cl
        _SHA_RESOLVED, unresolved = cl.resolve_sha_fields(list(sha_fields))
        if unresolved:
            raise ValueError(
                f"condition_library SHA slugs did not resolve against the live "
                f"form: {unresolved}. The form layout may have changed.")

    matched, unmatched = [], []

    for cond in conditions:
        if not cond["active"]:
            continue
        rule = RULES.get(cond["icd10"])
        targets = []
        if not rule:
            lib = _library_targets(cond, crosswalk, sha_fields,
                                   _SHA_RESOLVED, birth_sex)
            if not lib:
                unmatched.append(cond)
                continue
            targets = lib
            matched.append({"condition": cond, "targets": targets})
            continue

        if "dd2807" in rule:
            row = crosswalk.get(rule["dd2807"])
            if row and row.get("yes_field"):
                targets.append({
                    "target_form": "DD2807-1",
                    "target_field": row["yes_field"],
                    "question_text": row["question_text"],
                })
            else:
                raise ValueError(
                    f"{cond['icd10']}: dd2807 crosswalk entry {rule['dd2807']} "
                    f"missing or has no yes_field — form layout may have changed")
        for (item_letter, why) in rule.get("dd2807_inferred", []):
            row = crosswalk.get(item_letter)
            if not (row and row.get("yes_field")):
                raise ValueError(
                    f"{cond['icd10']}: inferred dd2807 entry {item_letter} "
                    f"missing or has no yes_field")
            targets.append({
                "target_form": "DD2807-1",
                "target_field": row["yes_field"],
                "question_text": row["question_text"],
                "inferred": why,
            })
        if "sha_field" in rule:
            if rule["sha_field"] not in sha_fields:
                raise ValueError(
                    f"{cond['icd10']}: SHA field {rule['sha_field']!r} not found "
                    f"in {sha_fields_path} — form layout may have changed")
            targets.append({
                "target_form": "SHA_PART_A",
                "target_field": rule["sha_field"],
                "question_text": rule.get("sha_label"),
            })

        # Add library coverage, skipping fields the curated rules already hit.
        seen = {(t["target_form"], t["target_field"]) for t in targets}
        for t in _library_targets(cond, crosswalk, sha_fields,
                                  _SHA_RESOLVED, birth_sex):
            if (t["target_form"], t["target_field"]) not in seen:
                targets.append(t)
                seen.add((t["target_form"], t["target_field"]))

        matched.append({"condition": cond, "targets": targets})

    record_level = []
    with open(conditions_path, encoding="utf-8") as fh:
        blob = json.load(fh)
    for rl in RECORD_LEVEL_RULES:
        reason = rl["predicate"](blob["clinical"], blob["administrative"])
        if not reason:
            continue
        row = crosswalk.get(rl["dd2807"])
        if not (row and row.get("yes_field")):
            continue
        record_level.append({
            "target_form": "DD2807-1",
            "target_field": row["yes_field"],
            "question_text": row["question_text"],
            "confidence": rl["confidence"],
            "reason": reason,
        })

    return matched, unmatched, record_level


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("conditions_json")
    ap.add_argument("dd2807_crosswalk_json")
    ap.add_argument("sha_fields_json")
    args = ap.parse_args()

    matched, unmatched, record_level = build_mapping(
        args.conditions_json, args.dd2807_crosswalk_json, args.sha_fields_json)

    print(f"{len(matched)} active conditions matched a rule "
          f"({sum(len(m['targets']) for m in matched)} total field targets)")
    for m in matched:
        c = m["condition"]
        forms = ", ".join(t["target_form"] for t in m["targets"])
        print(f"  {c['icd10']}: {c['condition']!r} -> {forms}")

    print(f"\n{len(record_level)} record-level rule(s) fired:")
    for rl in record_level:
        print(f"  [{rl['confidence']}] {rl['question_text']}")

    print(f"\n{len(unmatched)} active conditions with no rule (no proposal generated):")
    for c in unmatched:
        print(f"  {c['icd10'] or '(uncoded)'}: {c['condition']!r}")


if __name__ == "__main__":
    main()
