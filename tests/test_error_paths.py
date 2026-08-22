"""
Failure paths found by an adversarial end-to-end pass.

All three were 500s or silent bounces reachable by ordinary user behaviour:
refreshing a download URL, picking the wrong file, or uploading a record
that happens to contain no coded diagnoses.
"""

import io
import os
import sys

import pytest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)

pytest.importorskip("flask")
fitz = pytest.importorskip("fitz")

from app.server import app  # noqa: E402

INTAKE = {
    "full_name": "SAMPLE, ALEX RIVER", "branch": "Air Force",
    "component": "National Guard", "purpose": "Separation",
    "birth_sex": "Male", "date_of_birth": "1997-03-22",
    "address": "100 Example Ave", "phone": "555-0142",
    "email": "a@example.com", "duty_status": "Not on active duty",
    "position": "SrA", "occupation": "Analyst", "exam_location": "",
    "medications": "None", "allergies": "None",
}


@pytest.fixture
def client():
    app.config["TESTING"] = True
    return app.test_client()


@pytest.fixture
def blank_pdf(tmp_path):
    doc = fitz.open()
    doc.new_page().insert_text((72, 100), "Nothing clinical here.")
    p = str(tmp_path / "nothing.pdf")
    doc.save(p)
    doc.close()
    return p


def test_download_without_a_session_redirects_not_500(client):
    """A bookmarked or refreshed download URL used to dereference
    state['conditions'] while it was None and return a stack trace."""
    r = client.get("/package/download")
    assert r.status_code != 500
    assert r.status_code in (302, 200)


def test_unreadable_file_is_reported_not_fatal(client):
    """Picking the wrong file is an ordinary user event. It must not lose
    the whole run."""
    client.post("/", data=INTAKE)
    r = client.post("/upload", data={
        "records": (io.BytesIO(b"this is not a pdf"), "wrong.pdf")},
        content_type="multipart/form-data")
    assert r.status_code != 500

    body = client.get("/review").get_data(as_text=True)
    assert "could not be opened as a PDF" in body, \
        "the member must be told which file failed and why"


def test_one_bad_file_does_not_sink_the_good_one(client, blank_pdf):
    client.post("/", data=INTAKE)
    r = client.post("/upload", data={"records": [
        (io.BytesIO(b"garbage"), "bad.pdf"),
        (open(blank_pdf, "rb"), "good.pdf"),
    ]}, content_type="multipart/form-data")
    assert r.status_code != 500
    body = client.get("/review").get_data(as_text=True)
    assert "bad.pdf" in body and "good.pdf" in body


def test_zero_condition_record_still_reaches_review(client, blank_pdf):
    """Silently bouncing back to the upload page reads as 'your upload
    failed' -- the silent-failure mode BUILD_BRIEF 3.1 forbids."""
    client.post("/", data=INTAKE)
    client.post("/upload", data={"records": (open(blank_pdf, "rb"), "nothing.pdf")},
                content_type="multipart/form-data")
    r = client.get("/review")
    assert r.status_code == 200, "must not redirect away without explanation"
    body = r.get_data(as_text=True)
    assert "No answers could be proposed" in body
    assert "What was read from your files" in body


def test_zero_condition_record_still_produces_usable_forms(client, blank_pdf):
    """Even with nothing extracted, the intake answers are worth having."""
    client.post("/", data=INTAKE)
    client.post("/upload", data={"records": (open(blank_pdf, "rb"), "nothing.pdf")},
                content_type="multipart/form-data")
    client.post("/review", data={})
    client.post("/explain", data={"item29": ""})
    r = client.get("/package/download")
    assert r.status_code == 200

    import zipfile
    from pypdf import PdfReader
    z = zipfile.ZipFile(io.BytesIO(r.data))
    f = PdfReader(io.BytesIO(z.read("dd2807-1_FILLED.pdf"))).get_fields()
    assert f["form1[0].Page1[0].Row1[0].One[0]"].get("/V") == "SAMPLE, ALEX RIVER"
    checked = [k for k, v in f.items()
               if k.rsplit(".", 1)[-1].startswith("Yes")
               and v.get("/V") not in (None, "", "/Off")]
    assert not checked, "nothing was confirmed, so no medical box may be set"


def test_unknown_proposal_id_is_ignored(client, blank_pdf):
    client.post("/", data=INTAKE)
    client.post("/upload", data={"records": (open(blank_pdf, "rb"), "n.pdf")},
                content_type="multipart/form-data")
    r = client.post("/review", data={"decision_deadbeef": "confirm"})
    assert r.status_code != 500
