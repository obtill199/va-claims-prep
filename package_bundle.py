#!/usr/bin/env python3
"""
package_bundle.py — Milestone 6's deliverable: the VSO package.

Bundles everything the member hands to an accredited VSO into one zip:
both filled forms, a conditions worksheet, buddy-letter templates, an
evidence index, and a README explaining what the package is and what it
deliberately does not contain.

BUILD_BRIEF.md decision 5: this is the endpoint. The tool does not submit
anything to VA and does not advise on what to claim.
"""

import os
import zipfile
from datetime import date

README = """VA CLAIMS PREP PACKAGE
Generated {today}
For: {member_name}
{timing_block}
WHAT THIS IS
------------
An organized starting point for an appointment with an accredited
Veterans Service Officer (VSO). Everything here was assembled from your
own health records.

WHAT IT IS NOT
--------------
This is not a filed claim. Nothing here has been submitted to VA. This
tool does not decide, advise, or predict what you should claim or what
you are entitled to -- that is your VSO's job, and they are accredited to
do it. Every entry needs their review before it goes anywhere.

STILL TO DO -- THIS PACKAGE IS NOT FINISHED
-------------------------------------------
[ ] 1. Social Security Number and DoD ID, by hand. Both forms ask for
       each of them more than once -- EIGHT boxes across FOUR places:
       DD 2807-1  - items 2a and 2b on page 1        (SSN, DoD ID)
       DD 2807-1  - the header of page 2             (SSN, DoD ID)
       DD 2807-1  - the header of page 3             (SSN, DoD ID)
       SHA Part A - section 1                        (SSN, DoD ID)
       This tool never collects or writes those. Every other identity
       field is already filled from what you entered.

[ ] 2. Replace every "[Add treatment received]" in Item 29 on page 2.
       The form asks what treatment you had; your records do not state it
       in a form this tool can read. Physical therapy, medication,
       surgery, an injection -- or "no treatment" if that is true.

[ ] 3. Read every checked "Yes" and its explanation once more. You
       affirmed each during review, but DD Form 2807-1 carries a federal
       false-statement warning: up to 5 years confinement or a $10,000
       fine.

[ ] 4. Answer any question this tool left blank. It only proposes an
       answer when your records support one. A blank is not a "no" -- it
       means nothing in your records spoke to it, and you may well have
       an answer it could not see.

[ ] 5. Sign and date both forms -- AFTER your VSO has reviewed them.
       They are unsigned by design.

[ ] 6. Send the buddy-letter templates to people who actually witnessed
       what they describe.

WHAT TO ASK YOUR VSO
--------------------
- Which of these conditions are worth claiming?
- Are any of them presumptive for where and when I served?
- What is missing from this file?
- If still serving: am I inside the 180-to-90-day BDD window?

CONTENTS
--------
{contents}

CONDITIONS NOT INCLUDED
-----------------------
{unmapped_note}

FIND A VSO
----------
Accredited representatives can be found through VA's official directory:
va.gov/get-help-from-accredited-representative
Your state's Department of Veterans Affairs and service organizations
(VFW, American Legion, DAV, and others) also provide free VSO services.
"""

WORKSHEET_HEADER = """# Conditions Worksheet

Generated {today} from: {sources}

**Every row requires VSO verification before use.** This worksheet reports
what the health records contain. It does not assess severity, causation,
or service connection.

## Clinical conditions

| ICD-10 | Condition | Body system | First seen | Last seen | Enc. | Status | Problem list | Source |
|---|---|---|---|---|---|---|---|---|
"""


def build_worksheet(conditions, administrative, sources, findings=None):
    today = date.today().isoformat()
    out = [WORKSHEET_HEADER.format(today=today, sources=", ".join(sources))]

    for c in conditions:
        cite = c.get("source_document") or ""
        page = f", p. {c['source_page']}" if c.get("source_page") else ""
        out.append(
            f"| {c['icd10'] or '—'} | {c['condition']} | {c['body_system']} "
            f"| {c['first_seen']} | {c['last_seen']} | {c['encounters']} "
            f"| {'Active' if c['active'] else 'Inactive'} "
            f"| {'Yes' if c['on_problem_list'] else '—'} | {cite}{page} |")

    if administrative:
        out.append("\n## Administrative / encounter codes "
                   "(excluded from claim consideration)\n")
        out.append("| Code | Entry | First seen |")
        out.append("|---|---|---|")
        for a in administrative:
            out.append(f"| {a['icd10'] or '—'} | {a['condition']} "
                       f"| {a['first_seen']} |")

    if findings:
        out.append("\n## Cross-source flags — REVIEW WITH YOUR VSO\n")
        out.append("Evidence found in scanned documents that predates the "
                   "earliest coded date for the same body system. These are "
                   "keyword-and-date matches from OCR, not confirmed links — "
                   "each one needs a human to open the cited page and judge "
                   "whether it actually relates.\n")
        LABEL = {
            "earlier": "MEMBER CONFIRMED the earlier date is correct",
            "coded": "MEMBER CONFIRMED the coded date is correct",
            "unrelated": "Member reviewed and judged these pages unrelated",
            "unresolved": "NOT YET RESOLVED — needs review with your VSO",
        }
        for f in findings:
            verdict = LABEL.get(f.get("resolution", "unresolved"))
            out.append(f"- **{f['condition']} ({f['icd10']})** — coded first "
                       f"seen {f['structured_first_seen']}. _{verdict}._")
            for e in f["ocr_evidence"]:
                out.append(f"  - Scanned p. {e['page']} suggests "
                           f"{e['earliest_predating_date']} "
                           f"({e['years_earlier']} years earlier) — matched "
                           f"{', '.join(e['matched_keywords'])} "
                           f"[{e['confidence']} OCR confidence]")

    return "\n".join(out) + "\n"


