@echo off
setlocal
rem Starts the Student Workspace setup wizard. No PowerShell configuration is needed.
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0setup.ps1" %*
set "SETUP_EXIT=%errorlevel%"
if not "%SETUP_EXIT%"=="0" pause
exit /b %SETUP_EXIT%
