#!/usr/bin/env python3
"""
condition_library.py — ICD-10 ranges mapped to the questions on DD 2807-1
and SHA Part A.

WHY THIS EXISTS
---------------
field_map.py held about ten exact-code rules, hand-written against one
person's records. That works for that person and nobody else: a veteran
whose back pain is coded M54.5 instead of M54.9, or whose knee pain is
M25.562 instead of M25.561, got nothing at all.

ICD-10 is hierarchical, so the fix is to match on code *ranges* rather than
exact codes. M54.x is dorsalgia regardless of the subclass; F32.x is
depression whether it is F32.0 or F32.9. A few hundred range rules therefore
cover many thousands of individual codes, and a veteran with a condition
nobody anticipated still gets a proposal.

WHAT THIS IS NOT
----------------
Not an enumeration of every ICD-10 code, and not a copy of the VA rating
schedule. It maps codes to *the questions on these two forms* — which is a
much smaller and more tractable problem, and the only one this tool needs to
solve. Whether a condition is service-connected or how it rates under 38 CFR
Part 4 is a VSO's and a rating specialist's judgement, not this file's.

CONFIDENCE
----------
Each rule carries a confidence, which drives whether the review screen
pre-checks the box:
  high   — the code range and the question mean the same thing
           (J45 asthma -> "Asthma or any breathing problems")
  medium — reasonable inference, but the member should think about it
           (H52 refractive error -> "Worn contact lenses or glasses")
Nothing here is ever written to a form without confirmation.
"""

import re

# --------------------------------------------------------------- matching

def _norm(code):
    return (code or "").upper().replace(" ", "")


def _category(code):
    """The 3-character ICD-10 category: 'M54.51' -> 'M54'."""
    c = _norm(code)
    return c.split(".")[0][:3]


def _in_range(code, start, end):
    """Category-level range test, e.g. in_range('K25.1','K25','K31')."""
    cat = _category(code)
    if not cat or len(cat) < 3:
        return False
    letter, num = cat[0], cat[1:]
    if not (letter == start[0] == end[0]):
        return False
    try:
        return int(start[1:]) <= int(num) <= int(end[1:])
    except ValueError:
        return False


# ICD-10-CM is revised every 1 October: codes are added, deleted and
# reassigned. A deleted code does not raise here, it simply stops matching,
# and the condition it used to catch quietly disappears from every package
# built afterwards. Bump this when the rules below have been re-checked
# against the current release.
REVIEWED = "2026-08"


def _prefix(code, *prefixes):
    c = _norm(code)
    return any(c.startswith(p.upper()) for p in prefixes)


# ------------------------------------------------------------------ rules
# (dd2807 item, letter) | sha field key | label | confidence | predicate
#
# sha keys are the short slugs resolved against field_names_sha.json at load
# time, so a change to the form surfaces as a startup error rather than a
# silently unmapped question.

