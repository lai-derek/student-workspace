# Validation

Version 0.1.1, checked 2026-11-17 on native Windows 11 with Python 3.15.2.

0.1.1 changes: `Install.cmd` explains how to extract the ZIP when it is run
without the other setup files; a tool's setup option is greyed out until the
tool is chosen; `update` does nothing when everything is already current (use
`--reinstall` to repair); setup keeps the three most recent automatic backups;
`snapshot list` says when there are none; the release script writes release
notes with a direct setup link.

| Check | Result |
| --- | --- |
| `python -m pytest` | 114 passed (includes real venv/pip installs and the Windows `Install.cmd` and `setup.ps1` checks) |
| `ruff check`, `ruff format --check`, `mypy` | clean |
| GitHub CI (0.1.0) | Windows 3.14 and 3.15, Ubuntu 3.15 passed |
| Published release 2026.11.0 (0.1.0 with Opportunity Discovery 0.2.1 and Academic Planning 0.3.0) | downloaded from GitHub into disposable folders: Student Workspace alone, with each tool, with both, and tools added one at a time to an existing workspace; checksums matched and `check` exited 0 each time; personal files unchanged; backup, restore, handoff and `update` commands from the docs worked |
| Visible wizard, clicked through by hand | 2026.11.0 with Academic Planning, and a local 0.1.1 test release with Opportunity Discovery: every page, install and Finished page with "Workspace check: current"; daily collection unchecked and greyed out until Opportunity Discovery is chosen |
| Local 0.1.1 test release (`build_release.py --local-archives`) | upgraded workspaces installed from 2026.11.0, and fresh installs of every combination: `check` exit 0, one summary line per tool; a repeat `update` reported "Already current"; three automatic backups kept |
| Backups | SQLite copied through the backup API (WAL contents included, sidecars excluded); restore drops stale journals; `tools/` excluded |

Not verified yet: Linux, and Python installation through winget on a computer
without Python (the prompt and refusal paths are tested with a stub).
