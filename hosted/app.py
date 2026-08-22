#!/usr/bin/env python3
"""
hosted/app.py — prototype shell for a hosted version.

PURPOSE
-------
To make the client/server split concrete so it can be designed against: what
crosses the network, where it lands, how long it lives, and exactly which
controls a real deployment owes. It reuses the local tool's pipeline
unchanged so the conversation stays about the trust boundary rather than the
extraction logic.

THIS IS NOT DEPLOYABLE. Every security control in hosted/security.py is an
unimplemented stub, and start-up refuses any non-loopback bind while that is
true. See hosted/SECURITY_REQUIREMENTS.md.

WHAT CHANGES WHEN THIS GOES HOSTED
----------------------------------
The local tool has no attack surface worth the name: no network listener
reachable off-box, no accounts, no stored records, no operator. Every one of
those properties is a security control, and hosting trades all of them away
at once. This file exists to make that trade visible rather than implicit.

Run (loopback only):
    PROTOTYPE_ACK=1 python -m hosted.app
"""

import os
import secrets
import sys
import time

from flask import Flask, jsonify, request

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from hosted import security

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 128 * 1024 * 1024

# In memory only, and deliberately so: this prototype must not be able to
# leave PHI on a disk. A real deployment replaces this with storage that
# goes through security.encrypt_at_rest() and security.enforce_retention().
JOBS: dict[str, dict] = {}
JOB_TTL_SECONDS = 15 * 60


def _reap():
    """Stand-in for security.enforce_retention(). Not a substitute for it --
    this is best-effort, in-process, and dies with the process."""
    now = time.time()
    for jid in [j for j, v in JOBS.items() if now - v["created"] > JOB_TTL_SECONDS]:
        JOBS.pop(jid, None)


def _guard():
    """Refuse to do anything real while the controls are stubs."""
    missing = security.unimplemented_controls()
    if missing:
        return jsonify({
            "error": "security controls not implemented",
            "unimplemented": missing,
            "detail": ("This is an architecture prototype. It will not accept "
                       "records until these are implemented. See "
                       "hosted/SECURITY_REQUIREMENTS.md."),
        }), 501
    return None


@app.get("/api/health")
def health():
    return jsonify({
        "status": "prototype",
        "accepts_records": not security.unimplemented_controls(),
        "unimplemented_controls": security.unimplemented_controls(),
    })


@app.post("/api/jobs")
def create_job():
    """Accept records for processing.

    Ordering matters and is the point of this stub: authenticate, then scan,
    then encrypt -- before any parser sees the bytes. The local tool can skip
    all three because the bytes never left the machine that produced them.
    """
    blocked = _guard()
    if blocked:
        return blocked

    subject = security.authenticate(request)               # IA-2
    security.audit_log("job.create.attempt", subject=subject)

    files = [f for f in request.files.getlist("records") if f.filename]
    if not files:
        return jsonify({"error": "no files"}), 400

    job_id = secrets.token_urlsafe(32)                     # unguessable: AC-3
    stored = []
    for f in files:
        data = f.read()
        security.scan_upload(f.filename, data)             # SI-3
        stored.append({"name": os.path.basename(f.filename),
                       "blob": security.encrypt_at_rest(data)})   # SC-28

    JOBS[job_id] = {"subject": subject, "files": stored,
                    "created": time.time(), "status": "queued"}
    security.audit_log("job.create", subject=subject, job_id=job_id,
                       file_count=len(stored))
    _reap()
    return jsonify({"job_id": job_id, "status": "queued"}), 201


@app.get("/api/jobs/<job_id>")
def job_status(job_id):
    blocked = _guard()
    if blocked:
        return blocked
    subject = security.authenticate(request)
    job = JOBS.get(job_id)
    if not job:
        return jsonify({"error": "not found"}), 404
    security.authorize(subject, job)                       # IDOR check: AC-3
    security.audit_log("job.read", subject=subject, job_id=job_id)
    return jsonify({"job_id": job_id, "status": job["status"]})


@app.delete("/api/jobs/<job_id>")
def destroy_job(job_id):
    """Explicit destruction. The strongest control this design has is not
    keeping the data (SI-12), so deleting must be a first-class operation,
    not a side effect of expiry."""
    blocked = _guard()
    if blocked:
        return blocked
    subject = security.authenticate(request)
    job = JOBS.get(job_id)
    if not job:
        return jsonify({"error": "not found"}), 404
    security.authorize(subject, job)
    JOBS.pop(job_id, None)
    security.audit_log("job.destroy", subject=subject, job_id=job_id)
    return jsonify({"destroyed": job_id})


def main():
    if not os.environ.get("PROTOTYPE_ACK"):
        sys.exit(
            "\nThis is an unsecured architecture prototype for design review.\n"
            "It has no authentication, no encryption, and no audit logging.\n"
            "Set PROTOTYPE_ACK=1 to run it on loopback.\n")

    host = os.environ.get("HOST", "127.0.0.1")
    missing = security.unimplemented_controls()

    # The one hard stop: never listen off-box while the controls are stubs.
    if host != "127.0.0.1" and missing:
        sys.exit(
            f"\nRefusing to bind {host}.\n"
            f"{len(missing)} security controls are unimplemented: "
            f"{', '.join(missing)}.\n"
            "Binding a non-loopback interface would expose an endpoint that "
            "accepts veterans' medical records with no authentication, no "
            "encryption and no audit trail.\n"
            "Implement hosted/security.py first.\n")

    print(f"\n  Prototype shell on http://{host}:5001")
    print(f"  {len(missing)} unimplemented security controls — "
          f"record endpoints return HTTP 501.\n")
    app.run(host=host, port=int(os.environ.get("PORT", "5001")), debug=False)


if __name__ == "__main__":
    main()