RULES = [
    # ---- 10: respiratory -------------------------------------------------
    ((10, "a"), None, "Tuberculosis", "high",
     lambda c: _in_range(c, "A15", "A19") or _prefix(c, "B90")),
    ((10, "c"), None, "Coughed up blood", "high", lambda c: _prefix(c, "R04.2")),
    ((10, "d"), "asthma", "Asthma or breathing problems", "high",
     lambda c: _prefix(c, "J45", "J46")),
    ((10, "e"), None, "Shortness of breath", "medium", lambda c: _prefix(c, "R06.0")),
    ((10, "f"), "bronchitis", "Bronchitis", "high",
     lambda c: _prefix(c, "J20", "J21", "J40", "J41", "J42")),
    ((10, "g"), None, "Wheezing", "high", lambda c: _prefix(c, "R06.2")),
    ((10, "h"), None, "Prescribed or used an inhaler", "medium",
     lambda c: _prefix(c, "J45", "J44")),
    # R05 is "cough" -- the question asks about a *chronic* cough. One acute
    # encounter does not establish that, so this is the weak tier: surfaced
    # for the member to consider, never pre-checked.
    ((10, "i"), "chroniccough", "Chronic cough or cough at night", "low",
     lambda c: _prefix(c, "R05")),
    ((10, "j"), "sinusitis", "Sinusitis", "high",
     lambda c: _prefix(c, "J01", "J32")),
    ((10, "k"), None, "Hay fever", "high",
     lambda c: _prefix(c, "J30")),   # all of J30 is allergic rhinitis
    ((10, "l"), None, "Chronic or frequent colds", "high",
     lambda c: _prefix(c, "J00", "J06", "J31.0")),

    # ---- 11: head, eyes, ears, nose, throat ------------------------------
    ((11, "a"), None, "Severe tooth or gum trouble", "high",
     lambda c: _in_range(c, "K00", "K14")),
    ((11, "b"), "thyroid", "Thyroid trouble or goiter", "high",
     lambda c: _in_range(c, "E00", "E07")),
    ((11, "c"), "eyedisorder", "Eye disorder or trouble", "high",
     lambda c: _in_range(c, "H00", "H59")),
    ((11, "d"), "earnosethroat", "Ear, nose, or throat trouble", "high",
     lambda c: _in_range(c, "H60", "H75") or _in_range(c, "J31", "J39")
     or _prefix(c, "H92", "H93.8", "H93.9", "R07.0", "R49", "J02", "J03",
                "J35", "R09.81")),
    ((11, "e"), None, "Loss of vision in either eye", "high",
     lambda c: _prefix(c, "H54")),
    ((11, "f"), None, "Worn contact lenses or glasses", "medium",
     lambda c: _prefix(c, "H52")),
    ((11, "g"), "hearingaid", "Hearing loss or wear a hearing aid", "high",
     lambda c: _prefix(c, "H90", "H91", "H93.1")),
    ((11, "h"), None, "Surgery to correct vision", "high",
     lambda c: _prefix(c, "Z98.4")),

    # ---- 12: musculoskeletal --------------------------------------------
    ((12, "a"), "shoulderarm", "Painful shoulder, elbow or wrist", "high",
     lambda c: _prefix(c, "M25.51", "M25.52", "M25.53", "M75", "M77",
                       "M65.3", "M19.01", "M19.02")),
    ((12, "b"), None, "Arthritis, rheumatism, or bursitis", "high",
     lambda c: _in_range(c, "M05", "M19") or _prefix(c, "M70", "M71")),
    ((12, "c"), "backandchest", "Recurrent back pain or any back problem", "high",
     lambda c: _prefix(c, "M54", "M51", "M43", "M47", "M48", "M53",
                       "M62.830")),
    ((12, "d"), None, "Numbness or tingling", "high",
     lambda c: _prefix(c, "G56", "G57", "G58")),
    ((12, "d"), None, "Numbness or tingling", "medium", lambda c: _prefix(c, "R20")),
    ((12, "e"), None, "Loss of finger or toe", "high", lambda c: _prefix(c, "Z89")),
    ((12, "f"), "anklefoottoes", "Foot trouble", "high",
     lambda c: _prefix(c, "M20", "M21.6", "M72.2", "M77.4", "M77.5",
                       "M25.57", "M79.67")),
    ((12, "g"), None, "Impaired use of arms, legs, hands, or feet", "medium",
     lambda c: _prefix(c, "R26", "M62.4", "M62.5", "Z74.0")),
    ((12, "h"), None, "Swollen or painful joint(s)", "high",
     lambda c: _prefix(c, "M25.4", "M25.5")),
    ((12, "i"), "legknee", "Knee trouble", "high",
     lambda c: _prefix(c, "M22", "M23", "M25.56", "M17", "M70.5")),
    ((12, "j"), None, "Knee or foot surgery", "medium",
     lambda c: _prefix(c, "Z98.89") ),
    ((12, "k"), None, "Need corrective devices (brace, support, orthotics)",
     "medium", lambda c: _prefix(c, "Z97.1", "Z46.89", "Z99.3")),
    ((12, "l"), None, "Bone, joint, or other deformity", "high",
     lambda c: _in_range(c, "M40", "M43") or _prefix(c, "M20", "M21", "M95")),
    ((12, "m"), None, "Plate(s), screw(s), rod(s) or pin(s) in any bone",
     "high", lambda c: _prefix(c, "Z96.6", "Z47.2")),
    ((12, "n"), None, "Broken bone(s)", "high",
     lambda c: _prefix(c, "S02", "S12", "S22", "S32", "S42", "S52", "S62",
                       "S72", "S82", "S92", "M84.3", "M84.4")),

    # ---- 13: digestive, urinary, skin, endocrine -------------------------
    ((13, "a"), "indigestion", "Frequent indigestion or heartburn", "high",
     lambda c: _prefix(c, "K21", "K30", "R12")),
    ((13, "b"), "stomachintestinal", "Stomach, liver, intestinal trouble, or ulcer",
     "high", lambda c: _in_range(c, "K25", "K31") or _in_range(c, "K50", "K59")
     or _prefix(c, "K92")),
    # A single diarrhea code is a symptom, not "intestinal trouble". Weak
    # tier for the same reason as R05 above.
    ((13, "b"), "stomachintestinal", "Stomach, liver, intestinal trouble, or ulcer",
     "low", lambda c: _prefix(c, "R19.7")),
    ((13, "c"), "gallbladder", "Gall bladder trouble or gallstones", "high",
     lambda c: _in_range(c, "K80", "K82")),
    ((13, "d"), "liver", "Jaundice or hepatitis", "high",
     lambda c: _in_range(c, "B15", "B19") or _in_range(c, "K70", "K77")
     or _prefix(c, "R17")),
    ((13, "e"), "hernia", "Rupture/hernia", "high",
     lambda c: _in_range(c, "K40", "K46")),
    ((13, "f"), "rectal", "Rectal disease, hemorrhoids, or blood from rectum",
     "high", lambda c: _prefix(c, "K64", "K62", "K60")),
    ((13, "g"), "skindisease", "Skin diseases", "high",
     lambda c: _in_range(c, "L00", "L99")),
    ((13, "h"), "urination", "Frequent or painful urination", "high",
     lambda c: _prefix(c, "R30", "R35", "N39.0", "N30")),
    ((13, "i"), "bloodsugar", "High or low blood sugar", "high",
     lambda c: _in_range(c, "E08", "E13") or _prefix(c, "E16", "R73")),
    ((13, "j"), "kidney", "Kidney stone or blood in urine", "high",
     lambda c: _in_range(c, "N20", "N23") or _prefix(c, "R31")),
    ((13, "k"), "sugarprotein", "Sugar or protein in urine", "high",
     lambda c: _prefix(c, "R80", "R81")),
    ((13, "l"), None, "Sexually transmitted disease", "high",
     lambda c: _in_range(c, "A50", "A64")),

    # ---- 14: general -----------------------------------------------------
    ((14, "a"), "allergies", "Adverse reaction to serum, food, insect stings, or medicine",
     "high", lambda c: _prefix(c, "T78", "T80.5", "T88.6", "Z88", "Z91.0")),
    ((14, "b"), "weightchange", "Recent unexplained gain or loss of weight", "medium",
     lambda c: _prefix(c, "R63.4", "R63.5", "E66")),
    ((14, "d"), "cancer", "Tumor, growth, cyst, or cancer", "high",
     lambda c: _in_range(c, "C00", "C97") or _in_range(c, "D00", "D49")),

    # SHA-only: DD 2807-1 has no cholesterol question, SHA does.
    ((None, None), "cholesterol", "High or bad cholesterol", "high",
     lambda c: _prefix(c, "E78")),
    ((None, None), "tobacco", "Currently use tobacco products", "high",
     lambda c: _prefix(c, "F17", "Z72.0")),
    ((None, None), "sleepapnea", "Other lung problems", "medium",
     lambda c: _prefix(c, "G47.3")),

    # ---- 15: neurological ------------------------------------------------
    ((15, "a"), "dizziness", "Dizziness or fainting spells", "high",
     lambda c: _prefix(c, "R42", "R55", "H81")),
    ((15, "b"), "headaches", "Frequent or severe headache", "high",
     lambda c: _prefix(c, "G43", "G44", "R51")),
    ((15, "c"), "headinjury", "A head injury, memory loss or amnesia", "high",
     lambda c: _prefix(c, "S06", "R41.3", "F04")),
    ((15, "d"), "paralysis", "Paralysis", "high",
     lambda c: _in_range(c, "G81", "G83")),
    ((15, "e"), "neurological", "Seizures, convulsions, epilepsy", "high",
     lambda c: _prefix(c, "G40", "R56")),
    ((15, "g"), None, "A period of unconsciousness or concussion", "high",
     lambda c: _prefix(c, "S06.0", "R40")),
    ((15, "h"), "meningitis", "Meningitis, encephalitis, or other neurological problems",
     "high", lambda c: _in_range(c, "G00", "G09") or _in_range(c, "G90", "G99")),

    # ---- 16: cardiovascular / blood -------------------------------------
    ((16, "a"), "rheumaticfever", "Rheumatic fever", "high",
     lambda c: _in_range(c, "I00", "I02")),
    ((16, "b"), "prolongedbleeding", "Prolonged bleeding", "high",
     lambda c: _in_range(c, "D65", "D69")),
    ((16, "c"), "chestpain", "Pain or pressure in the chest", "high",
     # R07.0 is "pain in throat" -- explicitly excluded. It was matching
     # here and proposing a chest-pain answer for a sore throat.
     lambda c: _prefix(c, "R07") and not _prefix(c, "R07.0")),
    ((16, "d"), "palpitations", "Palpitation, pounding heart or abnormal heartbeat",
     "high", lambda c: _prefix(c, "R00.2", "I49", "I47", "I48")),
    ((16, "e"), "heartmurmur", "Heart trouble or murmur", "high",
     lambda c: _in_range(c, "I05", "I09") or _prefix(c, "R01", "I34", "I35")),
    ((16, "f"), "highbloodpressure", "High or low blood pressure", "high",
     lambda c: _in_range(c, "I10", "I16") or _prefix(c, "I95")),

    # ---- 17: mental health ----------------------------------------------
    ((17, "a"), "mentalhealth", "Nervous trouble of any sort (anxiety or panic)",
     "high", lambda c: _prefix(c, "F40", "F41", "F43.22", "F43.23")),
    ((17, "b"), None, "Habitual stammering or stuttering", "high",
     lambda c: _prefix(c, "F80.81")),
    ((17, "c"), None, "Loss of memory or amnesia, or neurological symptoms",
     "high", lambda c: _prefix(c, "R41", "F04", "F90")),
    ((17, "d"), None, "Frequent trouble sleeping", "high",
     lambda c: _prefix(c, "G47", "F51")),
    ((17, "e"), None, "Received counseling of any type", "medium",
     lambda c: _in_range(c, "F30", "F48") or _prefix(c, "Z71.4", "Z71.9")),
    ((17, "f"), "mentalhealth", "Depression or excessive worry", "high",
     lambda c: _prefix(c, "F32", "F33", "F34.1", "F43.21")),
    ((17, "g"), "mentalhealth", "Been evaluated or treated for a mental condition",
     "high", lambda c: _in_range(c, "F01", "F99")),
    ((17, "h"), None, "Attempted suicide", "high",
     lambda c: _prefix(c, "T14.91", "Z91.5")),
    ((17, "i"), None, "Used illegal drugs or abused prescription drugs", "high",
     # F17 is nicotine, which is neither. It was matching here and
     # proposing an illegal-drug answer for a smoking diagnosis.
     lambda c: _in_range(c, "F11", "F19") and not _prefix(c, "F17")),

    # ---- 18: female-specific (gated by birth sex at proposal time) -------
    ((18, "a"), None, "Treatment for a gynecological disorder", "high",
     lambda c: _in_range(c, "N70", "N98")),
    ((18, "b"), None, "A change of menstrual pattern", "high",
     lambda c: _prefix(c, "N91", "N92", "N93")),
    ((18, "c"), None, "Any abnormal PAP smears", "high",
     lambda c: _prefix(c, "R87.6")),
]

