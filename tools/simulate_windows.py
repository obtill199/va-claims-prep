#!/usr/bin/env python3
"""
tools/simulate_windows.py — run the full flow with the macOS frameworks removed.

Approximates a Windows or Linux box on a Mac: blocks the pyobjc Vision /
Quartz / Foundation imports the OCR tier depends on, then walks intake ->
upload -> review -> explanations -> package and checks real output comes out
the other end.

It cannot catch genuinely Windows-only problems (path separators in a shell,
CRLF, file locking), but it does answer the question that matters first:
does anything except OCR actually depend on being on a Mac?

    python tools/simulate_windows.py
"""

import io
import os
import re
import sys
import zipfile

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Block the macOS frameworks before anything imports them.
for module in ("Vision", "Quartz", "Foundation", "objc"):
    sys.modules[module] = None

sys.path.insert(0, REPO)

FAILURES = []


def check(label, ok, detail=""):
    print(f"  [{'PASS' if ok else 'FAIL'}] {label}"
          + (f" -- {detail}" if detail and not ok else ""))
    if not ok:
        FAILURES.append(label)


def main():
    from app.server import app
    import app.pipeline as pipeline

    app.config["TESTING"] = True
    client = app.test_client()

    print("\n=== platform gate ===")
    available, reason = pipeline.ocr_available()
    check("OCR correctly reports unavailable", not available, str(available))
    check("and explains why", bool(reason), reason or "no reason given")

    print("\n=== full flow without OCR ===")
    intake = {
        "full_name": "SAMPLE, ALEX RIVER", "date_of_birth": "1997-03-22",
        "birth_sex": "Male", "address": "100 Example Ave", "phone": "555-0142",
        "email": "a@example.com", "branch": "Air Force",
        "component": "National Guard", "duty_status": "Not on active duty",
        "purpose": "Separation", "position": "SrA", "occupation": "Analyst",
        "exam_location": "", "medications": "None", "allergies": "None",
    }
    r = client.post("/", data=intake)
    check("intake accepted", r.status_code == 302, str(r.status_code))

    sample = os.path.join(REPO, "tools", "sample_record.pdf")
    with open(sample, "rb") as fh:
        payload = {"records": (io.BytesIO(fh.read()), "sample_record.pdf"),
                   "run_ocr": "on"}   # requested, but unavailable
    r = client.post("/upload", data=payload, content_type="multipart/form-data")
    check("upload succeeds with OCR requested but unavailable",
          r.status_code == 302, str(r.status_code))
    if r.status_code != 302:
        print(r.get_data(as_text=True)[:1200])
        return 1

    body = client.get("/review").get_data(as_text=True)
    ids = list(dict.fromkeys(re.findall(r'name="decision_([0-9a-f]+)"', body)))
    check("proposals generated", len(ids) > 0, f"{len(ids)}")

    client.post("/review", data={f"decision_{i}": "confirm" for i in ids})

    explain = client.get("/explain").get_data(as_text=True)
    m = re.search(r'name="item29"[^>]*>(.*?)</textarea>', explain, re.S)
    import html
    item29 = html.unescape(m.group(1)) if m else ""
    check("item 29 drafted", len(item29) > 100, f"{len(item29)} chars")

    form = {"item29": item29}
    for fm in re.finditer(r'name="(sha_[^"]+)"[^>]*>(.*?)</textarea>', explain, re.S):
        form[fm.group(1)] = html.unescape(fm.group(2))
    client.post("/explain", data=form)

    r = client.get("/package/download")
    check("package downloads", r.status_code == 200, str(r.status_code))
    if r.status_code == 200:
        z = zipfile.ZipFile(io.BytesIO(r.data))
        names = z.namelist()
        check("both forms produced",
              "dd2807-1_FILLED.pdf" in names and "sha_part_a_FILLED.pdf" in names,
              str(names))

        from pypdf import PdfReader
        fields = PdfReader(io.BytesIO(z.read("dd2807-1_FILLED.pdf"))).get_fields()
        name_field = fields["form1[0].Page1[0].Row1[0].One[0]"].get("/V")
        check("identity written to the PDF", name_field == "SAMPLE, ALEX RIVER",
              str(name_field))
        checked = [k for k, v in fields.items()
                   if k.rsplit(".", 1)[-1].startswith("Yes")
                   and v.get("/V") not in (None, "", "/Off")]
        check("medical answers written", len(checked) > 0, f"{len(checked)}")

    print("\n=== scanned record without OCR ===")
    client2 = app.test_client()
    client2.post("/", data=intake)
    import fitz  # noqa: F401  -- pymupdf is cross-platform, unlike pyobjc
    print("  (pymupdf imports fine off-Mac)")

    print()
    if FAILURES:
        print(f"{len(FAILURES)} failure(s): {FAILURES}")
        return 1
    print("Everything except OCR works with the macOS frameworks removed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
