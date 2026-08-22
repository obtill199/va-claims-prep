"""
Contract tests between app/pipeline.py and app/server.py.

Written after a real failure: process_demo() was updated to return a third
value (the text corpus) but process_files() was not, so the demo path worked
and the real file-upload path raised
"ValueError: not enough values to unpack" -- after four minutes of OCR had
already run. Demo-only testing could not catch it, because the two entry
points had drifted apart.

These use a synthetic one-page PDF, so they run anywhere and need no real
records.
"""

import os
import sys
import tempfile

import pytest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)

fitz = pytest.importorskip("fitz")

from app import pipeline  # noqa: E402


@pytest.fixture
def tiny_pdf(tmp_path):
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 100), "Diagnosis: Test Condition")
    path = str(tmp_path / "tiny.pdf")
    doc.save(path)
    doc.close()
    return path


def test_process_files_returns_three_values(tiny_pdf, tmp_path):
    result = pipeline.process_files([tiny_pdf], str(tmp_path), run_ocr=False)
    assert len(result) == 3, (
        "server.upload() unpacks three values from process_files(); "
        "changing its arity breaks the real upload path")
    per_file, conditions, corpus = result
    assert isinstance(per_file, list)
    assert set(conditions) == {"clinical", "administrative"}
    assert isinstance(corpus, list)


def test_process_files_and_process_demo_agree(tiny_pdf, tmp_path):
    """Both entry points feed the same server code, so they must match."""
    from_files = pipeline.process_files([tiny_pdf], str(tmp_path), run_ocr=False)
    if not pipeline.demo_available():
        pytest.skip("demo record not generated on this machine")
    from_demo = pipeline.process_demo()
    assert len(from_files) == len(from_demo), (
        "process_files() and process_demo() must return the same shape")


def test_corpus_entries_are_text_and_offsets(tiny_pdf, tmp_path):
    _, _, corpus = pipeline.process_files([tiny_pdf], str(tmp_path), run_ocr=False)
    assert corpus, "corpus must not be empty -- find_record_prompts() needs it"
    text, page_starts = corpus[0]
    assert isinstance(text, str) and text
    assert isinstance(page_starts, list)


def test_no_text_layer_file_is_reported_not_skipped(tmp_path):
    """BUILD_BRIEF 3.1: a file that yields nothing must say so."""
    doc = fitz.open()
    doc.new_page()          # blank page, no text layer
    path = str(tmp_path / "blank.pdf")
    doc.save(path)
    doc.close()

    per_file, _, _ = pipeline.process_files([path], str(tmp_path), run_ocr=False)
    assert per_file[0]["diagnoses"] == 0
    assert per_file[0]["tier"] == "no-text-layer"
    assert "warning" in per_file[0], "silent zero-yield is the exact failure mode the brief forbids"
