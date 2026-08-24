# Copyright (c) 2026 Oliver Tillinghast.
# Licensed under the PolyForm Noncommercial License 1.0.0.
# Free for veterans, VSOs, nonprofits and government. Commercial use
# requires a separate licence -- see LICENSE, NOTICE.md, COMMERCIAL.md.
"""
The hosted prototype must not be able to accept a record.

This is the one place in the project where a mistake would put real
veterans' medical records on a server with no authentication, no encryption
and no audit trail. The guard is therefore tested rather than trusted.
"""

import os
import sys

import pytest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)

pytest.importorskip("flask")

from hosted import security  # noqa: E402
from hosted.app import app  # noqa: E402


def test_all_controls_are_still_stubs():
    """If a control gets implemented, this test should be updated
    deliberately -- not discovered by a record leaking."""
    assert set(security.unimplemented_controls()) == {
        "authenticate", "authorize", "scan_upload", "encrypt_at_rest",
        "decrypt_at_rest", "audit_log", "enforce_retention"}


def test_every_stub_raises_rather_than_passing():
    for name in security.unimplemented_controls():
        with pytest.raises(NotImplementedError):
            getattr(security, name)(*([None] * 2)[:_arity(name)])


def _arity(name):
    return {"authenticate": 1, "authorize": 2, "scan_upload": 2,
            "encrypt_at_rest": 1, "decrypt_at_rest": 1, "audit_log": 1,
            "enforce_retention": 1}[name]


def test_upload_endpoint_refuses_records():
    client = app.test_client()
    r = client.post("/api/jobs", data={
        "records": (open(__file__, "rb"), "notarecord.pdf")},
        content_type="multipart/form-data")
    assert r.status_code == 501, "prototype must never accept a record"
    assert r.get_json()["error"] == "security controls not implemented"


def test_health_reports_it_cannot_accept_records():
    r = app.test_client().get("/api/health")
    body = r.get_json()
    assert body["accepts_records"] is False
    assert body["unimplemented_controls"]


def test_nothing_is_persisted_to_disk():
    """The prototype holds jobs in memory only. If durable storage is ever
    added it must go through encrypt_at_rest() and enforce_retention()."""
    import hosted.app as happ
    assert isinstance(happ.JOBS, dict)
    assert happ.JOBS == {}, "no job should survive between runs"
