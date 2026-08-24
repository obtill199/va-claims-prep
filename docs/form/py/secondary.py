#!/usr/bin/env python3
"""
secondary.py — the questions a VSO would ask that the records do not raise.

VA can grant service connection for a condition caused or aggravated by an
already service-connected one. It is called secondary service connection,
it is worth as much as any other grant, and most people filing for the
first time have never heard of it. Somebody with a documented back injury
and documented depression routinely claims two unrelated things, when the
question of whether one followed the other was never put to them.

WHAT THIS MODULE DOES NOT DO

It does not decide that two conditions are connected. It cannot: a nexus
is a medical opinion, it needs a clinician, and no amount of code reading
ICD-10 codes substitutes for one. Nothing here reaches a form field, no
box is ever checked from it, and no output of this module changes a single
answer on DD 2807-1 or the SHA.

What it does is narrower and defensible: it reports what is already in the
member's own records, names the pairings where this question is commonly
raised, and hands that to the person qualified to answer it. Every line it
emits is a question addressed to a VSO, not a conclusion addressed to the
member.

The distinction matters enough to be structural rather than editorial --
this module produces `question` strings and has no vocabulary for
asserting a link. There is no code path here that outputs "is caused by".

Pairings are limited to ones a VSO handles routinely. This is deliberately
not an exhaustive medical cross-reference: a long list of speculative
links would bury the few worth the member's appointment time, and would
edge from reporting toward advising.
"""


def _pre(code, *prefixes):
    code = (code or "").upper().replace(".", "")
    return any(code.startswith(p.replace(".", "")) for p in prefixes)


