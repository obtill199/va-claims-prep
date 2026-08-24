#!/usr/bin/env python3
"""
intake.py — the questionnaire: what the member tells us directly.

Everything here is self-reported by the member on the intake screen, which
is why it does NOT go through the confirm gate that record-derived
proposals do (BUILD_BRIEF.md decision 1). That rule exists because
record-derived answers are inferences from documents the member may never
have read (section 3.3); it doesn't apply to a value they typed themselves
one screen earlier.

SSN and DoD ID are deliberately never collected. See BLANK_BY_DESIGN below.

Field names were verified against the real blank forms this session via
inspect_fields.py.
"""

from datetime import date


def _presumptive_exposures():
    """Imported lazily so intake.py stays importable on its own."""
    import presumptives
    return presumptives.EXPOSURES

# ---------------------------------------------------------------- schema

# (key, label, type, options, help_text)
QUESTIONS = [
    ("full_name", "Full name (Last, First, Middle)", "text", None,
     "As it appears in your service record."),
    ("date_of_birth", "Date of birth", "date", None, None),
    ("birth_sex", "Birth sex", "choice", ["Male", "Female"],
     "SHA Part A asks for this; it gates which sections apply."),
    ("address", "Home address", "textarea", None,
     "Street, city, state, ZIP."),
    ("phone", "Phone number", "text", None, None),
    ("email", "Personal email", "text", None, None),
    ("branch", "Service branch", "choice",
     ["Army", "Navy", "Marine Corps", "Air Force", "Space Force",
      "Coast Guard", "USPHS", "NOAA"], None),
    ("component", "Component", "choice",
     ["Regular", "Reserve", "National Guard"], None),
    ("duty_status", "Current duty status", "choice",
     ["Active Component",
      "Active Duty  Active Guard Reserve",
      "Active Duty  Non-Active Guard Reserve",
      "Not on active duty"],
     "SHA Part A only."),
    ("purpose", "Purpose of this exam", "choice",
     ["Separation", "Retirement", "Medical Board", "Retention"], None),
    # Not written to either form. It is here because every deadline that
    # decides an effective date counts from this one date, and without it
    # the tool cannot tell a member with 120 days left from one with 80.
    # See timing.py.
    # The one question that unlocks presumptive service connection. Branch,
    # component and duty status say nothing about whether somebody breathed
    # a burn pit in Balad or spent thirty days at Camp Lejeune in 1985, and
    # a presumption is the single biggest shortcut in the system. Not
    # written to either form -- see presumptives.py.
    ("exposures", "Where did you serve?", "multi",
     [(e["id"], e["label"], e["hint"]) for e in _presumptive_exposures()],
     "Tick everything that applies. Some places and periods carry "
     "presumptions \u2014 conditions VA connects to your service without "
     "you having to prove the link. This is not written to either form."),
    ("separation_date", "Separation or retirement date", "date", None,
     "Your actual or expected date. If you are already out, the date you "
     "separated. Approximate is fine \u2014 it is used to work out which "
     "filing deadlines apply to you, and is not written to either form."),
    ("position", "Position (title, grade, component)", "text", None, None),
    ("occupation", "Usual occupation / day-to-day job", "text", None, None),
    ("exam_location", "Examining location and address", "textarea", None,
     "Leave blank if you don't know it yet."),
    ("medications", "Current medications", "textarea", None,
     "Prescription and over-the-counter. Write 'None' if none."),
    ("allergies", "Allergies", "textarea", None,
     "Insect bites/stings, foods, medicines. Write 'None' if none."),
]

REQUIRED = {"full_name", "branch", "component", "purpose"}

