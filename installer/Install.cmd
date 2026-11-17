@echo off
setlocal
rem Starts the Student Workspace setup wizard. No PowerShell configuration is needed.
if not exist "%~dp0setup.ps1" goto :not_extracted
if not exist "%~dp0install.py" goto :not_extracted
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0setup.ps1" %*
set "SETUP_EXIT=%errorlevel%"
if not "%SETUP_EXIT%"=="0" pause
exit /b %SETUP_EXIT%

:not_extracted
echo The other setup files are not next to Install.cmd.
echo Extract the whole ZIP first: right-click Student-Tools-Setup.zip, choose Extract All,
echo then run Install.cmd from the extracted folder.
pause
exit /b 1