# Each rule names two things the records might contain and the question a
# VSO would put to the member about them.
#
#   match      what the primary looks like, by ICD-10
#   partner    what the other side looks like -- used to notice when BOTH
#              are already documented, which is the stronger case
#   ask        the plain-language name of what to ask about
#   question   the exact sentence handed to the member. Always a question.
#   prompt     id of a self_report catalog prompt, when the partner is
#              something the member would notice rather than be told
LINKS = [
    {
        "id": "osa-upper-airway",
        "primary_label": "chronic rhinitis or sinusitis",
        "match": lambda c: _pre(c, "J30", "J31", "J32", "J34.2"),
        "partner": lambda c: _pre(c, "G47.3"),
        "ask": "sleep apnea",
        "prompt": "apnea",
        "question": ("Your records document chronic upper-airway trouble. Does "
                     "the sleep apnea question belong here — either as a "
                     "condition to be evaluated for, or as secondary to the "
                     "airway condition?"),
    },
    {
        "id": "osa-mental-health",
        "primary_label": "a mental health condition",
        "match": lambda c: _pre(c, "F41", "F43", "F32", "F33"),
        "partner": lambda c: _pre(c, "G47.3"),
        "ask": "sleep apnea and sleep impairment",
        "prompt": "apnea",
        "question": ("Sleep problems and mental health conditions are commonly "
                     "claimed together. Should sleep be evaluated separately "
                     "here, or as secondary?"),
    },
    {
        "id": "htn-osa",
        "primary_label": "sleep apnea",
        "match": lambda c: _pre(c, "G47.3"),
        "partner": lambda c: _pre(c, "I10", "I11", "I12", "I13"),
        "ask": "high blood pressure",
        "prompt": "bp",
        "question": ("Both sleep apnea and blood pressure appear here. Is the "
                     "blood pressure worth raising as secondary rather than on "
                     "its own?"),
    },
    {
        "id": "mental-chronic-pain",
        "primary_label": "a long-running painful condition",
        "match": lambda c: _pre(c, "M54", "M25", "M17", "M23", "M75", "M79", "G89"),
        "partner": lambda c: _pre(c, "F32", "F33", "F41", "F43"),
        "ask": "depression, anxiety or sleep disturbance",
        "prompt": "depression",
        "question": ("Chronic pain and mood are commonly claimed together, in "
                     "either direction. Is that worth raising — and if a "
                     "mental health condition is already documented, should it "
                     "be claimed as secondary to the pain?"),
    },
    {
        "id": "radiculopathy-spine",
        "primary_label": "a back or neck condition",
        "match": lambda c: _pre(c, "M54", "M51", "M50", "M43"),
        "partner": lambda c: _pre(c, "M54.1", "G57", "G58", "R20"),
        "ask": "numbness, tingling or shooting pain down a limb",
        "prompt": "numb",
        "question": ("Nerve symptoms running from the spine into an arm or leg "
                     "are often rated separately from the spine condition "
                     "itself. Has that been looked at?"),
    },
    {
        "id": "opposite-joint",
        "primary_label": "a knee, ankle or hip condition",
        "match": lambda c: _pre(c, "M17", "M19.07", "M23", "M25.5", "M25.6", "S83", "S93"),
        "partner": lambda c: _pre(c, "M17", "M16", "M54"),
        "ask": "the other side, and the back",
        "prompt": "joints",
        "question": ("A joint injury on one side commonly leads to a claim about "
                     "the other side or the lower back, from years of favouring "
                     "it. Is that worth raising?"),
    },
    {
        "id": "gerd-nsaids",
        "primary_label": "a painful condition usually managed with anti-inflammatories",
        "match": lambda c: _pre(c, "M54", "M25", "M17", "M79", "G89"),
        "partner": lambda c: _pre(c, "K21", "K25", "K26", "K29"),
        "ask": "stomach trouble from long-term pain medication",
        "prompt": "reflux",
        "question": ("A condition can also be secondary to the MEDICATION for a "
                     "service-connected condition, not only to the condition "
                     "itself. If years of anti-inflammatories are behind the "
                     "stomach trouble, is that worth raising?"),
    },
    {
        "id": "migraine-neck-tbi",
        "primary_label": "a neck condition or a head injury",
        "match": lambda c: _pre(c, "M50", "M54.2", "S06", "F07.8"),
        "partner": lambda c: _pre(c, "G43", "G44", "R51"),
        "ask": "headaches",
        "prompt": "headache",
        "question": ("Headaches following a neck injury or a head injury are "
                     "commonly raised as secondary. Does that apply here?"),
    },
    {
        "id": "neuropathy-diabetes",
        "primary_label": "diabetes",
        "match": lambda c: _pre(c, "E10", "E11", "E13"),
        "partner": lambda c: _pre(c, "G62", "G63", "E11.4", "E10.4"),
        "ask": "numbness or burning in the feet and hands",
        "prompt": "numb",
        "question": ("Nerve damage in the feet and hands is commonly claimed "
                     "alongside diabetes. Has that been raised?"),
    },
    {
        "id": "ibs-mental",
        "primary_label": "a mental health condition",
        "match": lambda c: _pre(c, "F41", "F43", "F32", "F33"),
        "partner": lambda c: _pre(c, "K58", "K59"),
        "ask": "ongoing bowel trouble",
        "prompt": "gut",
        "question": ("Bowel conditions are commonly claimed as secondary to a "
                     "mental health condition. Is that worth raising?"),
    },
    {
        "id": "ed-mental-meds",
        "primary_label": "a mental health condition, or the medication for one",
        "match": lambda c: _pre(c, "F41", "F43", "F32", "F33"),
        "partner": lambda c: _pre(c, "N52", "F52"),
        "ask": "sexual dysfunction",
        "prompt": "sexual",
        "question": ("Sexual dysfunction secondary to a mental health condition "
                     "or its medication is common, routinely handled, and "
                     "rarely mentioned. Worth raising?"),
    },
    {
        "id": "tinnitus-hearing",
        "primary_label": "hearing loss or noise exposure",
        "match": lambda c: _pre(c, "H90", "H91", "Z57.0"),
        "partner": lambda c: _pre(c, "H93.1"),
        "ask": "tinnitus",
        "prompt": "tinnitus",
        "question": ("Tinnitus is rated separately from hearing loss and is "
                     "commonly claimed alongside it. Has it been raised?"),
    },
]


def _codes(conditions):
    return [(c.get("icd10") or "", c) for c in conditions]


