"""
web_pipeline.py — the browser build's replacement for pdf_io.py + ingest.py.

Runs inside Pyodide. Everything else — extract_conditions, field_map,
proposals, explanations, intake, prompts, schema — is imported unchanged
from the same source the desktop app uses, which is the point: the browser
build must not become a second, drifting implementation of the parser.

Two things had to be replaced, both because they are compiled extensions
that cannot run in WebAssembly:

  pdfplumber/PyMuPDF text extraction -> pypdf's own layout mode. Verified to
  produce identical results on the sample record: 25 diagnoses, 6 problem
  entries, 13 clinical conditions, provider names parsed correctly. The
  parser's regexes were already written to tolerate column-padded layout,
  which is why this substitution works at all.

  PyMuPDF decryption -> not needed. The blank forms are decrypted at build
  time by tools/prep_web_forms.py, so the browser only ever sees plaintext
  PDFs and never needs the `cryptography` extension.

OCR has no browser equivalent — it used macOS's Vision framework — so
scanned records degrade with an explicit message rather than silently
yielding nothing.
"""

import io
import json
import schema

from pypdf import PdfReader, PdfWriter
from pypdf.generic import BooleanObject, NameObject

import extract_conditions
from explanations import (conditions_by_ref, draft_dd2807_item_29,
                          draft_sha_explanations, sha_explain_labels)
from field_map import build_mapping
from proposals import build_proposals, proposals_from_prompts
from prompts import find_prompts
from schema import confirmed_only


# ------------------------------------------------------------- extraction

def extract_text_with_pages(pdf_bytes):
    """Layout-preserving text plus per-page character offsets.

    `extraction_mode="layout"` is pypdf's equivalent of poppler's
    `pdftotext -layout`, and preserves the column alignment the diagnosis
    regexes depend on.
    """
    reader = PdfReader(io.BytesIO(pdf_bytes))
    parts, page_starts, offset = [], [], 0
    for page in reader.pages:
        try:
            text = page.extract_text(extraction_mode="layout") or ""
        except Exception:
            text = page.extract_text() or ""
        page_starts.append(offset)
        parts.append(text)
        offset += len(text) + 1
    return "\n".join(parts), page_starts


def process_files(files):
    """files: [(filename, bytes)] -> (per_file, conditions, corpus)."""
    per_file, all_diag, all_prob, corpus = [], [], [], []

    for name, data in files:
        try:
            text, page_starts = extract_text_with_pages(data)
        except Exception as exc:
            per_file.append({
                "name": name, "pages": 0, "chars": 0, "diagnoses": 0,
                "problems": 0, "tier": "unreadable", "ocr": None,
                "warning": ("This file could not be opened as a PDF, so "
                            "nothing was read from it. It may be corrupted, "
                            "password-protected, or not a PDF at all. The "
                            "other files were still processed."),
                "error_detail": type(exc).__name__,
            })
            continue

        diagnoses = list(extract_conditions.parse_diagnoses(
            text, page_starts, name))
        problems = list(extract_conditions.parse_problems(text))

        # MHS Genesis is one layout among many. Fall back to the generic
        # coded-record parser for CCD-A exports, claims and pharmacy ledgers.
        narrative = False
        if not diagnoses:
            import coded_records
            if coded_records.looks_narrative(text):
                narrative = True
            else:
                diagnoses = coded_records.extract(text, page_starts, name)
        all_diag += diagnoses
        all_prob += problems
        corpus.append({"text": text, "page_starts": page_starts,
                       "source_document": name, "method": "structured"})

        entry = {"name": name, "pages": len(page_starts), "chars": len(text),
                 "diagnoses": len(diagnoses), "problems": len(problems),
                 "tier": "structured" if diagnoses else "no-text-layer",
                 "ocr": None}
        if not diagnoses:
            entry["tier"] = "narrative" if narrative else "no-text-layer"
            entry["warning"] = (
                "This record is written as narrative text — progress notes, "
                "chronological SF-600 entries or imaging reports — and "
                "contains no diagnosis codes. Reading a diagnosis out of a "
                "sentence is a different problem from matching a code, and "
                "this tool does not attempt it. Nothing was extracted from "
                "this file; bring it to your VSO directly."
                if narrative else
                "No structured diagnoses were found and no text could be "
                "recovered. This is expected for scanned records. Recovering "
                "those needs OCR, which this browser version cannot do — the "
                "desktop version can.")
        per_file.append(entry)

    records = extract_conditions.aggregate(all_diag, all_prob)
    conditions = {
        "clinical": [r for r in records if not r["administrative"]],
        "administrative": [r for r in records if r["administrative"]],
    }
    return per_file, conditions, corpus


