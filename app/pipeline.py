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
    """Whether OCR can run here, and why not if it can't.

    Delegates to ocr_backends so the answer is the same on every platform
    and the reason is actionable rather than "not supported".
    """
    import ocr_backends
    return ocr_backends.describe()


def process_files(paths, work_dir, run_ocr=True, progress=None):
    """Ingest + extract each uploaded record. Returns (per_file, conditions)."""
    def report(msg):
        if progress:
            progress(msg)

    per_file, all_diag, all_prob, corpus = [], [], [], []

    for path in paths:
        name = os.path.basename(path)
        report(f"Reading {name}...")
        txt_path = os.path.join(work_dir, name + ".txt")

        # One unreadable file must not lose the whole run. Picking the wrong
        # file, a truncated download, or a renamed non-PDF are ordinary user
        # events, not exceptional ones -- and someone who just waited through
        # a large upload should get the results for the files that did work.
        try:
            n_chars, n_pages = ingest(path, txt_path)
        except Exception as exc:
            report(f"{name}: could not be read")
            per_file.append({
                "name": name, "pages": 0, "chars": 0,
                "diagnoses": 0, "problems": 0,
                "tier": "unreadable", "ocr": None,
                "warning": (
                    "This file could not be opened as a PDF, so nothing was "
                    "read from it. It may be corrupted, password-protected "
                    "with a password we don't have, or not a PDF at all. "
                    "Check the file and try again — the other files were "
                    "still processed."),
                "error_detail": f"{type(exc).__name__}",
            })
            continue

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
        corpus.append({"text": text, "page_starts": page_starts,
                       "source_document": source_document,
                       "method": "structured"})

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

                # The recovered text joins the corpus. Without this, OCR
                # only ever fed reconciliation, so a duty-limiting profile
                # the scanner read perfectly well could never become a
                # proposed answer -- the single biggest source of manual
                # work left for the member.
                ocr_text_parts, ocr_starts, off = [], [], 0
                for r in results:
                    ocr_starts.append(off)
                    ocr_text_parts.append(r["text"])
                    off += len(r["text"]) + 1
                corpus.append({"text": "\n".join(ocr_text_parts),
                               "page_starts": ocr_starts,
                               "source_document": name,
                               "method": "ocr"})
            elif run_ocr:
                entry["ocr_unavailable"] = reason

        per_file.append(entry)
        report(f"{name}: {len(diagnoses)} diagnoses, {len(problems)} problems")

    records = extract_conditions.aggregate(all_diag, all_prob)
    conditions = {
        "clinical": [r for r in records if not r["administrative"]],
        "administrative": [r for r in records if r["administrative"]],
    }
    return per_file, conditions, corpus


def find_record_prompts(corpus, proposals):
    """Keyword mentions worth asking about — see prompts.py.

    Runs after proposals so a question that already has a real, coded
    proposal doesn't also get flagged as a maybe.
    """
    from prompts import find_prompts
    with open(DD_CROSSWALK) as fh:
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
                prev["matched_terms"] = sorted(set(prev["matched_terms"] + pr["matched_terms"]))
            else:
                found[pr["item"]] = dict(pr)
    return sorted(found.values(), key=lambda p: (-p["mentions"], p["item"]))


def build_session_proposals(conditions, work_dir, birth_sex=None):
    """conditions dict -> (proposals, unmapped). Reuses proposals.py."""
    conditions_path = os.path.join(work_dir, "conditions.json")
    with open(conditions_path, "w") as fh:
        json.dump(conditions, fh, indent=2)
    return build_proposals(conditions_path, DD_CROSSWALK, SHA_FIELDS,
                           birth_sex=birth_sex)


def run_reconciliation(conditions, per_file):
    """Cross-source findings, when a file went through the OCR tier."""
    from reconcile import reconcile
    import hashlib
    findings = []
    for entry in per_file:
        if entry.get("ocr_results"):
            findings += reconcile(conditions["clinical"], entry["ocr_results"])
    for f in findings:
        raw = f"{f['icd10']}|{f['condition']}|{f['structured_first_seen']}"
        f["id"] = hashlib.sha256(raw.encode()).hexdigest()[:10]
        f["earliest"] = min(e["earliest_predating_date"] for e in f["ocr_evidence"])
        f["max_years_earlier"] = max(e["years_earlier"] for e in f["ocr_evidence"])
        f["scanned_pages"] = sorted({e["page"] for e in f["ocr_evidence"]})
        f["resolution"] = "unresolved"
    return findings
