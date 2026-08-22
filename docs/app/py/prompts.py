#!/usr/bin/env python3
"""
prompts.py — "your records mention this; does it apply?"

Measured against a real completed DD 2807-1, the coded-diagnosis mapping in
field_map.py reaches every item it claims (no false positives) but only
about a third of what the member actually answered Yes to. The gap is not a
mapping bug: the rest lives in narrative notes, PHA self-reports and scanned
AF forms — text the structured "Diagnosis:" parser never sees. Real examples
from that comparison: tinnitus, blood pressure, headaches, ER visits, a
duty-limiting profile, and counseling history.

Auto-answering those from a keyword hit would trade away the property that
matters most on a form carrying a five-year false-statement warning. So this
module does the other useful thing: it reports that the words appear, on
which page, and which question they might bear on — and stops there. These
are never proposals, never pre-checked, and never written to a form. The
member decides, with the page number in hand.
"""

import re

# (item, letter) -> keywords. Deliberately narrow and clinical; a term only
# earns a place here if seeing it in a service record would genuinely make a
# reviewer ask the question.
PROMPT_KEYWORDS = {
    (11, "g"): ["tinnitus", "hearing loss", "hearing aid", "audiogram"],
    (12, "a"): ["shoulder", "elbow", "wrist"],
    (12, "f"): ["plantar", "foot pain", "bunion", "toe fracture", "tibialis"],
    (12, "g"): ["duty limiting", "duty limitation", "profile", "no lifting",
                "no bending", "restricted duty", "assistive device"],
    (12, "k"): ["crutches", "knee brace", "back support", "orthotic", "brace"],
    (12, "l"): ["kyphosis", "scoliosis", "curvature", "deformity"],
    (12, "n"): ["fracture", "broken bone"],
    (13, "a"): ["reflux", "gerd", "heartburn", "indigestion"],
    (14, "b"): ["weight gain", "weight loss", "bmi", "obesity"],
    (14, "d"): ["cyst", "tumor", "growth", "lipoma"],
    (15, "b"): ["headache", "migraine"],
    (15, "g"): ["concussion", "loss of consciousness", "unconscious"],
    (16, "f"): ["hypertension", "blood pressure"],
    (17, "a"): ["anxiety", "panic attack", "gad-7"],
    (17, "c"): ["memory loss", "poor concentration", "distractib"],
    (17, "e"): ["counseling", "behavioral health", "therapy session"],
    (17, "f"): ["depression", "phq-9", "depressive"],
    (17, "i"): ["substance", "alcohol abuse", "prescription drug"],
    (20, None): ["emergency room", "emergency department", "urgent care"],
    (21, None): ["hospital", "inpatient", "admitted"],
    (22, None): ["surgery", "surgical", "operation", "adenoidectomy",
                 "extraction"],
    (23, None): ["injury", "strain", "sprain", "tear"],
}

MAX_PAGES_REPORTED = 4


def _page_for(pos, page_starts):
    import bisect
    return bisect.bisect_right(page_starts, pos) if page_starts else None


def find_prompts(text, crosswalk_rows, page_starts=None, already_proposed=()):
    """Keyword mentions that map to a form item nothing else answered.

    `already_proposed` are field names the coded rules already cover — a
    prompt for a question that already has a real proposal would be noise.
    """
    by_item = {(r["item"], r["letter"]): r for r in crosswalk_rows}
    lowered = text.lower()
    out = []

    for item_letter, keywords in PROMPT_KEYWORDS.items():
        row = by_item.get(item_letter)
        if not row or not row.get("yes_field"):
            continue
        if row["yes_field"] in already_proposed:
            continue

        hits = []
        for kw in keywords:
            for m in re.finditer(re.escape(kw), lowered):
                page = _page_for(m.start(), page_starts)
                hits.append((kw, page))

        if not hits:
            continue

        terms = sorted({kw for kw, _ in hits})
        pages = sorted({p for _, p in hits if p})[:MAX_PAGES_REPORTED]
        out.append({
            "item": f"{item_letter[0]}{item_letter[1] or ''}",
            "question_text": row["question_text"],
            "target_field": row["yes_field"],
            "matched_terms": terms,
            "pages": pages,
            "mentions": len(hits),
        })

    out.sort(key=lambda p: (-p["mentions"], p["item"]))
    return out
