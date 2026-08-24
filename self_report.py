#!/usr/bin/env python3
"""
self_report.py — the conditions that are not in the records.

The extractor reads what a clinician wrote down. That is a hard ceiling,
and it sits exactly where the problem is: the conditions service members
most often go uncompensated for are the ones never documented. The back
you toughed out. The ringing you stopped noticing. The sleep you stopped
expecting. The mental health you avoided because of a clearance. None of
that is in an MHS Genesis export, and no amount of better parsing will
find it.

So this module asks. It is the one place in the tool where the input is
the member rather than the record, and it is deliberately a checklist
rather than a blank box -- "list your conditions" is the same blank-page
problem the whole tool exists to remove, and a list of plain-language
prompts is what actually jogs memory.

Two rules this module keeps:

  It does not diagnose and it does not advise. Every entry is phrased as
  a symptom in the member's own words, not a condition name, because the
  member is reporting an experience and the diagnosis is somebody else's
  job.

  Checking an item here does NOT check a box on a form. Each selection
  becomes a proposal carrying the exact wording printed on the form, and
  the member confirms that wording in review like any other. "Ringing in
  the ears" and "a hearing loss or wear a hearing aid" are not the same
  statement, and the one they sign is the second one.

DD Form 2807-1 is a self-report -- it asks the member, not the record --
so a truthful yes with no documentation behind it is a correct answer to
it. What matters is that the VSO can see which answers have paper behind
them and which do not, which is why these carry their own tier all the
way through to the worksheet.
"""

import re

# (id, what a member would call it, representative ICD-10 or None, hint)
#
# The ICD-10 code is not shown to anyone. It exists so these route through
# condition_library.match() and pick up the real form wording, instead of
# this module keeping its own second copy of the crosswalk.
#
# None means the library has no form question for it. That is not a gap to
# paper over: it goes on the worksheet for the VSO either way, and forcing
# it onto an approximate question would put a statement in the member's
# mouth that they did not make.
CATALOG = [
    ("Hearing and ears", [
        ("tinnitus", "Ringing, buzzing or hissing in my ears", "H93.19",
         "Very common after flight lines, ranges, engines and armour."),
        ("hearing", "I have trouble hearing, or ask people to repeat themselves",
         "H91.93", None),
        ("dizzy", "Dizziness, vertigo or fainting spells", "R42", None),
    ]),
    ("Sleep", [
        ("insomnia", "I have trouble falling or staying asleep", "G47.00", None),
        ("apnea", "I snore heavily, gasp, or have been told I stop breathing",
         "G47.33", "Often first noticed by a partner or a roommate."),
    ]),
    ("Bones, joints and muscles", [
        ("back", "Back pain that keeps coming back", "M54.50", None),
        ("neck", "Neck pain that keeps coming back", "M54.2", None),
        ("knee", "Knee pain, giving way, or swelling", "M25.561", None),
        ("shoulder", "Shoulder, elbow or wrist pain", "M25.511", None),
        ("foot", "Foot or ankle pain", "M25.571", None),
        ("joints", "Aching in several joints at once", "M25.50", None),
        ("numb", "Numbness or tingling in my hands or feet", "R20.2", None),
    ]),
    ("Head", [
        ("headache", "Frequent or severe headaches", "G44.209", None),
        ("headinjury", "A head injury, concussion, or blast exposure",
         "S06.0X0A", "Includes blasts and hard landings with no ER visit."),
        ("memory", "Trouble with memory or concentration", "R41.840", None),
    ]),
    ("Mood, stress and sleep of the mind", [
        ("anxiety", "Anxiety, feeling on edge, or panic", "F41.9", None),
        ("depression", "Low mood, or losing interest in things I used to enjoy",
         "F32.9", None),
        ("ptsd", "Nightmares, flashbacks, or avoiding reminders of something "
         "that happened", "F43.10", None),
        # No form question is a close enough match, and 17f ("depression or
        # excessive worry") is not what this person said. It goes to the VSO
        # on the worksheet rather than being bent onto an adjacent item.
        ("irritable", "Irritability, anger, or a shorter fuse than I used to have",
         None, None),
    ]),
    ("Breathing", [
        ("cough", "A cough that will not go away", "R05.9", None),
        ("breath", "Getting short of breath doing things I used to manage",
         "R06.02", None),
        ("sinus", "Constant sinus trouble or congestion", "J32.9", None),
        ("wheeze", "Wheezing, or breathing trouble with exertion or cold air",
         "J45.909", None),
    ]),
    ("Stomach and digestion", [
        ("reflux", "Heartburn or acid reflux", "K21.9", None),
        ("gut", "Stomach or bowel trouble that keeps coming back", "K58.9", None),
    ]),
    ("Skin, eyes and teeth", [
        ("skin", "Rashes or skin problems", "L30.9", None),
        ("scars", "Scars from an injury or surgery", "L90.5", None),
        ("vision", "Changes in my vision", "H53.9", None),
        ("teeth", "Tooth or gum trouble", "K08.9", None),
    ]),
    ("Other", [
        ("bp", "High blood pressure", "I10", None),
        ("urinary", "Frequent or painful urination", "R35.0", None),
        ("fatigue", "Tiredness that rest does not fix", None, None),
        ("sexual", "Sexual problems or erectile dysfunction", None,
         "Rarely reported and commonly connected to something already "
         "on your list. Worth raising even though it is awkward."),
    ]),
]

