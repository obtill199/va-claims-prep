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

    # ---------------------------------------------------------- musculoskeletal
    {
        "id": "knee-extension",
        "name": "Knee — cannot straighten fully",
        "dc": "5261",
        "match": lambda c: _pre(c, "M17", "M25.56", "M23"),
        "measures": "How far short of straight the knee stops, in degrees.",
        "levels": [
            (0, "Stops less than 5 degrees short of straight."),
            (10, "Stops 10 degrees short."),
            (20, "Stops 15 degrees short."),
            (30, "Stops 20 degrees short."),
            (40, "Stops 30 degrees short."),
            (50, "Stops 45 degrees short."),
        ],
        "dbq": "Knee and Lower Leg Conditions",
        "note": ("Rated separately from limited bending. One knee can carry "
                 "both ratings at once, and many people are only ever asked "
                 "about the bending."),
    },
    {
        "id": "knee-instability",
        "name": "Knee — giving way or instability",
        "dc": "5257",
        "match": lambda c: _pre(c, "M23.5", "M25.36", "S83.5", "M25.06"),
        "measures": "How much the knee moves sideways when an examiner tests it.",
        # The regulation says only "slight", "moderate" and "severe". Those
        # words tell a member nothing, so each is written as what an
        # examiner observes when choosing one.
        "levels": [
            (10, "Slight: the knee gives a little on testing, or gives way "
                 "occasionally."),
            (20, "Moderate: clear looseness on testing, giving way often "
                 "enough to affect how you move."),
            (30, "Severe: marked looseness, giving way regularly, often "
                 "needing a brace."),
        ],
        "dbq": "Knee and Lower Leg Conditions",
        "note": ("A third, separate rating from bending and straightening. If "
                 "your knee gives way and only motion is rated, ask about "
                 "this one specifically."),
    },
    {
        "id": "ankle",
        "name": "Ankle — limited movement",
        "dc": "5271",
        "match": lambda c: _pre(c, "M25.57", "M19.07", "S93.4", "M24.67"),
        "measures": "How far the ankle moves up and down, in degrees.",
        "levels": [
            (10, "Moderately limited."),
            (20, "Markedly limited."),
        ],
        "dbq": "Ankle Conditions",
        "note": "Each ankle is rated separately.",
    },
    {
        "id": "shoulder",
        "name": "Shoulder — limited movement",
        "dc": "5201",
        "match": lambda c: _pre(c, "M75", "M25.51", "M19.01", "S43.4"),
        "measures": "How high you can raise the arm, in degrees.",
        "levels": [
            (20, "Cannot raise the arm above shoulder level."),
            (30, "Cannot raise it more than halfway between the side and "
                 "shoulder level (dominant arm; 20 percent for the other)."),
            (40, "Cannot raise it more than 25 degrees from the side "
                 "(dominant arm; 30 percent for the other)."),
        ],
        "dbq": "Shoulder and Arm Conditions",
        "note": ("Which arm is your dominant one changes the percentage. Make "
                 "sure the examiner records it."),
    },
    {
        "id": "arthritis",
        "name": "Degenerative arthritis",
        "dc": "5003",
        "match": lambda c: _pre(c, "M15", "M16", "M18", "M19", "M47"),
        "measures": ("X-ray evidence of arthritis, plus how much movement is "
                     "lost in the affected joints."),
        "levels": [
            (10, "X-ray evidence in one or more major joints, with some "
                 "limitation of motion that is not itself compensable."),
            (20, "X-ray evidence in two or more major joint groups, with "
                 "occasional incapacitating episodes."),
        ],
        "dbq": "the DBQ for whichever joint is affected",
        "note": ("Used when a joint hurts and is stiff but does not yet meet "
                 "the limitation-of-motion criteria. If the joint has real "
                 "loss of motion, it is usually rated on that instead, and "
                 "the two are not stacked on the same joint."),
    },
    {
        "id": "flatfoot",
        "name": "Flat feet (pes planus)",
        "dc": "5276",
        "match": lambda c: _pre(c, "M21.4", "Q66.5"),
        "measures": ("Whether the deformity is correctable, whether shoes and "
                     "supports help, and whether there is swelling and "
                     "tenderness on use."),
        "levels": [
            (10, "Moderate: symptoms relieved by built-up shoes or supports."),
            (20, "Severe, one foot: marked deformity, pain on use, swelling."),
            (30, "Severe, both feet."),
            (30, "Pronounced, one foot: marked inward displacement, not "
                 "improved by shoes or supports."),
            (50, "Pronounced, both feet."),
        ],
        "dbq": "Foot Conditions",
        "note": ("One of the few where both feet together are rated higher "
                 "than one, rather than each side separately."),
    },
    {
        "id": "plantar-fasciitis",
        "name": "Plantar fasciitis",
        "dc": "5269",
        "match": lambda c: _pre(c, "M72.2"),
        "measures": ("Whether it is in one foot or both, and whether it "
                     "responds to treatment including orthotics."),
        "levels": [
            (10, "One foot, not responding to treatment."),
            (20, "Both feet, not responding to treatment."),
            (30, "Both feet, and no treatment has worked."),
        ],
        "dbq": "Foot Conditions",
        "note": ("This code was added in 2021. Claims decided before then may "
                 "have been rated by analogy under something else -- worth "
                 "asking your VSO whether a re-rating applies."),
    },
    {
        "id": "hip",
        "name": "Hip — limited movement",
        "dc": "5251–5253",
        "match": lambda c: _pre(c, "M16", "M25.55", "M19.05", "S73"),
        "measures": "How far the hip and thigh move, in degrees.",
        "levels": [
            (10, "Thigh cannot be raised much beyond 10 degrees, or rotation "
                 "is limited."),
            (20, "Thigh movement limited to 45 degrees from straight."),
            (30, "Thigh movement limited to 20 degrees."),
            (40, "Thigh movement limited to 10 degrees."),
        ],
        "dbq": "Hip and Thigh Conditions",
        "note": "Each hip separately.",
    },
    {
        "id": "wrist",
        "name": "Wrist — limited movement",
        "dc": "5215",
        "match": lambda c: _pre(c, "M25.53", "M19.03", "S63", "M18"),
        "measures": "How far the wrist bends back and forward, in degrees.",
        "levels": [
            (10, "Bending back limited to less than 15 degrees, or the wrist "
                 "cannot be bent to neutral."),
        ],
        "dbq": "Wrist Conditions",
        "note": ("10 percent is the ceiling for limited wrist motion on each "
                 "side. Higher ratings need fusion or nerve involvement, "
                 "which are rated elsewhere."),
    },

    # ---------------------------------------------------------------- neurology
    {
        "id": "upper-nerve",
        "name": "Arm and hand nerves — pain, numbness or weakness",
        "dc": "8510–8519",
        "match": lambda c: _pre(c, "G56", "M54.1", "G54.0", "G54.2"),
        "measures": ("Whether it is mostly sensory, and how much strength and "
                     "reflex are lost."),
        "levels": [
            (20, "Mild: mostly sensory, strength and reflexes largely intact "
                 "(dominant arm; 20 percent for the other at moderate)."),
            (40, "Moderate to moderately severe: measurable weakness."),
            (50, "Severe, with muscle wasting."),
            (70, "Complete paralysis."),
        ],
        "dbq": "Peripheral Nerves Conditions",
        "note": ("Rated separately from the neck or shoulder condition that "
                 "causes it, and on each arm separately. Which arm is dominant "
                 "changes the percentage."),
    },
    {
        "id": "tbi",
        "name": "Traumatic brain injury — lasting effects",
        "dc": "8045",
        "match": lambda c: _pre(c, "S06", "F07.81", "Z87.820"),
        "measures": None,
        "dbq": "Residuals of TBI",
        "pointer": True,
        "text": ("Rated differently from anything else in the schedule. An "
                 "examiner scores ten separate areas -- memory, judgment, "
                 "social interaction, orientation, motor activity, visual "
                 "spatial orientation, subjective symptoms, neurobehavioral "
                 "effects, communication and consciousness -- and the highest "
                 "single score sets the rating. Physical effects such as "
                 "headaches, dizziness or sleep problems are then rated "
                 "separately on top. There is no useful summary: what matters "
                 "is a current TBI examination and making sure every separate "
                 "effect is claimed rather than folded into one."),
    },

    # --------------------------------------------------------------- respiratory
    {
        "id": "asthma",
        "name": "Asthma",
        "dc": "6602",
        "match": lambda c: _pre(c, "J45"),
        "measures": ("Breathing-test numbers -- FEV-1 and the FEV-1/FVC ratio "
                     "-- and what medication you need to control it."),
        "levels": [
            (10, "FEV-1 71 to 80 percent of predicted, or an inhaler needed "
                 "intermittently."),
            (30, "FEV-1 56 to 70 percent, or daily inhaled medication."),
            (60, "FEV-1 40 to 55 percent, or at least monthly visits for "
                 "flare-ups, or courses of oral steroids three or more times "
                 "a year."),
            (100, "FEV-1 under 40 percent, or more than one attack a week "
                  "with breathing failure, or daily oral steroids."),
        ],
        "dbq": "Respiratory Conditions (other than TB and sleep apnea)",
        "note": ("A pulmonary function test is the case. Note that medication "
                 "alone can meet a level even when the numbers do not -- "
                 "people on daily inhalers are routinely rated too low "
                 "because nobody wrote the prescription pattern down."),
    },
    {
        "id": "copd",
        "name": "COPD, emphysema and chronic bronchitis",
        "dc": "6603–6604",
        "match": lambda c: _pre(c, "J41", "J42", "J43", "J44"),
        "measures": "FEV-1, the FEV-1/FVC ratio, and DLCO from a breathing test.",
        "levels": [
            (10, "FEV-1 71 to 80 percent of predicted."),
            (30, "FEV-1 56 to 70 percent."),
            (60, "FEV-1 40 to 55 percent."),
            (100, "FEV-1 under 40 percent, or needing outpatient oxygen."),
        ],
        "dbq": "Respiratory Conditions (other than TB and sleep apnea)",
        "note": "Get a current pulmonary function test before filing.",
    },

    # ------------------------------------------------------------ cardiovascular
    {
        "id": "hypertension",
        "name": "High blood pressure",
        "dc": "7101",
        "match": lambda c: _pre(c, "I10", "I11", "I12", "I13", "I15"),
        "measures": ("Diastolic and systolic readings, and whether you need "
                     "continuous medication to control them."),
        "levels": [
            (10, "Diastolic mostly 100 or more, or systolic mostly 160 or "
                 "more, or a history of diastolic mostly 100+ that now needs "
                 "continuous medication."),
            (20, "Diastolic mostly 110 or more."),
            (40, "Diastolic mostly 120 or more."),
            (60, "Diastolic mostly 130 or more."),
        ],
        "dbq": "Hypertension",
        "note": ("The 10 percent level can be met by history plus ongoing "
                 "medication even if readings are now controlled. That is the "
                 "one people miss, because the current numbers look fine."),
    },
    {
        "id": "heart",
        "name": "Heart disease",
        "dc": "7005–7007",
        "match": lambda c: _pre(c, "I20", "I21", "I22", "I24", "I25", "I50"),
        "measures": ("METs -- how much exertion brings on symptoms -- and the "
                     "heart's ejection fraction."),
        "levels": [
            (10, "Symptoms at 7 to 10 METs, or continuous medication needed."),
            (30, "Symptoms at 5 to 7 METs, or an enlarged heart on imaging."),
            (60, "Symptoms at 3 to 5 METs, or ejection fraction 30 to 50 "
                 "percent, or more than one episode of heart failure a year."),
            (100, "Symptoms at 3 METs or less, or ejection fraction under 30 "
                  "percent, or chronic heart failure."),
        ],
        "dbq": "Heart Conditions",
        "note": ("A METs figure is the whole case and is often absent from "
                 "ordinary records. Ask specifically for an exercise test or "
                 "an interview-based METs estimate."),
    },

    # ---------------------------------------------------------------- endocrine
    {
        "id": "diabetes",
        "name": "Diabetes",
        "dc": "7913",
        "match": lambda c: _pre(c, "E10", "E11", "E13"),
        "measures": ("What treatment it takes to control -- diet, oral "
                     "medication, insulin -- and whether your activity has to "
                     "be restricted."),
        "levels": [
            (10, "Managed by restricted diet alone."),
            (20, "Insulin and restricted diet, or an oral medication and "
                 "restricted diet."),
            (40, "Insulin, restricted diet, and regulation of activities."),
            (60, "The above plus episodes of ketoacidosis or hypoglycaemic "
                 "reactions needing one or two hospital visits a year."),
            (100, "More than one hospitalisation a year plus progressive "
                  "weight loss and strength loss."),
        ],
        "dbq": "Diabetes Mellitus",
        "note": ("\"Regulation of activities\" is a specific finding -- a "
                 "doctor has told you to avoid strenuous activity -- and it is "
                 "the step from 20 to 40 percent. It has to be written down. "
                 "Diabetes also causes conditions rated separately: nerve "
                 "damage in the feet, eye disease, kidney disease. Ask about "
                 "each."),
    },

    # -------------------------------------------------------------------- skin
    {
        "id": "skin",
        "name": "Eczema, dermatitis and similar skin conditions",
        "dc": "7806",
        "match": lambda c: _pre(c, "L20", "L21", "L23", "L24", "L25", "L27",
                                "L28", "L30", "L40", "L98.9"),
        "measures": ("What percentage of your body, and of exposed areas, is "
                     "affected -- and what medication controls it."),
        "levels": [
            (10, "Between 5 and 20 percent of the whole body or of exposed "
                 "areas, or intermittent systemic therapy in the last year."),
            (30, "Between 20 and 40 percent, or systemic therapy for six "
                 "weeks or more in the last year."),
            (60, "More than 40 percent, or constant systemic therapy."),
        ],
        "dbq": "Skin Diseases",
        "note": ("Rated on how it is at its worst, not on the day of the "
                 "examination. If it flares seasonally, say so and bring "
                 "photographs from a flare."),
    },
    {
        "id": "scars",
        "name": "Scars",
        "dc": "7800–7805",
        "match": lambda c: _pre(c, "L90.5", "L91.0", "T20", "T21", "T22",
                                "T23", "T24", "T25"),
        "measures": ("Where the scar is, its total area, and whether it is "
                     "painful or unstable."),
        "levels": [
            (10, "One or two scars that are painful, or unstable, or a deep "
                 "non-linear scar of at least 6 square inches."),
            (20, "Three or four painful or unstable scars, or 12 square "
                 "inches or more."),
            (30, "Five or more painful or unstable scars."),
        ],
        "dbq": "Scars / Disfigurement",
        "note": ("Painful scars are rated even when small. Scars on the head, "
                 "face or neck are rated under a separate, more generous code. "
                 "Surgical scars from a service-connected operation count."),
    },

    # --------------------------------------------------------------- digestive
    {
        "id": "ibs",
        "name": "Irritable bowel syndrome",
        "dc": "7319",
        "match": lambda c: _pre(c, "K58"),
        "measures": ("How often symptoms occur and whether abdominal pain is "
                     "present with them."),
        "levels": [
            (10, "Symptoms occurring at least six times a year."),
            (20, "Symptoms occurring more often, with abdominal pain."),
            (30, "Symptoms occurring daily, with abdominal pain."),
        ],
        "dbq": "Intestinal Conditions",
        "note": ("The digestive rating schedule was substantially rewritten in "
                 "2024 and these criteria replaced older ones. If your rating "
                 "predates that, ask your VSO whether the new criteria give "
                 "you a better result -- VA does not always reapply them "
                 "automatically."),
        "revised": "2024",
    },
    {
        "id": "gerd",
        "name": "Acid reflux (GERD)",
        "dc": "7206",
        "match": lambda c: _pre(c, "K21"),
        "measures": ("Which symptoms you get, how often, and whether they "
                     "persist despite treatment."),
        "levels": [
            (10, "Symptoms such as heartburn, regurgitation or difficulty "
                 "swallowing, controlled by treatment."),
            (30, "Persistent symptoms despite treatment."),
            (50, "Symptoms causing complications such as stricture or "
                 "bleeding."),
        ],
        "dbq": "Esophageal Conditions",
        "note": ("GERD moved to its own diagnostic code in the 2024 rewrite of "
                 "the digestive schedule -- it used to be rated by analogy to "
                 "hiatal hernia. These criteria are a plain-language summary "
                 "of the current rules and the wording matters, so read the "
                 "regulation itself before relying on a level."),
        "revised": "2024",
    },
    {
        "id": "hemorrhoids",
        "name": "Hemorrhoids",
        "dc": "7336",
        "match": lambda c: _pre(c, "K64"),
        "measures": "Size, whether they can be pushed back, and whether they bleed.",
        "levels": [
            (0, "Mild or moderate."),
            (10, "Large or thrombotic, irreducible, with frequent recurrence."),
            (20, "With persistent bleeding and anaemia, or with fissures."),
        ],
        "dbq": "Rectum and Anus Conditions",
        "revised": "2024",
        "note": "Also covered by the 2024 digestive rewrite.",
    },

    # ----------------------------------------------------------- genitourinary
    {
        "id": "ed",
        "name": "Erectile dysfunction",
        "dc": "7522",
        "match": lambda c: _pre(c, "N52", "F52.2"),
        "measures": "Whether there is physical deformity of the organ.",
        "levels": [
            (0, "No deformity: rated 0 percent."),
            (20, "With deformity."),
        ],
        "dbq": "Male Reproductive Organ Conditions",
        "note": ("Almost always rated 0 percent -- but that is not the point. "
                 "It normally qualifies for Special Monthly Compensation under "
                 "category K, which is a separate monthly payment on top of "
                 "your rating, and it is very commonly missed. Ask your VSO "
                 "about SMC-K specifically. It is also frequently secondary to "
                 "a mental health condition or its medication."),
    },

    # ---------------------------------------------------------------- hearing
    {
        "id": "vertigo",
        "name": "Dizziness and vertigo (Meniere\u2019s, labyrinthitis)",
        "dc": "6204",
        "match": lambda c: _pre(c, "H81", "R42"),
        "measures": "How often you get attacks, and whether you also stagger.",
        "levels": [
            (10, "Occasional dizziness."),
            (30, "Dizziness and occasional staggering."),
        ],
        "dbq": "Ear Conditions",
        "note": ("If it is Meniere's disease, there is a separate code that "
                 "can pay more where hearing loss and attacks are combined. "
                 "Ask which fits."),
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


# ---------------------------------------------------------------- fallback
#
# The criteria above cover the conditions veterans most often claim, but
# Part 4 runs to hundreds of diagnostic codes and no summary will ever hold
# all of them. Silence is the wrong answer for the rest: somebody with a
# condition that is not in the list above still needs to know which part of
# the schedule governs it, which questionnaire captures it, and that the
# criteria exist and are public.
#
# So every condition gets something. Specific criteria where we have them,
# and the right section, the right DBQ and the right question where we do
# not. Never nothing.
SYSTEMS = [
    ("Musculoskeletal", "§4.71a", "the DBQ for the affected joint",
     lambda c: _pre(c, "M0", "M1", "M2", "M4", "M5", "M6", "M7", "M8", "M9",
                    "S2", "S3", "S4", "S5", "S6", "S7", "S8", "S9"),
     "Most joint conditions are rated on lost range of motion, measured in "
     "degrees. If your records contain no measurement, that is what to go "
     "and get."),
    ("Mental health", "§4.130", "Mental Disorders",
     lambda c: _pre(c, "F"),
     "All mental health conditions share one rating formula and produce one "
     "combined rating, based on what the symptoms stop you doing rather than "
     "on the diagnosis."),
    ("Neurological", "§4.124a", "the DBQ for the affected nerve or condition",
     lambda c: _pre(c, "G"),
     "Nerve conditions are rated per nerve and per side, separately from "
     "whatever causes them."),
    ("Respiratory", "§4.97", "Respiratory Conditions",
     lambda c: _pre(c, "J"),
     "Usually rated on pulmonary function test numbers. Get a current test."),
    ("Cardiovascular", "§4.104", "Heart Conditions",
     lambda c: _pre(c, "I"),
     "Usually rated on METs -- the level of exertion that brings on symptoms."),
    ("Digestive", "§4.114", "the DBQ for the affected organ",
     lambda c: _pre(c, "K"),
     "This whole section was rewritten in 2024. If your rating predates that, "
     "ask whether the current criteria give a better result."),
    ("Genitourinary", "§4.115a", "the DBQ for the affected system",
     lambda c: _pre(c, "N"),
     "Often rated on frequency -- of voiding, of infections, of dialysis. "
     "Also ask about Special Monthly Compensation, which is separate from "
     "the rating and commonly missed."),
    ("Skin", "§4.118", "Skin Diseases",
     lambda c: _pre(c, "L"),
     "Rated on the percentage of body area affected and the treatment needed. "
     "Rated at its worst, not on the day of the exam."),
    ("Endocrine", "§4.119", "the DBQ for the affected condition",
     lambda c: _pre(c, "E"),
     "Usually rated on the treatment required and the complications it "
     "causes -- and the complications are often rated separately."),
    ("Eyes", "§4.79", "Eye Conditions",
     lambda c: _pre(c, "H0", "H1", "H2", "H3", "H4", "H5"),
     "Rated on measured visual acuity and field of vision."),
    ("Ears and hearing", "§4.85", "Hearing Loss and Tinnitus",
     lambda c: _pre(c, "H6", "H7", "H8", "H9"),
     "Hearing is rated from an audiogram against a combining table."),
    ("Blood and lymphatic", "§4.117", "Hematologic and Lymphatic Conditions",
     lambda c: _pre(c, "D5", "D6", "D7", "D8"),
     "Usually rated on blood counts and on the treatment required."),
    ("Infectious disease", "§4.88b", "Infectious Diseases",
     lambda c: _pre(c, "A", "B"),
     "Often rated on active disease plus any lasting damage, which is rated "
     "separately."),
    ("Gynecological", "§4.116", "Gynecological Conditions",
     lambda c: _pre(c, "N7", "N8", "N9"),
     "Usually rated on symptoms and on whether treatment controls them."),
    ("Cancer", "§4.type-specific", "the DBQ for the affected system",
     lambda c: _pre(c, "C", "D0", "D1", "D2", "D3", "D4"),
     "Active malignancy is normally rated 100 percent, then re-examined and "
     "re-rated on lasting effects once treatment ends. If you were rated "
     "during treatment and never re-examined, raise that."),
    ("Dental", "§4.150", "Dental and Oral Conditions",
     lambda c: _pre(c, "K0"),
     "Rated mainly on loss of bone or tooth loss caused by injury or disease, "
     "not on ordinary dental care."),
]


def system_for(icd10):
    """Which part of the schedule governs a condition we have no specific
    criteria for. Returns None only for codes outside the chapters above."""
    for name, section, dbq, match, guidance in SYSTEMS:
        try:
            if icd10 and match(icd10):
                return {"system": name, "section": section, "dbq": dbq,
                        "guidance": guidance}
        except Exception:
            continue
    return None
