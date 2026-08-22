#!/usr/bin/env python3
"""
app/server.py — the local web UI.

BUILD_BRIEF.md decision 2 (local-first) is enforced structurally here:
the server binds 127.0.0.1 only, record content never leaves the machine,
and no page loads an external asset. Uploaded records live in a temp
directory for the life of the session and are deleted on shutdown.

Run:
    python -m app.server        (or: ./run_app.sh)
"""

import atexit
import os
import shutil
import sys
import tempfile
import uuid
from datetime import date

from flask import (Flask, redirect, render_template, request,
                   send_file, session, url_for)

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import intake
import package_bundle
from app import pipeline
from buddy_letter import write_letters
from explanations import (conditions_by_ref, draft_dd2807_item_29,
                          draft_sha_explanations)
from fill_forms import fill_both
from schema import Proposal, confirmed_only

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

app = Flask(__name__)
# Session cookie only holds an opaque session id; all record data stays in
# SESSIONS below, in this process's memory, never in the cookie.
app.secret_key = os.urandom(32)
app.config["MAX_CONTENT_LENGTH"] = 512 * 1024 * 1024  # real exports run 20-40MB

SESSIONS = {}
WORK_ROOT = tempfile.mkdtemp(prefix="va-claims-prep-")


@atexit.register
def _cleanup():
    shutil.rmtree(WORK_ROOT, ignore_errors=True)


def current():
    sid = session.get("sid")
    if not sid or sid not in SESSIONS:
        sid = str(uuid.uuid4())
        session["sid"] = sid
        work_dir = os.path.join(WORK_ROOT, sid)
        os.makedirs(work_dir, exist_ok=True)
        SESSIONS[sid] = {"answers": {}, "work_dir": work_dir, "proposals": [],
                         "conditions": None, "per_file": [], "unmapped": [],
                         "findings": [], "prompts": [], "log": []}
    return SESSIONS[sid]


def blank_forms():
    """Blank form locations. Configurable so this isn't tied to ~/Downloads."""
    dd = os.environ.get("DD2807_BLANK",
                        os.path.expanduser("~/Downloads/dd2807-1.pdf"))
    sha = os.environ.get("SHA_BLANK", os.path.expanduser(
        "~/Downloads/SHA_DBQ_Part_A_Self-Assessment.pdf"))
    return dd, sha


# ------------------------------------------------------------ 1. intake

@app.route("/", methods=["GET", "POST"])
def index():
    state = current()
    errors = []
    if request.method == "POST":
        answers = {key: (request.form.get(key) or "").strip()
                   for key, *_ in intake.QUESTIONS}
        errors = intake.validate(answers)
        if not errors:
            state["answers"] = answers
            return redirect(url_for("upload"))
        state["answers"] = answers

    return render_template("intake.html", questions=intake.QUESTIONS,
                           answers=state["answers"], errors=errors,
                           required=intake.REQUIRED,
                           blank_reason=intake.BLANK_BY_DESIGN_REASON)


# ------------------------------------------------------------ 2. upload

@app.route("/upload", methods=["GET", "POST"])
def upload():
    state = current()
    if not state["answers"]:
        return redirect(url_for("index"))

    if request.method == "POST":
        files = [f for f in request.files.getlist("records") if f.filename]
        if not files:
            return render_template("upload.html", state=state,
                                   error="Choose at least one PDF.",
                                   ocr_ok=pipeline.ocr_available()[0],
                                   demo_ok=pipeline.demo_available())

        paths = []
        for f in files:
            safe = os.path.basename(f.filename)
            dest = os.path.join(state["work_dir"], safe)
            f.save(dest)
            paths.append(dest)

        run_ocr = request.form.get("run_ocr") == "on"
        state["log"] = []
        per_file, conditions, corpus = pipeline.process_files(
            paths, state["work_dir"], run_ocr=run_ocr,
            progress=state["log"].append)

        state["per_file"] = per_file
        state["conditions"] = conditions
        proposals, unmapped = pipeline.build_session_proposals(
            conditions, state["work_dir"])
        state["proposals"] = proposals
        state["unmapped"] = unmapped
        state["prompts"] = pipeline.find_record_prompts(corpus, proposals)
        if run_ocr:
            state["findings"] = pipeline.run_reconciliation(conditions, per_file)

        return redirect(url_for("review"))

    return render_template("upload.html", state=state, error=None,
                           ocr_ok=pipeline.ocr_available()[0],
                           demo_ok=pipeline.demo_available())


@app.route("/upload/demo", methods=["POST"])
def upload_demo():
    """Run the pipeline against the de-identified sample record."""
    state = current()
    if not state["answers"]:
        return redirect(url_for("index"))

    per_file, conditions, corpus = pipeline.process_demo()
    state["per_file"] = per_file
    state["conditions"] = conditions
    proposals, unmapped = pipeline.build_session_proposals(
        conditions, state["work_dir"])
    state["proposals"] = proposals
    state["unmapped"] = unmapped
    state["prompts"] = pipeline.find_record_prompts(corpus, proposals)
    state["findings"] = []
    state["demo"] = True
    return redirect(url_for("review"))


