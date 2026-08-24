# Copyright (c) 2026 Oliver Tillinghast.
# Licensed under the PolyForm Noncommercial License 1.0.0.
# Free for veterans, VSOs, nonprofits and government. Commercial use
# requires a separate licence -- see LICENSE, NOTICE.md, COMMERCIAL.md.
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


def test_corpus_entries_carry_text_offsets_and_provenance(tiny_pdf, tmp_path):
    """find_record_prompts() needs the text, the page offsets, and where it
    came from -- the last so an OCR-derived proposal can say so rather than
    passing itself off as a structured read."""
    _, _, corpus = pipeline.process_files([tiny_pdf], str(tmp_path), run_ocr=False)
    assert corpus, "corpus must not be empty -- find_record_prompts() needs it"
    entry = corpus[0]
    assert set(entry) >= {"text", "page_starts", "source_document", "method"}
    assert isinstance(entry["text"], str) and entry["text"]
    assert isinstance(entry["page_starts"], list)
    assert entry["method"] in ("structured", "ocr")


def test_demo_mode_is_gone():
    """Demo mode was removed deliberately: only real records go in. If it
    comes back, it needs a sample record shipped with the repo again."""
    assert not hasattr(pipeline, "process_demo")
    assert not hasattr(pipeline, "demo_available")


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
