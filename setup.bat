@echo off
REM Convenience wrapper so a user can double-click setup instead of
REM discovering PowerShell's execution policy the hard way.
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0setup.ps1"
pause