# Fields on both forms that this tool intentionally never fills. Listed
# explicitly (rather than just omitted) so the omission is a visible
# decision and the UI can tell the member exactly what to complete by hand.
BLANK_BY_DESIGN = {
    "DD2807-1": [
        "form1[0].Page1[0].Row1[0].TwoA[0]",        # SSN
        "form1[0].Page1[0].Row1[0].TwoB[0]",        # DoD ID
        "form1[0].Page2[0].Row1[0].SSN_pg2[0]",
        "form1[0].Page2[0].Row1[0].DODNumber_pg2[0]",
        "form1[0].Page3[0].Row1[0].SSN_pg3[0]",
        "form1[0].Page3[0].Row1[0].DODNumber_pg3[0]",
    ],
    "SHA_PART_A": [
        "TI_2_2SSNSOCIALSECURITYNUMBER",
        "TI_3_3DODIDNUMBER",
    ],
}

BLANK_BY_DESIGN_REASON = (
    "Social Security Number and DoD ID are intentionally left blank. This "
    "tool never collects, stores, or writes them. Fill them in by hand in a "
    "PDF reader before you hand the package to your VSO."
)

# ------------------------------------------------------- DD 2807-1 mapping

DD_TEXT_FIELDS = {
    "full_name": [
        "form1[0].Page1[0].Row1[0].One[0]",
        "form1[0].Page2[0].Row1[0].Name_pg2[0]",
        "form1[0].Page3[0].Row1[0].Name_pg3[0]",
    ],
    "address": ["form1[0].Page1[0].Four[0].fourA[0]"],
    "phone": ["form1[0].Page1[0].Four[0].fourB[0]"],
    "email": ["form1[0].Page1[0].Four[0].fourC[0]"],
    "exam_location": ["form1[0].Page1[0].Five[0].five[0]"],
    "position": ["form1[0].Page1[0].Seven[0].SevenA[0]"],
    "occupation": ["form1[0].Page1[0].Seven[0].SevenB[0]"],
    "medications": ["form1[0].Page1[0].Eight[0]"],
    "allergies": ["form1[0].Page1[0].Nine[0]"],
}

DD_TODAY_FIELD = "form1[0].Page1[0].Row1[0].Three[0]"
DD_ITEM_29_FIELD = "form1[0].Page2[0].TwentyNine[0]"

_DD_SIX = "form1[0].Page1[0].Six[0]"
DD_BRANCH_CHECKBOX = {
    "Army": f"{_DD_SIX}.SixA[0].#subform[0].sixA_Army[0]",
    "Navy": f"{_DD_SIX}.SixA[0].#subform[0].sixA_Navy[0]",
    "Marine Corps": f"{_DD_SIX}.SixA[0].#subform[0].sixA_Marine[0]",
    "Air Force": f"{_DD_SIX}.SixA[0].#subform[0].sixA_AirForce[0]",
    "Coast Guard": f"{_DD_SIX}.SixA[0].#subform[1].sixA_Coast[0]",
    "USPHS": f"{_DD_SIX}.SixA[0].#subform[1].sixA_usphs[0]",
    "Space Force": f"{_DD_SIX}.SixA[0].#subform[1].sixA_space[0]",
    "NOAA": f"{_DD_SIX}.SixA[0].#subform[1].sixA_noaa[0]",
}
DD_COMPONENT_CHECKBOX = {
    "Regular": f"{_DD_SIX}.SixB[0].sixB_Regular[0]",
    "Reserve": f"{_DD_SIX}.SixB[0].sixB_Reserve[0]",
    "National Guard": f"{_DD_SIX}.SixB[0].sixB_NationalGuard[0]",
}
DD_PURPOSE_CHECKBOX = {
    "Retention": f"{_DD_SIX}.SixC[0].LeftColumn[0].sixC_Retention[0]",
    "Separation": f"{_DD_SIX}.SixC[0].LeftColumn[0].sixC_Separation[0]",
    "Medical Board": f"{_DD_SIX}.SixC[0].LeftColumn[0].sixC_MedBoard[0]",
    "Retirement": f"{_DD_SIX}.SixC[0].LeftColumn[0].sixC_Retirement[0]",
}

# ------------------------------------------------------ SHA Part A mapping

