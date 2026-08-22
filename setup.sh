#!/usr/bin/env bash
# One-time setup. Creates a local Python environment and installs
# dependencies. Nothing here contacts a server with your records.
set -e
cd "$(dirname "$0")"

echo "Creating a local Python environment..."
python3 -m venv .venv
.venv/bin/pip install --quiet --upgrade pip
echo "Installing dependencies (this takes a minute)..."
.venv/bin/pip install --quiet --prefer-binary \
  flask pypdf pymupdf pdfplumber python-docx pytest

if [[ "$(uname)" == "Darwin" ]]; then
  echo "Installing macOS OCR support..."
  .venv/bin/pip install --quiet pyobjc-framework-Vision pyobjc-framework-Quartz
else
  echo "Note: OCR of scanned records currently requires macOS. Everything"
  echo "      else works; scanned files will simply report that they could"
  echo "      not be read."
fi

echo
echo "Done. Start the app with:   ./run_app.sh"
echo "Then open:                  http://127.0.0.1:5000"
