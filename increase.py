#!/usr/bin/env python3
# Copyright (c) 2026 Oliver Tillinghast.
# Licensed under the PolyForm Noncommercial License 1.0.0.
# Free for veterans, VSOs, nonprofits and government. Commercial use
# requires a separate license -- see LICENSE, NOTICE.md, COMMERCIAL.md.
"""
increase.py — the plan for asking for a higher rating.

Turns "my back is worse" into "my back was last measured in 2019 and the
20 percent level asks for forward flexion between 30 and 60 degrees, so I
need a current measurement." That is the whole difference between a claim
that goes somewhere and one that does not.

Built on what the tool already extracted. Every condition it found carries
a last-seen date and an encounter count, which is exactly the signal an
increase claim runs on: is there RECENT evidence, and how much of it.

Order is deliberate. The reduction risk comes first, before anything that
might read as encouragement, because a veteran who files without knowing
an examination can go against them has been badly served no matter how
good the rest of the advice was. Capped conditions come next -- telling
somebody not to bother is often the most useful thing here. Only then the
ones with somewhere to go.
"""

import datetime

import rating_criteria as rc

RECENT_MONTHS = 12


def _months_since(iso):
    if not iso:
        return None
    try:
        seen = datetime.date.fromisoformat(str(iso)[:10])
    except ValueError:
        return None
    today = datetime.date.today()
    return (today.year - seen.year) * 12 + (today.month - seen.month)


def _evidence(condition):
    """What the records already say about how current this is."""
    months = _months_since(condition.get("last_seen"))
    encounters = condition.get("encounters") or 0
    if months is None:
        return {"months": None, "encounters": encounters, "recent": False,
                "line": "No date recorded for this in your records."}
    if months <= RECENT_MONTHS:
        line = (f"Last documented {months} month{'s' if months != 1 else ''} "
                f"ago, {encounters} encounter{'s' if encounters != 1 else ''} "
                f"in total.")
    else:
        years = round(months / 12, 1)
        line = (f"Last documented about {years} years ago "
                f"({encounters} encounter{'s' if encounters != 1 else ''}). "
                f"VA will want current evidence, so this almost certainly "
                f"needs a new examination.")
    return {"months": months, "encounters": encounters,
            "recent": months <= RECENT_MONTHS, "line": line}


def plan(conditions, ratings):
    """conditions: extracted records. ratings: {icd10 or name: percent}.

    Returns the sections a member acts on, in the order they should read
    them.
    """
    capped, actionable, unrated, general = [], [], [], []

    for cond in conditions or []:
        code = cond.get("icd10") or ""
        rated_at = ratings.get(code, ratings.get(cond.get("condition")))
        entries = rc.for_condition(code)

        # No specific criteria. Part 4 runs to hundreds of diagnostic codes
        # and no summary holds all of them -- but silence is the wrong
        # answer, so fall back to the section that governs it, the right
        # questionnaire, and what that section generally turns on.
        if not entries:
            info = rc.system_for(code)
            if info and rated_at is not None:
                general.append({
                    "condition": cond.get("condition"), "icd10": code,
                    "current": rated_at, "evidence": _evidence(cond),
                    "page": cond.get("source_page"), **info})
            continue

        for entry in entries:
            item = {
                "condition": cond.get("condition"),
                "icd10": code,
                "name": entry["name"],
                "dc": entry.get("dc"),
                "dbq": entry.get("dbq"),
                "note": entry.get("note"),
                "measures": entry.get("measures"),
                "current": rated_at,
                "evidence": _evidence(cond),
                "page": cond.get("source_page"),
            }
            if "text" in entry:                       # a pointer, not a table
                item["pointer"] = entry["text"]
                actionable.append(item)
            elif rated_at is None:
                unrated.append(item)
            elif rc.is_capped(entry, rated_at):
                capped.append(item)
            else:
                nxt = rc.next_level(entry, rated_at)
                item["next"] = {"percent": nxt[0], "requires": nxt[1]} if nxt else None
                actionable.append(item)

    return {"capped": capped, "actionable": actionable,
            "unrated": unrated, "general": general}


