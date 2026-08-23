# setup.ps1 — one-time setup on Windows.
#
# Creates a local Python environment and installs dependencies. Nothing here
# contacts a server with your records.
#
# If Windows blocks this script, it is because PowerShell's default policy
# refuses unsigned scripts. Run it this way instead, which allows it for
# this one command only:
#
#     powershell -ExecutionPolicy Bypass -File .\setup.ps1

$ErrorActionPreference = "Stop"
Set-Location -Path $PSScriptRoot

function Find-Python {
    foreach ($candidate in @("py -3", "python", "python3")) {
        $parts = $candidate.Split(" ")
        $exe = $parts[0]
        $args = if ($parts.Length -gt 1) { $parts[1..($parts.Length-1)] } else { @() }
        try {
            $version = & $exe @args --version 2>&1
            if ($LASTEXITCODE -eq 0) { return ,@($exe, $args) }
        } catch { }
    }
    return $null
}

$python = Find-Python
if ($null -eq $python) {
    Write-Host ""
    Write-Host "Python 3 was not found." -ForegroundColor Red
    Write-Host "Install it from https://www.python.org/downloads/ and tick"
    Write-Host "'Add python.exe to PATH' during installation, then run this again."
    exit 1
}
$exe  = $python[0]
$pre  = $python[1]

Write-Host "Creating a local Python environment..."
& $exe @pre -m venv .venv

$venvPy = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $venvPy)) {
    Write-Host "Could not create the environment at .venv" -ForegroundColor Red
    exit 1
}

& $venvPy -m pip install --quiet --upgrade pip
Write-Host "Installing dependencies (this takes a minute)..."
& $venvPy -m pip install --quiet --prefer-binary `
    flask pypdf pymupdf pdfplumber python-docx pytest

Write-Host "Installing Windows OCR support..."
# winsdk exposes Windows.Media.Ocr, the OCR engine already built into
# Windows 10 and 11. Nothing else to install; it uses the language packs
# already on the machine.
& $venvPy -m pip install --quiet winsdk
if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "  winsdk did not install. Everything else works; scanned" -ForegroundColor Yellow
    Write-Host "  records will report that they could not be read." -ForegroundColor Yellow
}

Write-Host ""
Write-Host "Done. Start the app with:   .\run_app.bat"
Write-Host "Then open:                  http://127.0.0.1:5000"