# Items 18a-c apply only to members who indicated female birth sex. Proposing
# them otherwise is both wrong and a bad experience.
FEMALE_ONLY_ITEMS = {(18, "a"), (18, "b"), (18, "c")}

# SHA slug -> a fragment that must appear in the real field name. Resolved
# against field_names_sha.json so a form change fails loudly.
SHA_SLUGS = {
    "asthma": "Asthma", "bronchitis": "Bronchitis",
    "chroniccough": "Chroniccough", "sinusitis": "Sinusitis",
    "thyroid": "Thyroidtrouble", "eyedisorder": "Eyedisorderortrouble",
    "earnosethroat": "Earnoseorthroattrouble", "hearingaid": "wornahearingaid",
    "shoulderarm": "ShoulderArm", "backandchest": "BackandChest",
    "anklefoottoes": "AnkleFootToes", "legknee": "LegKnee",
    "indigestion": "Frequentindigestion", "stomachintestinal": "Stomachorintestinal",
    "gallbladder": "Gallbladder", "liver": "Liverproblems", "hernia": "Hernia",
    "rectal": "Rectaldisease", "skindisease": "Skindiseases",
    "urination": "Frequentorpainfulurination", "bloodsugar": "Highorlowbloodsugar",
    "kidney": "Kidneyproblems", "sugarprotein": "Sugarorproteininurine",
    "allergies": "Allergies", "weightchange": "Recentunexplainedgain",
    "cancer": "Cancerotherthanskin", "dizziness": "Periodsofdizziness",
    "headaches": "Recurringheadaches", "headinjury": "Aheadinjurymemoryloss",
    "paralysis": "Paralysis", "neurological": "Neurologicalproblems",
    "meningitis": "Meningitis", "rheumaticfever": "Rheumaticfever",
    "prolongedbleeding": "Prolongedbleeding", "chestpain": "Painpressureordiscomfort",
    "palpitations": "Palpitations", "heartmurmur": "Heartmurmur",
    "highbloodpressure": "Highbloodpressure", "mentalhealth": "Mentalhealthproblems",
    "cholesterol": "Highorbadcholesterol",
    "tobacco": "Doyoucurrentlyusetobaccoproducts",
    "sleepapnea": "Otherlungproblems",
}


