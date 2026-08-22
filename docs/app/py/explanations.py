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


_PROV_PREFIX_RE = re.compile(r"^\s*\d{1,2}/\d{1,2}/\d{4}[^;]*;\s*")


def clean_provider(raw):
    """Turn a raw provider string into a usable name.

    They arrive as "7/19/2021 13:13 CDT; DOE, DOE, JANE R, LCSW"
    — an encounter timestamp, then the surname repeated. DD 2807-1 Item 29
    explicitly asks for "name of doctor(s) and/or hospital(s)", so this is
    required content, not decoration.
    """
    name = _PROV_PREFIX_RE.sub("", raw or "").strip().strip(",")
    if not name:
        return None
    parts = [p.strip() for p in name.split(",") if p.strip()]
    # Trailing role markers ("Primary", "Attending") are routing metadata,
    # not part of the clinician's name.
    while parts and parts[-1].lower() in ("primary", "attending", "consulting"):
        parts.pop()
    deduped = [p for i, p in enumerate(parts) if i == 0 or p.upper() != parts[i - 1].upper()]
    return ", ".join(deduped) or None


def provider_names(cond, limit=3):
    seen, out = set(), []
    for raw in cond.get("providers") or []:
        name = clean_provider(raw)
        if name and name.upper() not in seen:
            seen.add(name.upper())
            out.append(name)
    return out[:limit]


def _fmt(iso):
    """MMM YYYY — how dates actually read on a completed 2807-1."""
    try:
        y, m, d = iso.split("-")
        months = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN",
                  "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]
        return f"{months[int(m) - 1]} {y}"
    except Exception:
        return iso


TREATMENT_PROMPT = "[Add treatment received]"


def _condition_sentence(cond):
    """One condition, in the shape Item 29 actually asks for.

    The form wants: dates, doctor/hospital, treatment given, and current
    medical status. Dates, providers and status come from the record.
    Treatment does not — it lives in narrative notes this parser doesn't
    read — so rather than quietly omit a field the form requires, each
    entry carries an explicit prompt for the member to fill in.
    """
    icd = f" ({cond['icd10']})" if cond.get("icd10") else ""
    span = (_fmt(cond["first_seen"]) if cond["first_seen"] == cond["last_seen"]
            else f"{_fmt(cond['first_seen'])} to {_fmt(cond['last_seen'])}")

    bits = [f"{span}: {cond['condition']}{icd}"]

    encounters = cond.get("encounters", 0)
    bits.append(f"{encounters} documented encounter{'s' if encounters != 1 else ''}")

    if cond.get("on_problem_list"):
        bits.append("Active on problem list")

    providers = provider_names(cond)
    if providers:
        bits.append("Seen by " + "; ".join(providers))

    bits.append("Status: " + ("ongoing" if cond.get("active") else "resolved/inactive"))

    return ". ".join(bits) + f". {TREATMENT_PROMPT}"


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


def _onset_note(cond, findings_by_ref):
    """If the member accepted an earlier onset from a scanned document, say so.

    This is the payoff for cross-source reconciliation: an in-service
    limitation documented years before the coded record is exactly the sort
    of thing a 2807-1 should carry, and the member has affirmed it.
    """
    f = findings_by_ref.get(cond.get("icd10"))
    if not f or f.get("resolution") != "earlier":
        return ""
    pages = ", ".join(str(p) for p in f.get("scanned_pages", [])[:4])
    return (f" Earlier documentation of this condition appears in scanned "
            f"records from approximately {f['earliest']}"
            + (f" (see scanned pages {pages})" if pages else "") + ".")


def draft_dd2807_item_29(confirmed_props, conditions_by_ref, dd_crosswalk,
                         findings=None):
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

    findings_by_ref = {f.get("icd10"): f for f in (findings or [])}

    if not by_item:
        return ""

    lines = []
    for (label, question), conds in sorted(
            by_item.items(), key=lambda kv: (int(re.match(r"\d+", kv[0][0]).group()), kv[0][0])):
        conds = sorted(_dedupe(conds), key=lambda c: c["first_seen"])
        header = f"Item {label}" + (f" ({question})" if question else "") + ":"
        body = " ".join(_condition_sentence(c) + _onset_note(c, findings_by_ref)
                        for c in conds)
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