SOURCE_LABEL = "(self-reported)"
FREE_TEXT_ID = "other"


def catalog():
    """The checklist, as the UI needs it -- no codes."""
    return [{"group": group,
             "items": [{"id": i, "label": label, "hint": hint}
                       for (i, label, _code, hint) in items]}
            for group, items in CATALOG]


def _by_id():
    return {i: (label, code, hint)
            for _g, items in CATALOG for (i, label, code, hint) in items}


def to_conditions(selected_ids, free_text=None):
    """Selections -> condition records shaped like extracted ones.

    They carry self_reported=True and no page citation, because there is
    no page. Everything downstream keys off that rather than guessing from
    a missing source_page.
    """
    lookup = _by_id()
    out = []
    for sid in selected_ids or []:
        if sid not in lookup:
            continue
        label, code, _hint = lookup[sid]
        out.append(_record(label, code))

    for line in _split_free_text(free_text):
        out.append(_record(line, None))
    return out


def _split_free_text(free_text):
    """One condition per line. Members write lists, not paragraphs."""
    if not free_text:
        return []
    seen, out = set(), []
    for raw in str(free_text).replace(";", "\n").split("\n"):
        line = " ".join(raw.split()).strip(" .,-•*")
        if len(line) < 3 or line.lower() in seen:
            continue
        seen.add(line.lower())
        out.append(line[:120])
    return out[:25]


def _record(label, code):
    return {
        "condition": label,
        "icd10": code or "",
        "body_system": "Self-reported",
        "first_seen": None,
        "last_seen": None,
        "encounters": 0,
        "active": True,
        "on_problem_list": False,
        "providers": [],
        "administrative": False,
        "source_document": SOURCE_LABEL,
        "source_page": None,
        "self_reported": True,
    }


# Questions that ask whether something WAS DONE TO YOU -- treated,
# evaluated, counselled, operated on, hospitalised -- rather than what you
# experience.
#
# This exists because of a specific near-miss. A member checking "nightmares,
# flashbacks, avoiding reminders" routes through F43.10, and the library maps
# that code to "Received counseling of any type" and "Been evaluated or
# treated for a mental condition". For a code lifted out of a medical record
# that mapping is sound -- the code is there because a clinician put it
# there, so somebody did evaluate them. For a symptom the member typed, it is
# false, and it is false in the worst direction: the whole reason these
# conditions go unclaimed is that people never sought help for them. Checking
# those boxes would have the tool assert, on a form carrying a five-year
# false-statement penalty, the one thing that did not happen.
#
# A self-report can answer "do you have X". It cannot answer "did someone
# treat you for X". Only the member knows that, and the questionnaire does
# not ask.
TREATMENT_HISTORY = re.compile(
    r"received counseling|been evaluated or treated|been treated|"
    r"have you consulted|hospitaliz|been admitted|"
    r"operations or surgery|any .*surgery|surgery to correct|"
    r"been prescribed|attempted suicide|been rejected|been discharged|"
    r"applied for pension|denied life insurance",
    re.I)


def answerable_from_self_report(question_text):
    """Can a member truthfully answer this from a symptom alone?"""
    return not TREATMENT_HISTORY.search(question_text or "")


def is_self_reported(condition):
    return bool(condition.get("self_reported")) or \
        condition.get("source_document") == SOURCE_LABEL


def summarise(conditions):
    """What the records turned up, so the member can see the gap they are
    being asked to fill. A checklist with no context is a quiz; a checklist
    after 'your records show 21 conditions' is a prompt."""
    clinical = [c for c in conditions.get("clinical", [])
                if not is_self_reported(c)]
    systems = sorted({c.get("body_system") for c in clinical if c.get("body_system")})
    return {"count": len(clinical), "systems": systems}
