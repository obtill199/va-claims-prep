#!/usr/bin/env python3
# Copyright (c) 2026 Oliver Tillinghast.
# Licensed under the PolyForm Noncommercial License 1.0.0.
# Free for veterans, VSOs, nonprofits and government. Commercial use
# requires a separate licence -- see LICENSE, NOTICE.md, COMMERCIAL.md.
"""
presumptives.py — where you served, and what that changes.

For most claims the member has to show that a condition is connected to
service. For some, VA presumes it: if you served in a particular place in
a particular period and you have a particular condition, the connection is
taken as given and does not have to be argued. That is the single biggest
shortcut in the whole system, and the questionnaire never asked the one
thing that unlocks it -- where.

Branch, component and duty status were collected. None of them tell you
whether somebody breathed a burn pit in Balad or spent thirty days at
Camp Lejeune in 1985.

WHAT THIS MODULE CLAIMS, AND WHAT IT DOES NOT

Every statement here is about VA policy, not about the member. "VA
presumes X for service in Y" is a fact about the rules and is safe to
state. "You qualify" is a determination VA makes on a full record --
character of discharge, dates, unit, exposure, degree of disability -- and
this module never says it. Output is phrased as an overlap between what
the member ticked and what the records contain, handed to a VSO.

Nothing here reaches a form field. It is a conversation for an appointment.

ACCURACY AND DECAY

Presumptive lists are law and they move. The PACT Act of 2022 added most
of what is below, and more locations and conditions have been added since
by rule. Everything here carries a REVIEWED date, and the tool tells the
member to confirm against VA's own page rather than trusting a list
compiled at a point in time. A stale presumptive list is worse than none,
because it reads as authoritative.
"""

REVIEWED = "2026-08"
VA_SOURCE = "https://www.va.gov/disability/eligibility/presumptive-disability-claims/"


def _pre(code, *prefixes):
    code = (code or "").upper().replace(".", "")
    return any(code.startswith(p.replace(".", "")) for p in prefixes)


# ---------------------------------------------------------------- where
# Each entry is one thing to ask the member, phrased the way they would
# recognise it rather than the way the regulation words it.
EXPOSURES = [
    {
        "id": "swa",
        "label": "Iraq, Kuwait, Saudi Arabia, Bahrain, Qatar, Oman, the UAE "
                 "or Somalia — any time from August 1990 onward",
        "short": "Southwest Asia",
        "hint": "Includes Desert Shield and Desert Storm, and everything since.",
    },
    {
        "id": "post911",
        "label": "Afghanistan, Djibouti, Egypt, Jordan, Lebanon, Syria, Yemen "
                 "or Uzbekistan — any time from September 2001 onward",
        "short": "post-9/11 theatre",
        "hint": None,
    },
    {
        "id": "burnpit",
        "label": "I was around open-air burn pits, or other airborne hazards "
                 "like oil-well fires, sandstorms or exhaust in an enclosed space",
        "short": "airborne hazards",
        "hint": "Tick this even if you also ticked a country above.",
    },
    {
        "id": "vietnam",
        "label": "Vietnam, its inland waterways, or offshore — January 1962 "
                 "to May 1975",
        "short": "Vietnam",
        "hint": None,
    },
    {
        "id": "herbicide_other",
        "label": "The Korean DMZ (1967–1971), a Thailand air base, Laos, "
                 "Cambodia, Guam, American Samoa or Johnston Atoll",
        "short": "other herbicide locations",
        "hint": "These carry the same herbicide presumption as Vietnam.",
    },
    {
        "id": "lejeune",
        "label": "Camp Lejeune or MCAS New River, North Carolina — 30 days or "
                 "more between August 1953 and December 1987",
        "short": "Camp Lejeune",
        "hint": "The 30 days do not have to be consecutive.",
    },
    {
        "id": "radiation",
        "label": "Atmospheric nuclear testing, the occupation of Hiroshima or "
                 "Nagasaki, or a cleanup at Enewetak Atoll or Palomares",
        "short": "radiation risk activity",
        "hint": None,
    },
    {
        "id": "pow",
        "label": "I was a prisoner of war",
        "short": "former POW",
        "hint": None,
    },
]

EXPOSURE_IDS = {e["id"] for e in EXPOSURES}

# Groups that share a presumption, so a rule can name one instead of three.
TOXIC = ("swa", "post911", "burnpit")
HERBICIDE = ("vietnam", "herbicide_other")


