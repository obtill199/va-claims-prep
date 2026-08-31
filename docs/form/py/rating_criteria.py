#!/usr/bin/env python3
# Copyright (c) 2026 Oliver Tillinghast.
# Licensed under the PolyForm Noncommercial License 1.0.0.
# Free for veterans, VSOs, nonprofits and government. Commercial use
# requires a separate license -- see LICENSE, NOTICE.md, COMMERCIAL.md.
"""
rating_criteria.py — what the next rating level actually requires.

An increase claim is a different problem from an initial one. Service
connection is already settled; the question is whether the condition is
worse than the current rating reflects. That is decided by 38 CFR Part 4,
the Schedule for Rating Disabilities, and Part 4 does not ask whether it
hurts more. It asks for a specific measurement:

    the back        forward flexion, in degrees
    migraines       how often attacks are PROSTRATING
    sleep apnea     whether a breathing device is prescribed
    mental health   what the symptoms stop you doing, at work and at home

A veteran who does not know that says "my back is worse" and gets denied.
A veteran who does know brings a measurement. That gap is the entire
reason this module exists, and closing it needs no new parsing -- only
telling somebody what to go and get.

WHAT THIS DOES NOT DO

It does not decide that anybody qualifies for a higher rating. That is
VA's determination on a full record and an examination. Nothing here
reaches a form. Every entry is a summary of published criteria plus the
question to take to a VSO.

It also does not hide the risk in the other direction: filing for an
increase invites a fresh examination, and an examination that shows
improvement can REDUCE an existing rating. Veterans are rarely told this
before they file, and any honest tool has to say it first.

ACCURACY

These are plain-language summaries, not the regulation. The regulation is
the regulation, it is public, and every entry links to it. Part 4 also
gets revised -- the digestive system schedule changed substantially in
2024 -- so each entry carries the date it was last checked and the tool
tells the member to confirm rather than trusting a summary compiled at a
point in time.
"""

REVIEWED = "2026-08"
CFR_PART_4 = "https://www.ecfr.gov/current/title-38/chapter-I/part-4"

# Filing an increase invites a new examination. This is the sentence that
# has to appear before any of the rest of it.
REDUCTION_WARNING = (
    "Filing for an increase means VA will usually schedule a new "
    "examination. If that examination shows the condition has improved, VA "
    "can lower the rating you already have. That is uncommon for a "
    "long-standing, well-documented condition, and it is not a reason to "
    "avoid filing -- but you should know it before you file, and it is a "
    "question worth putting to your VSO first."
)

EFFECTIVE_DATE_NOTE = (
    "If your records show the condition got worse at some point in the year "
    "before you file, the increase can sometimes be backdated to that point "
    "rather than to your filing date. That is worth real money and it is "
    "routinely missed. Bring the dates."
)


def _pre(code, *prefixes):
    code = (code or "").upper().replace(".", "")
    return any(code.startswith(p.replace(".", "")) for p in prefixes)


