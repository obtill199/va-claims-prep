#!/usr/bin/env python3
"""
explanations.py — draft the "explain your YES answers" text.

DD 2807-1 states plainly: "Every item marked 'YES' must be fully explained
in Item 29 on Page 2." SHA Part A has a paired free-text box per question
(CO_<n>_TA_..._YES_IFYESEXPLAIN) alongside each yes/no radio. A package
that checks Yes boxes and leaves those blank is an incomplete form, so
this drafts them from the same confirmed conditions that produced the Yes.

These are *drafts*. They're presented on the review screen for the member
to edit or reject before anything is written, because they land on a form
carrying a five-year false-statement warning (BUILD_BRIEF.md section 3.3)
and because the wording is generated, not something the member said.

Every draft states only what the record actually shows — condition name,
ICD-10, documented date range, encounter count, and source citation. It
never characterizes severity, causation, or service-connection: that's
the VSO's and the member's judgment, not this tool's.
"""

import re
from collections import defaultdict

# CO_<n>_RG_...  ->  CO_<n>_TA_..._YES_IFYESEXPLAIN. Verified this session:
# all 87 SHA yes/no response fields have exactly one matching explain field
# sharing their CO_<n>_ prefix, so the pairing is derivable rather than
# another hand-maintained table that could drift out of sync.
_CO_PREFIX_RE = re.compile(r"^CO_(\d+)_")


def sha_explain_field_for(response_field, sha_field_names):
    """The IFYESEXPLAIN field paired with a SHA yes/no field, or None."""
    m = _CO_PREFIX_RE.match(response_field)
    if not m:
        return None
    prefix = f"CO_{m.group(1)}_"
    matches = [name for name in sha_field_names
               if name.startswith(prefix) and "IFYESEXPLAIN" in name]
    return matches[0] if len(matches) == 1 else None


def _condition_sentence(cond):
    """One condition, stated as what the record shows and nothing more."""
    icd = f" ({cond['icd10']})" if cond.get("icd10") else ""
    if cond["first_seen"] == cond["last_seen"]:
        when = f"documented {cond['first_seen']}"
    else:
        when = f"documented {cond['first_seen']} through {cond['last_seen']}"

    encounters = cond.get("encounters", 0)
    enc = f"{encounters} encounter{'s' if encounters != 1 else ''}"

    parts = [f"{cond['condition']}{icd}: {when}, {enc}"]
    if cond.get("on_problem_list"):
        parts.append("listed on the clinician-maintained problem list")

    citation = cond.get("source_document") or "service treatment record"
    page = cond.get("source_page")
    parts.append(f"see {citation}" + (f", p. {page}" if page else ""))

    return "; ".join(parts) + "."


def sha_explain_labels(sha_field_names):
    """{explain_field: human-readable question} for the review screen.

    SHA field names embed a truncated, space-stripped slug of the question
    (CO_19_TA_3_21EARNOSEORTHROATTROUBLE_YES_IFYESEXPLAIN), which is not
    something to put in front of a person. field_map.py already carries a
    written label for every question it maps, so reuse those.
    """
    from field_map import RULES
    labels = {}
    for rule in RULES.values():
        response_field = rule.get("sha_field")
        label = rule.get("sha_label")
        if not response_field or not label:
            continue
        explain_field = sha_explain_field_for(response_field, sha_field_names)
        if explain_field:
            labels[explain_field] = label
    return labels


def draft_sha_explanations(confirmed_props, conditions_by_ref, sha_field_names):
    """{explain_field_name: draft_text} for confirmed SHA "Yes" answers."""
    by_field = defaultdict(list)
    for p in confirmed_props:
        if p.target_form != "SHA_PART_A" or p.confirmed_value != "Yes":
            continue
        by_field[p.target_field].extend(conditions_by_ref.get(p.condition_ref, []))

    drafts = {}
    for response_field, conds in by_field.items():
        explain_field = sha_explain_field_for(response_field, sha_field_names)
        if not explain_field:
            continue
        conds = sorted(_dedupe(conds), key=lambda c: c["first_seen"])
        drafts[explain_field] = " ".join(_condition_sentence(c) for c in conds)
    return drafts


def draft_dd2807_item_29(confirmed_props, conditions_by_ref, dd_crosswalk):
    """One combined Item 29 block. The form has a single explanation field
    for all YES answers, so each entry is labelled with its item number."""
    field_to_item = {}
    for row in dd_crosswalk:
        if row.get("yes_field"):
            label = f"{row['item']}{row['letter'] or ''}"
            field_to_item[row["yes_field"]] = (label, row.get("question_text"))

    by_item = defaultdict(list)
    for p in confirmed_props:
        if p.target_form != "DD2807-1" or p.confirmed_value != "Yes":
            continue
        entry = field_to_item.get(p.target_field)
        if entry:
            by_item[entry].extend(conditions_by_ref.get(p.condition_ref, []))

    if not by_item:
        return ""

    lines = []
    for (label, question), conds in sorted(
            by_item.items(), key=lambda kv: (int(re.match(r"\d+", kv[0][0]).group()), kv[0][0])):
        conds = sorted(_dedupe(conds), key=lambda c: c["first_seen"])
        header = f"Item {label}" + (f" ({question})" if question else "") + ":"
        body = " ".join(_condition_sentence(c) for c in conds)
        lines.append(f"{header} {body}")

    return "\n\n".join(lines)


def conditions_by_ref(conditions):
    """Index conditions the way Proposal.condition_ref refers to them.

    Maps to a *list*, not a single condition: distinct conditions can share
    an ICD-10 code (the real record has two J01.91 sinusitis entries with
    different names), and condition_ref is that code. A one-to-one dict
    silently dropped one of them and made the other's text appear twice.
    """
    index = defaultdict(list)
    for c in conditions:
        index[c["icd10"] or c["condition"]].append(c)
    return dict(index)


def _dedupe(conds):
    """Same condition reached via two proposals shouldn't be stated twice."""
    seen, out = set(), []
    for c in conds:
        key = (c.get("icd10"), c["condition"], c["first_seen"])
        if key not in seen:
            seen.add(key)
            out.append(c)
    return out
