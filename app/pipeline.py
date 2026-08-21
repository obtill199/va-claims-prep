#!/usr/bin/env python3
"""
app/pipeline.py — orchestrates the existing CLI modules for one web session.

Deliberately thin: every real operation already exists and is verified from
Milestones 1-4. This just sequences them and reports per-file extraction
confidence loudly, per BUILD_BRIEF.md decision 3 -- a file that yields
nothing must say so, never fail silently (section 3.1).
"""

import json
import os
import platform
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import extract_conditions
from ingest import ingest
from proposals import build_proposals

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DD_CROSSWALK = os.path.join(REPO, "dd2807_crosswalk.json")
SHA_FIELDS = os.path.join(REPO, "field_names_sha.json")


def ocr_available():
    """OCR uses macOS's Vision framework -- see ocr.py. Not portable yet."""
    if platform.system() != "Darwin":
        return False, "OCR requires macOS (uses the built-in Vision framework)."
    try:
        import Vision  # noqa: F401
        return True, None
    except ImportError:
        return False, "pyobjc Vision bindings are not installed."


def process_files(paths, work_dir, run_ocr=True, progress=None):
    """Ingest + extract each uploaded record. Returns (per_file, conditions)."""
    def report(msg):
        if progress:
            progress(msg)

    per_file, all_diag, all_prob = [], [], []

    for path in paths:
        name = os.path.basename(path)
        report(f"Reading {name}...")
        txt_path = os.path.join(work_dir, name + ".txt")
        n_chars, n_pages = ingest(path, txt_path)

        with open(txt_path, encoding="utf-8", errors="replace") as fh:
            text = fh.read()
        sidecar_path = txt_path + ".pages.json"
        page_starts, source_document = None, name
        if os.path.exists(sidecar_path):
            with open(sidecar_path) as fh:
                sidecar = json.load(fh)
            page_starts = sidecar["page_starts"]
            source_document = sidecar["source_document"]

        diagnoses = list(extract_conditions.parse_diagnoses(
            text, page_starts, source_document))
        problems = list(extract_conditions.parse_problems(text))
        all_diag += diagnoses
        all_prob += problems

        entry = {
            "name": name,
            "pages": n_pages,
            "chars": n_chars,
            "diagnoses": len(diagnoses),
            "problems": len(problems),
            "tier": "structured" if diagnoses else "no-text-layer",
            "ocr": None,
        }

        # The failure the brief says must never be silent: a scanned file
        # with a poor text layer yields zero structured diagnoses and looks
        # identical to a clean file that simply had nothing in it.
        if not diagnoses:
            entry["warning"] = (
                "No structured diagnoses found. This is expected for scanned "
                "records (AF forms, legacy STRs) whose text layer is poor or "
                "absent. Nothing from this file was extracted into the "
                "conditions list.")
            available, reason = ocr_available()
            if run_ocr and available:
                report(f"OCR-ing {name} (this takes a few minutes)...")
                from ocr import ocr_pdf
                results = ocr_pdf(path)
                entry["ocr"] = {
                    "pages": len(results),
                    "medium": sum(1 for r in results if r["confidence"] == "medium"),
                    "low": [r["page"] for r in results if r["confidence"] == "low"],
                }
                entry["ocr_results"] = results
                entry["tier"] = "ocr"
            elif run_ocr:
                entry["ocr_unavailable"] = reason

        per_file.append(entry)
        report(f"{name}: {len(diagnoses)} diagnoses, {len(problems)} problems")

    records = extract_conditions.aggregate(all_diag, all_prob)
    conditions = {
        "clinical": [r for r in records if not r["administrative"]],
        "administrative": [r for r in records if r["administrative"]],
    }
    return per_file, conditions


DEMO_TXT = os.path.join(REPO, "demo", "demo_record.txt")


def demo_available():
    return os.path.exists(DEMO_TXT)


def process_demo():
    """Load the de-identified sample record.

    BUILD_BRIEF.md decision 4 makes demo mode first-class: the tool has to be
    demonstrable and user-testable without anyone handling real PHI. The demo
    file is pre-extracted text (pii_scrub.py output) rather than a PDF, so it
    skips ingest.py and joins the pipeline at the same point a real file does
    — same parser, same aggregation, same page citations.
    """
    with open(DEMO_TXT, encoding="utf-8", errors="replace") as fh:
        text = fh.read()
    with open(DEMO_TXT + ".pages.json") as fh:
        sidecar = json.load(fh)

    diagnoses = list(extract_conditions.parse_diagnoses(
        text, sidecar["page_starts"], sidecar["source_document"]))
    problems = list(extract_conditions.parse_problems(text))
    records = extract_conditions.aggregate(diagnoses, problems)

    per_file = [{
        "name": sidecar["source_document"],
        "pages": len(sidecar["page_starts"]),
        "chars": len(text),
        "diagnoses": len(diagnoses),
        "problems": len(problems),
        "tier": "structured",
        "ocr": None,
        "demo": True,
    }]
    conditions = {
        "clinical": [r for r in records if not r["administrative"]],
        "administrative": [r for r in records if r["administrative"]],
    }
    return per_file, conditions


def build_session_proposals(conditions, work_dir):
    """conditions dict -> (proposals, unmapped). Reuses proposals.py."""
    conditions_path = os.path.join(work_dir, "conditions.json")
    with open(conditions_path, "w") as fh:
        json.dump(conditions, fh, indent=2)
    return build_proposals(conditions_path, DD_CROSSWALK, SHA_FIELDS)


def run_reconciliation(conditions, per_file):
    """Cross-source findings, when a file went through the OCR tier."""
    from reconcile import reconcile
    findings = []
    for entry in per_file:
        if entry.get("ocr_results"):
            findings += reconcile(conditions["clinical"], entry["ocr_results"])
    return findings
