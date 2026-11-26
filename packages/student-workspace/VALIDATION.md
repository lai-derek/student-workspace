# Validation

## 0.2.0 in progress: Phase 1 PR (checked 2026-11-25, native Windows 11, Python 3.15.2)

The reader walkthrough covered the released setup, running Studio from source,
starting a resume, exporting it, and finding the update and recovery guides.

- Fresh editable install and `serve` in a disposable workspace served the app
  through its launch link. A blank resume previewed, exported and passed
  `resume verify`.
- Frontend clean install, type check, Vitest (9 passed) and production build
  passed. Ruff lint, Ruff format and mypy passed for the core, along with the
  release-script Ruff checks.
- Core pytest passed 177 tests in the full run. The missing-interface test
  still expected the old wording. After it was updated to check the two recovery
  instructions, all 18 server tests passed on rerun.
- Opportunity Discovery's Windows CI checks passed. Academic Planning passed
  all 89 tests.
- The local release build included the Studio assets, templates, migrations
  and updated installer. The archive checksums matched the manifest.
- Public-repo readiness and reader-experience reviews checked the proposed
  files for private or generated material and verified the linked reader path.

## 0.2.0 in progress: Application Studio (checked 2026-11-22, native Windows 11, Python 3.15.2 and 3.14.10)

The local app (`serve`, or `Open Student Workspace.cmd`) now has a React
interface and the resume studio: resumes stored in SQLite, typeset with Typst
in three templates, edited directly with a live, clickable preview, exported as
`.typ` + `.pdf`, with screening checks and file-based agent handoffs.

| Check | Result |
| --- | --- |
| Core `python -m pytest` | 177 passed on 3.15 and 3.14 (studio store, rendering, export, import, checks, handoff, API, server). One warning: Starlette deprecates `httpx` for its test client |
| Opportunity Discovery, Academic Planning | 498 passed, 89 OK on both versions |
| `ruff check`, `ruff format --check`, `mypy` (core and `scripts/`) | clean |
| Front end: `tsc`, Vitest, `vite build` | clean; 8 tests passed; built into the core package |
| Benchmark (`scripts/benchmark_studio.py`, see [docs/benchmarks.md](../../docs/benchmarks.md)) | 15 structural edits, 0 AI turns, about 21–27 ms per edit including the new preview; exported PDF reproduced byte for byte from its source; parse check ok; flat time and memory over 300 edits |
| Real resume (a one-page LaTeX resume, in a scratch workspace) | imported with all 442 words intact; one page; export verified |
| Browser (built-in, Windows) | sign-in link, Home, studio; double-click a bullet on the PDF, edit, Enter: preview updated in 18 ms; screening checks; "edited since export" badge; tablet width without sideways scrolling |
| Local test release (`build_release.py --local-archives`, with `npm ci` and the build) | core ZIP contains the interface, templates and migrations. Fresh install from the new setup ZIP and an update of a published 2026.11.1 workspace with its own CLI: `check` exit 0, launcher created, the installed app served the interface, imported, previewed, exported, and `resume verify` matched |
| Backup | includes `studio.sqlite3`; integrity ok |

Not verified yet: GitHub CI for these changes, Linux, the wizard's new "Open
Student Workspace" button clicked by hand, and the handoff round trip with
a real agent (tested with a simulated agent response).

## 0.2.0 in progress: local app server (checked 2026-11-22, native Windows 11, Python 3.15.2 and 3.14.10)

`student-workspace serve` starts a FastAPI server on 127.0.0.1 with Host,
session-cookie and Origin checks; `/api/sections` and `/api/workspace` are the
first routes. The React interface is not built yet.

| Check | Result |
| --- | --- |
| `python -m pytest` | 132 passed on 3.15 and 3.14 (18 new server tests). One warning: Starlette deprecates `httpx` for its test client |
| `ruff check`, `ruff format --check`, `mypy` | clean |
| Real run (`serve --no-browser --port 8766` on a workspace with both tools) | without the cookie 401; launch link 303 to `/`; sections listed all five; `/api/workspace` reported all three tools ok in 1.9 s; a spoofed Host got 400 |
| Dependency wheels | fastapi 0.165, starlette 1.10, pydantic 2.14 (`pydantic-core` has cp314 and cp315 Windows wheels), uvicorn 0.54; nothing compiles at install |

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
