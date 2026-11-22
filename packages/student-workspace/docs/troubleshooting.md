# Troubleshooting

**"The other setup files are not next to Install.cmd".** `Install.cmd` was
opened from inside the ZIP. Right-click `Student-Tools-Setup.zip`, choose
Extract All, and run `Install.cmd` from the extracted folder.

**Setup says Python 3.14 or newer is needed.** Install Python 3.15 from
python.org (or answer yes to the winget offer), then run `Install.cmd` again.

**Setup says this Python has no tkinter.** Run the Python installer again,
choose Modify, and enable "tcl/tk and IDLE".

**Windows warns about an unverified publisher.** Files downloaded from the
internet show this once; choose Run if you downloaded the ZIP from the
student-workspace Releases page.

**Setup stopped.** Read the message on the last page and
`.student-workspace/install.log`. The previous `tools/` folder is restored and
personal files are untouched. Close an open dashboard or a running collection
before updating, then run setup again.

**A tool's files are damaged or `tools\.venv` is missing.** Run `Install.cmd`
again on the same folder; when everything is current it reinstalls the same
versions. If `tools\.venv` still works, `.\tools\.venv\Scripts\student-workspace.exe update . --reinstall`
does the same from PowerShell.

**"tools/NAME is a Git checkout".** That tool was installed for development;
update it with Git and pip instead of setup.

**The folder is inside a Git folder.** Setup and `student-workspace audit` warn
about this because private files could be committed by accident. Choose a folder
outside Git unless you intend it; an audit error means private files are
actually tracked.

**`student-workspace check` says `stale`.** A tool needs a refresh, for
example collection hasn't run recently or generated files need rebuilding; the
output names the tool and what to run. `error` is a problem to fix first. (For
scripts: exit code 0 is current, 2 stale, 1 error.)

**Updating from PowerShell instead of the wizard.** From the workspace folder,
`.\tools\.venv\Scripts\student-workspace.exe update .` installs the latest
release, or says you're already current. Like the wizard, it backs up first;
setup keeps the three most recent of these backups in
`.student-workspace\backups\`.