def build_review(conditions, corpus, birth_sex=None):
    """conditions + corpus -> (proposals, unmapped) ready for review."""
    with open("conditions.json", "w") as fh:
        json.dump(conditions, fh)

    proposals, unmapped = build_proposals(
        "conditions.json", "dd2807_crosswalk.json", "field_names_sha.json",
        birth_sex=birth_sex)
    with open("dd2807_crosswalk.json") as fh:
        rows = json.load(fh)

    already = {p.target_field for p in proposals}
    found = {}
    for entry in corpus:
        for pr in find_prompts(entry["text"], rows, entry["page_starts"], already):
            pr["source_document"] = entry["source_document"]
            pr["method"] = entry["method"]
            prev = found.get(pr["item"])
            if prev:
                prev["mentions"] += pr["mentions"]
                prev["pages"] = sorted(set(prev["pages"] + pr["pages"]))[:4]
                prev["matched_terms"] = sorted(
                    set(prev["matched_terms"] + pr["matched_terms"]))
            else:
                found[pr["item"]] = dict(pr)

    weak = proposals_from_prompts(
        sorted(found.values(), key=lambda p: (-p["mentions"], p["item"])))
    rank = schema.confidence_rank
    merged = sorted(proposals + weak,
                    key=lambda p: (rank(p.confidence), p.target_form,
                                   p.question_text))
    return merged, unmapped


# --------------------------------------------------------------- filling

def _dd_updates(props):
    import re
    out = {}
    for p in props:
        if p.confirmed_value == "Yes":
            out[p.target_field] = "/1"
        elif p.confirmed_value == "No":
            out[re.sub(r"\bYes(\d)", r"No\1", p.target_field)] = "/1"
    return out


def _sha_updates(props):
    return {p.target_field: f"/{p.confirmed_value}"
            for p in props if p.confirmed_value in ("Yes", "No")}


def fill_form(blank_bytes, updates):
    """Pure-pypdf form fill. Mirrors fill_forms.py, minus the decryption
    step the desktop build needs (blanks are decrypted at build time)."""
    reader = PdfReader(io.BytesIO(blank_bytes))
    live = reader.get_fields() or {}
    missing = [n for n in updates if n not in live]
    if missing:
        raise ValueError(f"{len(missing)} field(s) not found in the form: "
                         f"{missing[:3]}")

    writer = PdfWriter()
    writer.append(reader)

    acro = writer.root_object.get("/AcroForm")
    if acro is not None:
        acro = acro.get_object()
        acro[NameObject("/NeedAppearances")] = BooleanObject(True)
        # DD 2807-1 is a hybrid XFA form; viewers that prefer the XFA stream
        # would render a blank form over the AcroForm we just filled.
        if "/XFA" in acro:
            del acro["/XFA"]

    for page in writer.pages:
        writer.update_page_form_field_values(page, updates,
                                             auto_regenerate=False)
    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()


def build_outputs(answers, proposals, conditions, per_file, item29,
                  sha_explanations, dd_blank, sha_blank):
    """Everything the member downloads. Returns {filename: bytes|str}."""
    import intake
    import package_bundle

    confirmed = confirmed_only(proposals)

    dd_extra = intake.dd2807_updates(answers)
    sha_extra = intake.sha_updates(answers)
    if item29:
        dd_extra[intake.DD_ITEM_29_FIELD] = item29
    for field, text in (sha_explanations or {}).items():
        if text:
            sha_extra[field] = text

    dd_updates = dict(dd_extra)
    dd_updates.update(_dd_updates(
        [p for p in confirmed if p.target_form == "DD2807-1"]))
    sha_up = dict(sha_extra)
    sha_up.update(_sha_updates(
        [p for p in confirmed if p.target_form == "SHA_PART_A"]))

    out = {
        "dd2807-1_FILLED.pdf": fill_form(dd_blank, dd_updates),
        "sha_part_a_FILLED.pdf": fill_form(sha_blank, sha_up),
    }

    sources = [f["name"] for f in per_file]
    package_bundle.annotate_reached(conditions["clinical"], confirmed)
    out["conditions_worksheet.md"] = package_bundle.build_worksheet(
        conditions["clinical"], conditions["administrative"], sources, None,
        exposures=answers.get("exposures"))
    out["evidence_index.md"] = package_bundle.build_evidence_index(
        conditions["clinical"], None)

    confirmed_refs = {p.condition_ref for p in confirmed}
    # Self-reported conditions get a letter whether or not they reached a
    # form question. The ones that reached nothing are exactly the ones with
    # no other evidence anywhere -- gating them behind a confirmed proposal
    # would drop the only claim a lay statement could still support.
    letter_conditions = [c for c in conditions["clinical"]
                         if c.get("self_reported")
                         or (c["icd10"] or c["condition"]) in confirmed_refs]
    letter_conditions.sort(key=lambda c: (not c.get("self_reported"),
                                          c.get("condition", "")))
    for name, text in _buddy_letters(answers.get("full_name", ""),
                                     letter_conditions).items():
        out[f"buddy_letters/{name}"] = text

    import timing as _timing
    _assess = _timing.assess(answers.get("separation_date"),
                             component=answers.get("component"),
                             duty_status=answers.get("duty_status"))
    _assess["caveat"] = _timing.bdd_eligibility_caveat(
        answers.get("component"), answers.get("duty_status"))
    out["README.txt"] = package_bundle.render_readme(
        member_name=answers.get("full_name"),
        contents="\n".join(f"  {k}" for k in sorted(out)),
        unmapped_note="See conditions_worksheet.md for everything found.",
        timing=_assess,
        conditions=conditions["clinical"],
        exposures=answers.get("exposures"))
    return out