# ------------------------------------------------------------ 3. review

@app.route("/review", methods=["GET", "POST"])
def review():
    state = current()
    if not state["proposals"]:
        return redirect(url_for("upload"))

    if request.method == "POST":
        for p in state["proposals"]:
            decision = request.form.get(f"decision_{p.id}")
            if decision == "confirm":
                p.status = "confirmed"
                p.confirmed_value = p.proposed_value
            elif decision == "edit":
                new_value = (request.form.get(f"value_{p.id}") or "").strip()
                p.status = "edited"
                p.confirmed_value = new_value or p.proposed_value
            else:
                p.status = "rejected"
                p.confirmed_value = None

        # Cross-source conflicts: the member decides which date is right.
        # Unresolved is a real answer here, not a failure to answer — it
        # means "I don't know yet", which is what the VSO needs to see.
        for f in state.get("findings", []):
            choice = request.form.get(f"finding_{f['id']}")
            if choice in ("earlier", "coded", "unrelated"):
                f["resolution"] = choice
        return redirect(url_for("explain"))

    return render_template("review.html", state=state,
                           proposals=state["proposals"],
                           findings=state["findings"],
                           unmapped=state["unmapped"],
                           prompts=state.get("prompts", []))


# ------------------------------------- 3b. confirm drafted explanation text

@app.route("/explain", methods=["GET", "POST"])
def explain():
    state = current()
    confirmed = confirmed_only(state["proposals"])
    if not confirmed:
        return redirect(url_for("package"))

    by_ref = conditions_by_ref(state["conditions"]["clinical"])
    import json
    with open(os.path.join(REPO, "field_names_sha.json")) as fh:
        sha_names = list(json.load(fh).keys())
    with open(os.path.join(REPO, "dd2807_crosswalk.json")) as fh:
        crosswalk = json.load(fh)

    if request.method == "POST":
        state["item29"] = (request.form.get("item29") or "").strip()
        state["sha_explanations"] = {
            key[len("sha_"):]: value.strip()
            for key, value in request.form.items()
            if key.startswith("sha_") and value.strip()
        }
        return redirect(url_for("package"))

    state.setdefault("item29", draft_dd2807_item_29(
        confirmed, by_ref, crosswalk, state.get("findings")))
    state.setdefault("sha_explanations",
                     draft_sha_explanations(confirmed, by_ref, sha_names))
    from explanations import sha_explain_labels
    return render_template("explain.html", state=state,
                           item29=state["item29"],
                           sha_explanations=state["sha_explanations"],
                           sha_labels=sha_explain_labels(sha_names))


# ----------------------------------------------------------- 4. package

@app.route("/package")
def package():
    state = current()
    return render_template("package.html", state=state,
                           confirmed=confirmed_only(state["proposals"]),
                           blank_reason=intake.BLANK_BY_DESIGN_REASON)


@app.route("/package/download")
def download():
    state = current()
    answers = state["answers"]
    confirmed = confirmed_only(state["proposals"])
    work = state["work_dir"]
    dd_blank, sha_blank = blank_forms()

    dd_extra = intake.dd2807_updates(answers)
    sha_extra = intake.sha_updates(answers)

    if state.get("item29"):
        dd_extra[intake.DD_ITEM_29_FIELD] = state["item29"]
    for field, text in (state.get("sha_explanations") or {}).items():
        sha_extra[field] = text

    filled = fill_both(confirmed, dd_blank, sha_blank, work,
                       dd_extra=dd_extra, sha_extra=sha_extra)

    conditions = state["conditions"]
    sources = [f["name"] for f in state["per_file"]]
    worksheet = package_bundle.build_worksheet(
        conditions["clinical"], conditions["administrative"], sources,
        state["findings"])

    ocr_results = next((f.get("ocr_results") for f in state["per_file"]
                        if f.get("ocr_results")), None)
    evidence = package_bundle.build_evidence_index(
        conditions["clinical"], ocr_results)

    confirmed_refs = {p.condition_ref for p in confirmed}
    letter_conditions = [c for c in conditions["clinical"]
                         if (c["icd10"] or c["condition"]) in confirmed_refs]
    letters = write_letters(answers.get("full_name", ""), letter_conditions,
                            os.path.join(work, "buddy_letters"))

    out_zip = os.path.join(work, f"VSO_package_{date.today().isoformat()}.zip")
    package_bundle.build_bundle(
        out_zip, answers.get("full_name", ""),
        {k: v[1] for k, v in filled.items()},
        worksheet, evidence, letters, state["unmapped"],
        prompts_text=package_bundle.build_prompts_doc(state.get("prompts", [])))

    return send_file(out_zip, as_attachment=True,
                     download_name=os.path.basename(out_zip))


def main():
    port = int(os.environ.get("PORT", "5000"))
    print(f"\n  VA Claims Prep -- http://127.0.0.1:{port}")
    print("  Local only. Records are processed on this machine and never "
          "uploaded.\n")
    # 127.0.0.1, never 0.0.0.0: nothing on the local network can reach this.
    app.run(host="127.0.0.1", port=port, debug=False)


if __name__ == "__main__":
    main()