def resolve_sha_fields(sha_field_names):
    """slug -> real SHA field name. Unresolved slugs are returned too, so a
    caller can report them rather than silently dropping the mapping."""
    resolved, missing = {}, []
    for slug, fragment in SHA_SLUGS.items():
        hits = [n for n in sha_field_names
                if fragment.lower() in n.lower()
                and n.endswith("_Question_YesNo_Response")]
        if len(hits) == 1:
            resolved[slug] = hits[0]
        else:
            missing.append((slug, len(hits)))
    return resolved, missing


def match(code, birth_sex=None):
    """Every form question an ICD-10 code maps to.

    Returns [(item, letter, sha_slug, label, confidence)].
    """
    out = []
    for (item_letter, sha_slug, label, confidence, pred) in RULES:
        if item_letter in FEMALE_ONLY_ITEMS and (birth_sex or "").lower() != "female":
            continue
        try:
            if pred(code):
                out.append((item_letter[0], item_letter[1], sha_slug,
                            label, confidence))  # item may be (None, None)
                                                 # for SHA-only questions
        except Exception:
            continue
    return out


def coverage_summary():
    """How many distinct questions the library can reach, for reporting."""
    dd = {(r[0][0], r[0][1]) for r in RULES}
    sha = {r[1] for r in RULES if r[1]}
    return {"rules": len(RULES), "dd2807_items": len(dd), "sha_questions": len(sha)}
