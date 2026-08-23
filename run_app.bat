@echo off
REM Launch the local VA Claims Prep app on Windows.
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
  echo.
  echo Setup has not been run yet.
  echo Run this first:  powershell -ExecutionPolicy Bypass -File .\setup.ps1
  echo.
  pause
  exit /b 1
)

echo Starting VA Claims Prep...
echo Your records are processed on this computer and are never uploaded.
echo.
start "" http://127.0.0.1:5000
".venv\Scripts\python.exe" -m app.server
pause