def worksheet(conditions, ratings, member_name=None):
    """Markdown for the package. Rendered to HTML by report_html."""
    result = plan(conditions, ratings)
    if not any(result.values()):
        return ""

    out = ["# Asking for a higher rating", ""]
    if member_name:
        out += [f"Prepared for {member_name}.", ""]

    out += ["## Read this first", "", rc.REDUCTION_WARNING, "",
            "**These are summaries of published criteria, not decisions.** "
            "Whether a rating goes up is VA's call, on a full record and an "
            "examination. Nothing here has been submitted, and nothing here "
            "is advice about what to claim. Take it to an accredited VSO.", "",
            f"Criteria last checked {rc.REVIEWED}. The rating schedule is "
            f"revised from time to time -- confirm against {rc.CFR_PART_4}.",
            ""]

    if result["capped"]:
        out += ["## Already at the maximum — do not spend time here", "",
                "There is no higher level for these. Knowing that is worth "
                "as much as anything else on this page.", ""]
        for i in result["capped"]:
            out.append(f"- **{i['name']}** — rated {i['current']}%. "
                       f"{i['note'] or ''}")
        out.append("")

    if result["actionable"]:
        out += ["## What each one would need", ""]
        for i in result["actionable"]:
            out.append(f"### {i['name']}")
            out.append("")
            if i.get("current") is not None:
                out.append(f"Currently rated **{i['current']}%** "
                           f"(diagnostic code {i['dc']}).")
            else:
                out.append(f"Diagnostic code {i['dc']}.")
            out.append("")
            out.append(f"**In your records:** {i['evidence']['line']}"
                       + (f" First appears on page {i['page']}." if i.get("page") else ""))
            out.append("")
            if i.get("pointer"):
                out += [i["pointer"], ""]
            else:
                if i.get("next"):
                    out.append(f"**The next level is {i['next']['percent']}%**, "
                               f"which asks for: {i['next']['requires']}")
                    out.append("")
                out.append(f"**What has to be measured:** {i['measures']}")
                out.append("")
            if i.get("dbq"):
                out.append(f"**Ask about this questionnaire:** {i['dbq']} "
                           f"(a DBQ). It is the form built to capture exactly "
                           f"what this rating turns on, and your own doctor "
                           f"can complete one.")
                out.append("")
            if i.get("note"):
                out += [i["note"], ""]

    if result["general"]:
        out += ["## Rated, but not in our criteria list yet", "",
                "The schedule runs to hundreds of diagnostic codes and this "
                "tool carries plain-language criteria for the ones claimed "
                "most often. These are not among them &mdash; which says "
                "nothing about your claim, only about the list. Here is the "
                "part of the schedule that governs each, and the "
                "questionnaire that captures it. The criteria themselves are "
                "public.", ""]
        for i in result["general"]:
            out.append(f"### {i['condition']}")
            out.append("")
            out.append(f"Currently rated **{i['current']}%**. Governed by "
                       f"{i['section']} ({i['system']}).")
            out.append("")
            out.append(f"**In your records:** {i['evidence']['line']}")
            out.append("")
            out.append(i["guidance"])
            out.append("")
            out.append(f"**Ask about this questionnaire:** {i['dbq']}.")
            out.append("")
            out.append(f"Read the criteria at {rc.CFR_PART_4} and take them to "
                       f"your VSO.")
            out.append("")

    if result["unrated"]:
        out += ["## Documented, but you did not list a rating for them", "",
                "Either these are not service-connected yet, or you left them "
                "out. If a condition is in your records and not rated, that is "
                "a different claim -- a new one, not an increase -- and worth "
                "raising.", ""]
        for i in result["unrated"]:
            out.append(f"- **{i['condition']}** — {i['evidence']['line']}")
        out.append("")

    out += ["## Before you file", "", rc.EFFECTIVE_DATE_NOTE, "",
            "1. Get a current examination for anything last documented more "
            "than a year ago. Without current evidence an increase claim has "
            "very little to work with.",
            "2. Ask whether a DBQ from your own doctor would help. It is often "
            "faster than waiting on a VA examination, and it is completed by "
            "somebody who already knows your history.",
            "3. Take this page to an accredited VSO before you file. They are "
            "free, and the reduction risk above is exactly the kind of thing "
            "they are there to weigh.", ""]
    return "\n".join(out)
