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
  echo "Note: OCR of scanned records needs Tesseract on this platform."
  echo "      Install it, then re-run this script:"
  echo "        Debian/Ubuntu:  sudo apt install tesseract-ocr"
  echo "        Fedora:         sudo dnf install tesseract"
  echo "      Everything else works without it; scanned files will report"
  echo "      that they could not be read rather than silently yielding"
  echo "      nothing."
  if command -v tesseract >/dev/null 2>&1; then
    echo "Tesseract found - installing the Python bindings..."
    .venv/bin/pip install --quiet pytesseract pillow
  fi
fi

echo
echo "Done. Start the app with:   ./run_app.sh"
echo "Then open:                  http://127.0.0.1:5000"