# Each entry:
#   dc         VA diagnostic code(s) -- NOT the ICD-10 code
#   match      which extracted ICD-10 codes point at this
#   measures   the thing an examiner has to write down. The actionable part.
#   levels     [(percent, plain-language summary of the criterion)]
#   dbq        the Disability Benefits Questionnaire that captures it
#   note       anything that changes what the member should do
CRITERIA = [
    {
        "id": "tinnitus",
        "name": "Tinnitus (ringing in the ears)",
        "dc": "6260",
        "match": lambda c: _pre(c, "H93.1"),
        "measures": "Nothing. There is no higher level to measure toward.",
        "levels": [(10, "10 percent is the maximum, whether one ear or both.")],
        "dbq": "Hearing Loss and Tinnitus",
        "note": ("This one is capped. If you are already at 10 percent for "
                 "tinnitus there is no increase to claim, and time spent on "
                 "it is time not spent on something that can move. Worth "
                 "knowing before you file."),
    },
    {
        "id": "sleep-apnea",
        "name": "Sleep apnea",
        "dc": "6847",
        "match": lambda c: _pre(c, "G47.3"),
        "measures": ("Whether a breathing assistance device such as CPAP is "
                     "PRESCRIBED -- and that the prescription is in writing, "
                     "in your records."),
        "levels": [
            (0, "Documented sleep-disordered breathing, but no symptoms."),
            (30, "Persistent daytime sleepiness."),
            (50, "Requires use of a breathing assistance device such as CPAP."),
            (100, "Chronic respiratory failure with carbon dioxide retention, "
                  "or cor pulmonale, or requires a tracheostomy."),
        ],
        "dbq": "Sleep Apnea",
        "note": ("The jump from 30 to 50 turns on a prescribed device, not on "
                 "how tired you feel. If you use a CPAP and are rated below "
                 "50, make sure the prescription itself is in the file."),
    },
    {
        "id": "migraine",
        "name": "Migraine headaches",
        "dc": "8100",
        "match": lambda c: _pre(c, "G43", "G44"),
        "measures": ("How often you get PROSTRATING attacks -- ones that stop "
                     "you and send you to a dark room. Frequency over recent "
                     "months, not severity in the abstract."),
        "levels": [
            (0, "Less frequent attacks than the 10 percent level."),
            (10, "Prostrating attacks averaging one every two months."),
            (30, "Prostrating attacks averaging about one a month."),
            (50, "Very frequent, completely prostrating and prolonged attacks "
                 "that make it hard to hold down work."),
        ],
        "dbq": "Headaches (including Migraine Headaches)",
        "note": ("\"Prostrating\" is the word that decides this. Keep a "
                 "headache diary with dates and what each attack stopped you "
                 "doing -- that record is often worth more than the exam."),
    },
    {
        "id": "thoracolumbar",
        "name": "Lower back (thoracolumbar spine)",
        "dc": "5235–5243",
        "match": lambda c: _pre(c, "M54.5", "M54.4", "M51", "M43.1", "M48.06"),
        "measures": "Forward flexion of the lower back, in degrees.",
        "levels": [
            (10, "Forward flexion greater than 60 but not greater than 85 degrees."),
            (20, "Forward flexion greater than 30 but not greater than 60 degrees."),
            (40, "Forward flexion 30 degrees or less."),
            (50, "The entire lower back is fixed in an unfavorable position."),
        ],
        "dbq": "Back (Thoracolumbar Spine) Conditions",
        "note": ("Measured in degrees by an examiner with a goniometer. If "
                 "your records have no measurement, that is the single thing "
                 "to go and get. Ask that it be measured after repeated use, "
                 "and on a bad day rather than a good one."),
    },
    {
        "id": "cervical",
        "name": "Neck (cervical spine)",
        "dc": "5235–5243",
        "match": lambda c: _pre(c, "M54.2", "M50", "M43.02"),
        "measures": "Forward flexion of the neck, in degrees.",
        "levels": [
            (10, "Forward flexion greater than 30 but not greater than 40 degrees."),
            (20, "Forward flexion greater than 15 but not greater than 30 degrees."),
            (30, "Forward flexion 15 degrees or less."),
            (40, "The entire neck is fixed in an unfavorable position."),
        ],
        "dbq": "Neck (Cervical Spine) Conditions",
        "note": "Same measurement problem as the lower back, different numbers.",
    },
    {
        "id": "mental",
        "name": "Mental health conditions (PTSD, depression, anxiety)",
        "dc": "9201–9440",
        "match": lambda c: _pre(c, "F43.1", "F41", "F32", "F33", "F31"),
        "measures": ("What the symptoms stop you doing -- at work and in your "
                     "relationships. Not a diagnosis, and not a symptom list."),
        "levels": [
            (10, "Mild symptoms, or symptoms controlled by medication."),
            (30, "Occasional dips in work efficiency, generally functioning well."),
            (50, "Reduced reliability and productivity."),
            (70, "Problems in most areas -- work, school, family, judgment, mood."),
            (100, "Total impairment at work and socially."),
        ],
        "dbq": "Mental Disorders",
        "note": ("All mental health conditions share one rating formula, and "
                 "you get one rating for all of them together -- not one per "
                 "diagnosis. It is rated on function, so what matters is a "
                 "concrete account of what you can no longer do. Statements "
                 "from a spouse, a supervisor or a friend carry real weight "
                 "here, more than on most conditions."),
    },
    {
        "id": "knee-flexion",
        "name": "Knee — limited bending",
        "dc": "5260",
        "match": lambda c: _pre(c, "M17", "M25.56", "M23"),
        "measures": "How far the knee bends, in degrees.",
        "levels": [
            (0, "Bends to 60 degrees or more."),
            (10, "Bends only to 45 degrees."),
            (20, "Bends only to 30 degrees."),
            (30, "Bends only to 15 degrees."),
        ],
        "dbq": "Knee and Lower Leg Conditions",
        "note": ("Bending and straightening are rated separately, and knee "
                 "instability is a third rating again. Ask your VSO whether "
                 "more than one applies to you -- people routinely claim only "
                 "the one they were asked about."),
    },
    {
        "id": "sciatic",
        "name": "Sciatic nerve — pain or numbness down the leg",
        "dc": "8520",
        "match": lambda c: _pre(c, "M54.1", "M54.3", "M54.4", "G57.0"),
        "measures": ("Whether the nerve problem is mild, moderate, "
                     "moderately severe or severe, and whether there is "
                     "muscle wasting."),
        # The regulation genuinely uses bare words here -- "mild",
        # "moderate", "moderately severe". Repeating them tells a member
        # nothing, so each is written as what an examiner is actually
        # looking at when they choose one.
        "levels": [
            (10, "Mild: mostly sensory. Numbness, tingling or pain, with "
                 "strength and reflexes largely intact."),
            (20, "Moderate: sensory symptoms plus some measurable weakness "
                 "or reduced reflexes."),
            (40, "Moderately severe: clear weakness in the leg or foot, "
                 "affecting how you walk."),
            (60, "Severe: marked weakness with visible muscle wasting in "
                 "the leg."),
            (80, "Complete paralysis: the foot dangles and cannot be "
                 "lifted, with no movement below the knee."),
        ],
        "dbq": "Peripheral Nerves Conditions",
        "note": ("This is rated separately from the back condition that "
                 "causes it, and on each leg separately. If you have "
                 "radiating pain or numbness and only the back is rated, "
                 "that is a question for your VSO."),
    },
    {
        "id": "rhinitis",
        "name": "Allergic rhinitis",
        "dc": "6522",
        "match": lambda c: _pre(c, "J30"),
        "measures": "Whether there are polyps, and how blocked the airway is.",
        "levels": [
            (10, "No polyps, but the airway is more than half blocked on both "
                 "sides, or completely blocked on one."),
            (30, "Polyps present."),
        ],
        "dbq": "Sinusitis, Rhinitis and Other Conditions of the Nose",
        "note": "Rated on what an examiner can see, so an examination is the whole case.",
    },
    {
        "id": "sinusitis",
        "name": "Chronic sinusitis",
        "dc": "6510–6514",
        "match": lambda c: _pre(c, "J32", "J01"),
        "measures": ("How many episodes a year, how long they last, and "
                     "whether they needed antibiotics."),
        "levels": [
            (10, "One or two episodes a year needing prolonged antibiotics, "
                 "or three to six milder episodes."),
            (30, "Three or more episodes a year needing prolonged antibiotics, "
                 "or more than six milder episodes."),
            (50, "Following surgery, with repeated infections after."),
        ],
        "dbq": "Sinusitis, Rhinitis and Other Conditions of the Nose",
        "note": ("Counted per year, so the evidence is your treatment history "
                 "rather than a single exam. Dates and antibiotic "
                 "prescriptions are the case."),
    },
]

# Conditions where an increase is decided by a test the member should simply
# go and get, and summarising the table would mislead more than it helps.
POINTERS = {
    "hearing": {
        "match": lambda c: _pre(c, "H90", "H91"),
        "name": "Hearing loss",
        "dc": "6100",
        "text": ("Rated from an audiogram, using a table that combines your "
                 "hearing thresholds with your speech discrimination score. "
                 "There is no shortcut and no summary worth trusting: the "
                 "action is to get a current VA audiology exam. Bring any "
                 "private audiogram you already have."),
        "dbq": "Hearing Loss and Tinnitus",
    },
}


def for_condition(icd10):
    """Every rating entry an extracted condition points at."""
    out = [c for c in CRITERIA if icd10 and c["match"](icd10)]
    out += [p for p in POINTERS.values() if icd10 and p["match"](icd10)]
    return out


def next_level(entry, current_percent):
    """The next step up from where they are, and what it asks for."""
    if "levels" not in entry:
        return None
    higher = [(pct, text) for pct, text in entry["levels"]
              if current_percent is None or pct > current_percent]
    return higher[0] if higher else None


def is_capped(entry, current_percent):
    if "levels" not in entry or current_percent is None:
        return False
    return current_percent >= max(pct for pct, _ in entry["levels"])