BUDDY_PROMPTS = [
    "How do you know the veteran, and for how long?",
    "What did you personally see or hear? Specific moments, not general "
    "impressions.",
    "When did you first notice it? What was different before versus after?",
    "How does it affect their day to day — work, sleep, relationships, "
    "physical activity?",
    "Has it got better, worse, or stayed the same?",
    "Anything else you witnessed that a doctor's notes would not capture?",
]


def _buddy_letters(member_name, conditions):
    """Markdown rather than .docx: python-docx needs lxml, a compiled
    extension unavailable in the browser. Same content, opens anywhere."""
    def one(cond=None):
        subject = cond["condition"] if cond else "general statement"
        lines = [f"# Buddy Letter / Lay Statement", "",
                 f"**Regarding:** {member_name}", f"**Subject:** {subject}", "",
                 "## Your information", "", "- Full name: ",
                 "- Relationship to the veteran: ", "- Address: ",
                 "- Phone: ", "- Email: ", ""]
        if cond and cond.get("self_reported"):
            # This is the letter that decides something. A documented
            # condition has a clinician's note carrying it; this one has
            # nothing but the member's word, and somebody who saw it is the
            # only evidence that will ever exist. Say so, so the person
            # writing it knows it is not a formality.
            lines += ["## Why this letter matters more than the others", "",
                      f"There is no medical record for "
                      f"{cond['condition'].lower()}. It was never written "
                      f"down at the time — which is ordinary, and is not "
                      f"evidence it did not happen. What you personally saw "
                      f"is the evidence.", "",
                      "Be specific: dates, places, what changed, what they "
                      "stopped being able to do. Do not guess at a diagnosis "
                      "or use medical words — describe what you observed and "
                      "let the doctors name it.", ""]
        elif cond:
            icd = f" ({cond['icd10']})" if cond.get("icd10") else ""
            span = (cond["first_seen"] if cond["first_seen"] == cond["last_seen"]
                    else f"{cond['first_seen']} to {cond['last_seen']}")
            lines += ["## What the medical record already documents", "",
                      f"{cond['condition']}{icd} — documented {span}, "
                      f"{cond['encounters']} encounter"
                      f"{'s' if cond['encounters'] != 1 else ''}.", "",
                      "This is context so your statement lines up with the "
                      "record. Don't repeat it back — write what you saw.", ""]
        lines += ["## What to address", ""]
        lines += [f"- {p}" for p in BUDDY_PROMPTS]
        lines += ["", "## Your statement", "", "", "_" * 60, "", "",
                  "Signature: ______________________  Date: ____________", "",
                  "---", "",
                  "Write in your own words. Only write what you personally "
                  "witnessed — don't guess at diagnoses or causes. Be specific "
                  "with dates where you can. Sign and date it."]
        return "\n".join(lines)

    import re
    out = {"buddy_letter_GENERAL.md": one()}
    for c in conditions:
        slug = re.sub(r"[^A-Za-z0-9]+", "_", c["condition"]).strip("_")[:50]
        prefix = "NEEDED_" if c.get("self_reported") else ""
        out[f"buddy_letter_{prefix}{slug}.md"] = one(c)
    return out