def find(conditions):
    """Which questions the records make worth asking.

    Returns a list of dicts, each carrying:
        question     the sentence to put to the VSO
        ask          plain name of what it is about
        because      what in the record raised it, with citations
        both_present True when the partner condition is ALSO documented,
                     which makes it a question about how to claim what is
                     already there rather than about something new
        prompt       self_report catalog id, when the partner is something
                     the member would notice rather than be told
    """
    coded = _codes(conditions)
    out = []
    for link in LINKS:
        primaries = [c for code, c in coded if code and link["match"](code)]
        if not primaries:
            continue
        partners = [c for code, c in coded if code and link["partner"](code)]

        # Don't raise a pairing whose primary IS the partner -- a single
        # back condition matching both sides of the spine rule is not two
        # things to ask about.
        primaries = [c for c in primaries if c not in partners]
        if not primaries:
            continue

        out.append({
            "id": link["id"],
            "question": link["question"],
            "ask": link["ask"],
            "prompt": link.get("prompt"),
            "both_present": bool(partners),
            "because": _cite(primaries),
            "partner_because": _cite(partners) if partners else None,
        })
    return _prioritise(out)


def _prioritise(items):
    """One entry per thing being asked about, strongest first.

    Several rules can point at the same question from different directions
    -- sleep apnea is reached from an airway condition and again from a
    mental health condition -- and printing both spends the member's
    appointment time twice on one topic. A VSO appointment is short, and a
    long list of maybes buries the two or three worth raising.

    Where a topic is reached more than once, the version whose partner is
    ALSO documented wins: "both of these are already in your file, should
    they be claimed as related" is a sharper question than "this sometimes
    goes with that".
    """
    best = {}
    for item in items:
        key = item.get("prompt") or item["id"]
        current = best.get(key)
        if current is None or (item["both_present"] and not current["both_present"]):
            best[key] = item
        elif item["both_present"] == current["both_present"]:
            # Same strength, different evidence: keep both citations so the
            # VSO can see every route into the question.
            extra = item["because"]
            if extra and extra not in current["because"]:
                current["because"] += "; " + extra
    ordered = sorted(best.values(), key=lambda i: (not i["both_present"], i["ask"]))
    return ordered


def _cite(conditions, limit=3):
    bits = []
    for c in conditions[:limit]:
        name = c.get("condition") or c.get("icd10") or "?"
        page = c.get("source_page")
        if c.get("self_reported"):
            bits.append(f"{name} (you told us)")
        elif page:
            bits.append(f"{name} (p. {page})")
        else:
            bits.append(name)
    if len(conditions) > limit:
        bits.append(f"and {len(conditions) - limit} more")
    return "; ".join(bits)


def worksheet_section(conditions):
    """Markdown for the conditions worksheet -- the page the VSO reads."""
    items = find(conditions)
    if not items:
        return ""

    out = ["\n## Questions about how these conditions connect\n",
           "VA can service-connect a condition that was caused or aggravated "
           "by another one, including by the medication for another one. It "
           "is worth the same as any other grant and is routinely missed by "
           "people filing for the first time.\n",
           "**These are questions, not findings.** This tool cannot determine "
           "that two conditions are related -- that is a medical opinion and "
           "it needs a clinician. What follows is drawn from what is already "
           "in the records below, so the question can at least get asked.\n"]

    both = [i for i in items if i["both_present"]]
    single = [i for i in items if not i["both_present"]]

    if both:
        out.append("\n### Both already documented\n")
        out.append("For these, both sides are already in the records. The "
                   "question is not whether the member has them -- it is "
                   "whether they should be claimed as related rather than "
                   "separately.\n")
        for i in both:
            out.append(f"- **{i['ask']}** — {i['question']}")
            out.append(f"  - In the records: {i['because']}")
            out.append(f"  - Also documented: {i['partner_because']}")

    if single:
        out.append("\n### Worth asking about\n")
        for i in single:
            out.append(f"- **{i['ask']}** — {i['question']}")
            out.append(f"  - In the records: {i['because']}")

    return "\n".join(out) + "\n"