# ------------------------------------------------------------ what for
# (exposures, matcher, plain name, what the presumption is)
#
# Matchers are deliberately broad at the category level -- "a respiratory
# condition" rather than each ICD-10 code VA lists -- because the output is
# a prompt for a VSO, and a near-miss that gets the question asked is a
# better failure than a miss that does not.
RULES = [
    {
        "id": "burnpit-respiratory",
        "exposures": TOXIC,
        "match": lambda c: _pre(c, "J30", "J31", "J32", "J40", "J41", "J42",
                                "J43", "J44", "J45", "J47", "J60", "J61",
                                "J62", "J63", "J64", "J65", "J66", "J67",
                                "J68", "J69", "J70", "J84", "J90", "J94", "D86"),
        "name": "respiratory conditions",
        "presumption": ("The PACT Act made asthma, chronic rhinitis, chronic "
                        "sinusitis, COPD, chronic bronchitis, emphysema, "
                        "bronchiolitis, interstitial lung disease, pulmonary "
                        "fibrosis, pleuritis and sarcoidosis presumptive for "
                        "this service."),
    },
    {
        "id": "burnpit-cancer",
        "exposures": TOXIC,
        "match": lambda c: _pre(c, "C"),
        "name": "cancer",
        "presumption": ("The PACT Act made many cancers presumptive for this "
                        "service — head and neck, respiratory, "
                        "gastrointestinal, reproductive, kidney, brain, "
                        "pancreatic, melanoma and lymphoma among them."),
    },
    {
        "id": "gulf-war-illness",
        "exposures": ("swa",),
        "match": lambda c: _pre(c, "R53", "G93.3", "M79.7", "K58", "R51",
                                "G47.0", "R42", "R10", "M25.5", "R63"),
        "name": "unexplained chronic symptoms",
        "presumption": ("Southwest Asia service carries a presumption for "
                        "medically unexplained chronic multisymptom illness — "
                        "chronic fatigue syndrome, fibromyalgia, irritable "
                        "bowel syndrome, and undiagnosed illnesses presenting "
                        "as fatigue, widespread pain, headache, sleep "
                        "disturbance or gastrointestinal symptoms."),
    },
    {
        "id": "herbicide-standard",
        "exposures": HERBICIDE,
        "match": lambda c: _pre(c, "E11", "E10", "I20", "I21", "I22", "I24",
                                "I25", "G20", "G21", "C", "E85", "L70.8",
                                "E80.1", "G62", "D47.2", "I10", "I11"),
        "name": "the herbicide list",
        "presumption": ("Herbicide exposure carries presumptions for type 2 "
                        "diabetes, ischaemic heart disease, Parkinson's "
                        "disease and parkinsonism, several cancers, AL "
                        "amyloidosis, chloracne, porphyria cutanea tarda, "
                        "early-onset peripheral neuropathy, MGUS, and — added "
                        "by the PACT Act — hypertension."),
    },
    {
        "id": "lejeune-conditions",
        "exposures": ("lejeune",),
        "match": lambda c: _pre(c, "C91", "C92", "C93", "C94", "C95", "D61",
                                "C67", "C64", "C22", "C90", "C82", "C83",
                                "C84", "C85", "G20"),
        "name": "the Camp Lejeune list",
        "presumption": ("Camp Lejeune water contamination carries presumptions "
                        "for adult leukaemia, aplastic anaemia and other "
                        "myelodysplastic syndromes, bladder cancer, kidney "
                        "cancer, liver cancer, multiple myeloma, "
                        "non-Hodgkin's lymphoma and Parkinson's disease."),
    },
]


def _cite(conditions, limit=3):
    bits = []
    for c in conditions[:limit]:
        name = c.get("condition") or c.get("icd10") or "?"
        if c.get("self_reported"):
            bits.append(f"{name} (you told us)")
        elif c.get("source_page"):
            bits.append(f"{name} (p. {c['source_page']})")
        else:
            bits.append(name)
    if len(conditions) > limit:
        bits.append(f"and {len(conditions) - limit} more")
    return "; ".join(bits)


def _label(exposure_id):
    for e in EXPOSURES:
        if e["id"] == exposure_id:
            return e["short"]
    return exposure_id


def find(conditions, exposures):
    """Overlaps between where they served and what the records contain.

    Returns matches -- a documented condition that falls in a presumptive
    category for an exposure they ticked -- and standing, the exposures
    they ticked that produced no match but still change what to ask about.
    """
    ticked = [e for e in (exposures or []) if e in EXPOSURE_IDS]
    if not ticked:
        return {"matches": [], "standing": [], "exposures": []}

    matches, used = [], set()
    for rule in RULES:
        overlap = [e for e in rule["exposures"] if e in ticked]
        if not overlap:
            continue
        hits = [c for c in conditions
                if c.get("icd10") and rule["match"](c["icd10"])]
        if not hits:
            continue
        used.update(overlap)
        matches.append({
            "id": rule["id"],
            "name": rule["name"],
            "presumption": rule["presumption"],
            "because": _cite(hits),
            "exposure": ", ".join(_label(e) for e in overlap),
        })

    standing = [{"id": e, "short": _label(e)} for e in ticked if e not in used]
    return {"matches": matches, "standing": standing, "exposures": ticked}


HEADLINE = (
    "A presumptive condition does not have to be argued. For most claims you "
    "have to show that a condition is connected to your service; where a "
    "presumption applies, VA takes the connection as given. It is the single "
    "biggest shortcut in the system."
)

DISCLAIMER = (
    "Whether a presumption actually applies to you is VA's determination, on "
    "your full record -- dates, unit, location, discharge, and how severe the "
    "condition is. This tool is only pointing out that what you ticked and "
    "what your records contain line up, so the question gets asked. Take it "
    "to your VSO."
)

FRESHNESS = (
    f"Presumptive lists are law and they change. This one was last checked in "
    f"{REVIEWED}. Confirm against VA's own page: {VA_SOURCE}"
)


def worksheet_section(conditions, exposures):
    found = find(conditions, exposures)
    if not found["exposures"]:
        return ""

    out = ["\n## Presumptive service connection — ASK ABOUT THIS\n",
           HEADLINE + "\n", "**" + DISCLAIMER + "**\n"]

    if found["matches"]:
        out.append("\n### What lines up\n")
        for m in found["matches"]:
            out.append(f"- **{m['name']}** — from service in {m['exposure']}.")
            out.append(f"  - In the records: {m['because']}")
            out.append(f"  - {m['presumption']}")

    if found["standing"]:
        out.append("\n### Service that carries presumptions anyway\n")
        out.append("Nothing in the records currently lines up with these, "
                   "which does not make them irrelevant: presumptive lists "
                   "grow, and a condition that appears years from now is "
                   "still covered by service that already happened.\n")
        for s in found["standing"]:
            out.append(f"- {s['short']}")

    out.append("\n" + FRESHNESS + "\n")
    return "\n".join(out) + "\n"