def build_prompts_doc(prompts):
    """Questions the coded record can't answer but the narrative hints at."""
    if not prompts:
        return "No additional questions were flagged.\n"
    lines = [
        "# Questions To Check By Hand\n",
        "These DD 2807-1 items have **no coded diagnosis** behind them, so "
        "nothing was proposed or checked for them. But these terms do appear "
        "in your records on the pages listed. Most real \"Yes\" answers live "
        "here — in narrative notes, PHA self-reports and scanned forms — not "
        "in the coded diagnosis list.\n",
        "Open the cited pages, decide for yourself, and mark by hand what "
        "applies.\n",
        "| Item | Question | Terms found | Pages |",
        "|---|---|---|---|",
    ]
    for p in prompts:
        lines.append(f"| {p['item']} | {p['question_text']} | "
                     f"{', '.join(p['matched_terms'])} | "
                     f"{', '.join(str(x) for x in p['pages'])} |")
    return "\n".join(lines) + "\n"


def build_evidence_index(conditions, ocr_results=None):
    lines = ["# Evidence Index\n",
             "Where each condition came from, so your VSO can go straight to "
             "the page.\n",
             "| Condition | ICD-10 | Source document | Page |",
             "|---|---|---|---|"]
    for c in conditions:
        lines.append(f"| {c['condition']} | {c['icd10'] or '—'} "
                     f"| {c.get('source_document') or '—'} "
                     f"| {c.get('source_page') or '—'} |")

    if ocr_results:
        low = [r["page"] for r in ocr_results if r["confidence"] == "low"]
        if low:
            lines.append("\n## Pages that could not be read reliably\n")
            lines.append(
                "These pages of the scanned record produced little or no "
                "readable text — handwriting, stamps, signatures, or blank "
                "pages. **Nothing on them was extracted.** Review them by "
                "hand; a duty limitation or diagnosis written by hand would "
                "not appear anywhere else in this package.\n")
            lines.append(f"Pages: {', '.join(str(p) for p in low)}")

    return "\n".join(lines) + "\n"


def format_timing(assessment):
    """The deadline, as the first thing in the README rather than a footnote.
    A member who reads this file once reads the top of it."""
    if not assessment or assessment.get("state") == "unknown":
        return ""
    rule = "=" * 68
    lines = ["", rule, "  " + assessment["headline"].upper(), rule, ""]
    for chunk in assessment["detail"].split(". "):
        chunk = chunk.strip()
        if chunk:
            lines.append("  " + chunk.rstrip(".") + ".")
    if assessment.get("actions"):
        lines.append("")
        for i, act in enumerate(assessment["actions"], 1):
            lines.append(f"  {i}. {act}")
    if assessment.get("caveat"):
        lines += ["", "  CHECK THIS FIRST: " + assessment["caveat"]]
    lines += ["", "  (Worked out from the separation date you entered. If that date",
              "   was wrong, every deadline above moves with it.)", ""]
    return "\n".join(lines)


def build_bundle(out_zip, member_name, filled_forms, worksheet_text,
                 evidence_text, buddy_letter_paths, unmapped_conditions=None,
                 prompts_text=None, timing=None):
    contents, arcnames = [], {}

    for label, path in filled_forms.items():
        arc = os.path.basename(path)
        arcnames[path] = arc
        contents.append(f"  {arc}  —  {label}, prefilled and unsigned")

    contents.append("  conditions_worksheet.md  —  every condition found, with citations")
    contents.append("  evidence_index.md  —  where each condition came from")
    if prompts_text:
        contents.append("  questions_to_check.md  —  items to review and mark by hand")
    for path in buddy_letter_paths:
        contents.append(f"  buddy_letters/{os.path.basename(path)}")

    if unmapped_conditions:
        unmapped_note = (
            "These conditions appear in your records but were NOT matched to "
            "a question on either form, so no box was checked for them. That "
            "is deliberate -- this tool only proposes an answer when the match "
            "is unambiguous. Raise them with your VSO directly:\n\n"
            + "\n".join(f"  - {c['condition']} ({c['icd10'] or 'uncoded'})"
                        for c in unmapped_conditions))
    else:
        unmapped_note = "All extracted conditions were matched to a form question."

    readme = README.format(
        timing_block=format_timing(timing),
        today=date.today().isoformat(),
        member_name=member_name or "(name not provided)",
        contents="\n".join(contents),
        unmapped_note=unmapped_note)

    with zipfile.ZipFile(out_zip, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("README.txt", readme)
        z.writestr("conditions_worksheet.md", worksheet_text)
        z.writestr("evidence_index.md", evidence_text)
        if prompts_text:
            z.writestr("questions_to_check.md", prompts_text)
        for path, arc in arcnames.items():
            z.write(path, arc)
        for path in buddy_letter_paths:
            z.write(path, f"buddy_letters/{os.path.basename(path)}")

    return out_zip
