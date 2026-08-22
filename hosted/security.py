#!/usr/bin/env python3
"""
hosted/security.py — the security seams, deliberately unimplemented.

This is the contract for the hosted prototype. Every function here is a
control point that a real deployment must implement before it touches one
real veteran's records. They are stubs, not TODO comments, so that the
places security belongs are part of the type-level structure of the app
rather than something to remember.

Each raises NotImplementedError by default. `app.py` refuses to start in any
mode other than local prototype unless every one of them has been replaced.
That is intentional: the failure mode for a half-secured PHI service should
be "won't boot", not "boots and leaks".

WHY THESE PARTICULAR CONTROLS
-----------------------------
The data here is 38 U.S.C. §5701 protected veteran information and, in
practice, PHI: full name, date of birth, SSN, DoD ID/EDIPI, complete
diagnosis history, treating clinicians, and duty limitations. That places a
hosted deployment under, at minimum:

  - HIPAA Security Rule (45 CFR §164.308-312) if operating as a covered
    entity or business associate -- access control, audit controls,
    integrity, transmission security.
  - FISMA / NIST SP 800-53 controls if operated for or connected to a
    federal agency; VA specifically applies VA Handbook 6500.
  - NIST SP 800-171 if handling CUI outside federal systems -- the records
    themselves are marked CUI (see the banner on DD 2807-1).
  - State breach-notification law for the operator's jurisdiction.

The mapping in each docstring is a starting point for whoever implements
this, not a compliance opinion.
"""

from __future__ import annotations


class SecurityNotImplemented(NotImplementedError):
    """Raised by every unimplemented control, so a partially-built
    deployment fails loudly rather than silently skipping a check."""


# ----------------------------------------------------------- identity

def authenticate(request):
    """Establish who is making this request. Return an opaque subject id.

    NIST 800-53 IA-2, IA-8; HIPAA §164.312(d).
    Considerations for whoever implements this:
      - Veterans authenticating to a VA-adjacent service will expect
        Login.gov or ID.me; both are the de facto federal CSPs and both
        support the IAL2 identity proofing this data arguably requires.
      - Session fixation, absolute and idle session timeouts.
      - MFA is not optional for IAL2/AAL2.
    """
    raise SecurityNotImplemented("authenticate() must be implemented")


def authorize(subject, job):
    """Confirm this subject may act on this job. Return None or raise.

    NIST 800-53 AC-3, AC-4; HIPAA §164.312(a)(1).
    The dominant risk here is IDOR: job identifiers must not be guessable,
    and ownership must be checked on every single access, not just at
    creation. A veteran retrieving another veteran's package is the worst
    outcome this system can produce.
    """
    raise SecurityNotImplemented("authorize() must be implemented")


# ------------------------------------------------------------ payload

def scan_upload(filename, data):
    """Validate and scan an uploaded file before anything parses it.

    NIST 800-53 SI-3, SI-10.
    At minimum: enforce a real content-type check rather than trusting the
    extension, cap size, and run AV. Note that this service's whole purpose
    is to feed uploaded bytes into PDF parsers -- pypdf, pdfplumber, PyMuPDF
    -- which are memory-unsafe attack surface reachable by unauthenticated
    input if authenticate() is ever bypassed. Parsing should be sandboxed
    and resource-limited.
    """
    raise SecurityNotImplemented("scan_upload() must be implemented")


def encrypt_at_rest(plaintext: bytes) -> bytes:
    """Encrypt before anything touches durable storage.

    NIST 800-53 SC-28; HIPAA §164.312(a)(2)(iv).
    Key management is the real work, not the cipher: use a KMS/HSM, keep
    keys out of the application and out of the repository, support rotation,
    and use per-record data keys so one compromise is not total.
    """
    raise SecurityNotImplemented("encrypt_at_rest() must be implemented")


def decrypt_at_rest(ciphertext: bytes) -> bytes:
    """Inverse of encrypt_at_rest()."""
    raise SecurityNotImplemented("decrypt_at_rest() must be implemented")


# ------------------------------------------------- accountability

def audit_log(event: str, subject=None, job_id=None, **fields):
    """Record a security-relevant event to append-only storage.

    NIST 800-53 AU-2, AU-9; HIPAA §164.312(b).
    Every access to record content is an auditable event. The log itself
    must not become a second copy of the PHI -- log identifiers and actions,
    never diagnoses, names, or file contents. Logs need their own retention
    policy and tamper protection.
    """
    raise SecurityNotImplemented("audit_log() must be implemented")


def enforce_retention(store):
    """Delete records past their retention window.

    NIST 800-53 SI-12, MP-6; HIPAA §164.310(d)(2)(i).
    The strongest control available to this system is simply not keeping
    the data. A hosted version should hold uploads only as long as the
    processing job runs, and destroy both inputs and outputs immediately
    afterward. Deletion must be real -- overwriting or crypto-shredding the
    data key -- not a database flag.
    """
    raise SecurityNotImplemented("enforce_retention() must be implemented")


IMPLEMENTED_MARKER = "__implemented__"


def unimplemented_controls():
    """Which controls are still stubs. app.py uses this as a start-up gate."""
    import inspect
    import sys

    out = []
    module = sys.modules[__name__]
    for name in ("authenticate", "authorize", "scan_upload", "encrypt_at_rest",
                 "decrypt_at_rest", "audit_log", "enforce_retention"):
        fn = getattr(module, name)
        if getattr(fn, IMPLEMENTED_MARKER, False):
            continue
        src = inspect.getsource(fn)
        if "SecurityNotImplemented" in src:
            out.append(name)
    return out