SHA_TEXT_FIELDS = {
    "full_name": ["TI_1_1NAME"],
    "address": ["TI_5_1CURRENTADDRESS"],
    "phone": ["TI_7_3PERSONALTELEPHONENUMBER"],
    "email": ["TI_9_5PERSONALEMAIL"],
    "occupation": ["TA_44_4USUALOCCUPATIONMOSTRECENTDAYTODAYJOB"],
    "medications": ["TA_70_1LISTYOURCURRENTMEDICATIONSINCLUDINGSUPPLEMENTS"],
}

SHA_TODAY_FIELD = "TI_4_4TODAYSDATESELFASSESSMENTDATEYYYYMMDD"
SHA_DOB_FIELD = "TI_15_1DATEOFBIRTHDOBYYYYMMDD"
SHA_AGE_FIELD = "TI_16_2AGE"

SHA_RADIOS = {
    "branch": ("RG_1Service_1_Service", {
        "Army": "/Army", "Navy": "/Navy", "Marine Corps": "/Marine Corps",
        "Air Force": "/Air Force", "Space Force": "/Space Force",
        "Coast Guard": "/Coast Guard", "USPHS": "/Other", "NOAA": "/Other",
    }),
    "component": ("RG_2Component_2_Component", {
        "Regular": "/Active Duty", "Reserve": "/Reserve",
        "National Guard": "/National Guard",
    }),
    "duty_status": ("RG_3DutyStatus_3_Duty_Status", {
        "Active Component": "/Active Component",
        "Active Duty  Active Guard Reserve": "/Active Duty  Active Guard Reserve",
        "Active Duty  Non-Active Guard Reserve": "/Active Duty  Non-Active Guard Reserve",
        "Not on active duty": "/Not on active duty",
    }),
    "birth_sex": ("RG_4BirthSexbiologicalsex_4_Birth_Sex", {
        "Male": "/Male", "Female": "/Female",
    }),
    "purpose": ("RG_2PurposeofExam_2_Purpose_of_Exam", {
        "Separation": "/Separation from military service",
        "Retirement": "/Retirement",
        "Medical Board": "/Medical Board",
        "Retention": "/Other",
    }),
}


# --------------------------------------------------------------- building

def _yyyymmdd(iso_date):
    """Both forms ask for YYYYMMDD."""
    return iso_date.replace("-", "") if iso_date else ""


def _age_from_dob(iso_dob, today=None):
    if not iso_dob:
        return ""
    today = today or date.today()
    dob = date.fromisoformat(iso_dob)
    years = today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
    return str(years)


def validate(answers):
    """Returns a list of human-readable problems; empty means OK."""
    return [
        f"{label} is required."
        for key, label, *_ in QUESTIONS
        if key in REQUIRED and not (answers.get(key) or "").strip()
    ]


def dd2807_updates(answers, today=None):
    """Questionnaire answers -> {field_name: value} for DD 2807-1."""
    today = today or date.today()
    updates = {}

    for key, fields in DD_TEXT_FIELDS.items():
        value = (answers.get(key) or "").strip()
        if value:
            for field in fields:
                updates[field] = value

    updates[DD_TODAY_FIELD] = today.strftime("%Y%m%d")

    for key, table in (("branch", DD_BRANCH_CHECKBOX),
                        ("component", DD_COMPONENT_CHECKBOX),
                        ("purpose", DD_PURPOSE_CHECKBOX)):
        field = table.get(answers.get(key))
        if field:
            updates[field] = "/1"

    return updates


def sha_updates(answers, today=None):
    """Questionnaire answers -> {field_name: value} for SHA Part A."""
    today = today or date.today()
    updates = {}

    for key, fields in SHA_TEXT_FIELDS.items():
        value = (answers.get(key) or "").strip()
        if value:
            for field in fields:
                updates[field] = value

    updates[SHA_TODAY_FIELD] = today.strftime("%Y%m%d")

    dob = (answers.get("date_of_birth") or "").strip()
    if dob:
        updates[SHA_DOB_FIELD] = _yyyymmdd(dob)
        updates[SHA_AGE_FIELD] = _age_from_dob(dob, today)

    for key, (field, value_map) in SHA_RADIOS.items():
        export_value = value_map.get(answers.get(key))
        if export_value:
            updates[field] = export_value

    return updates
