# Validation

## 0.2.0 in progress: one repository (checked 2026-11-20, native Windows 11, Python 3.15.2 and 3.14.10)

The core moved to `packages/student-workspace/`, and Opportunity Discovery
and Academic Planning were imported with their history into `packages/`.
Versions are now 0.2.0, 0.2.3 and 0.3.2; both tools require
`student-workspace>=0.2,<0.3`. One CI workflow tests all packages, and
`scripts/build_release.py` zips each package from the release tag.

| Check | Result |
| --- | --- |
| Core: `python -m pytest`; `ruff check`, `ruff format --check`, `mypy` (including `scripts/`) | 114 passed on 3.15 and 3.14; clean |
| Opportunity Discovery: `pytest -m "not live"`; ruff; mypy; `opdisc audit .` | 498 passed on 3.15 and 3.14; clean; audit 0 errors, 0 warnings |
| Academic Planning: `unittest discover` | 89 tests OK on 3.15 and 3.14 |
| Local test release (`build_release.py --local-archives`) | fresh install of all three from the new setup ZIP: `check` exit 0. Update of a workspace installed from the published 2026.11.1, run with its own 0.1.1 CLI: all three updated, backup taken, personal file kept, `check` exit 0, and a repeat `update` reported "Already current" |
| Published-mode archives (`git archive <ref>:packages/<name>`) | one top-level folder per ZIP, with the manifest at its root |

Fixed while checking: `test_installer.py` reused one archive path for two test
releases with the same core version, so the checksum of the first could go
stale when the second was written a second later. Each test release now has its
own folder.

Not verified yet: GitHub CI for the combined repository (nothing is pushed),
and the visible wizard clicked through by hand for 0.2.0.

## 0.1.1

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
