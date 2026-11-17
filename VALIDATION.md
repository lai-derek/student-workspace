# Validation

Version 0.1.0, checked 2026-11-16 on native Windows 11 with Python 3.15.2.

| Check | Result |
| --- | --- |
| `python -m pytest` | 112 passed (includes real venv/pip installs) |
| `ruff check`, `ruff format --check`, `mypy` | clean |
| Wizard pages | every page driven in a hidden Tk window: required tool locked, Git warning, options, summary for new and existing workspaces, finish and error states |
| Install core | fresh install with a tool option; adding a tool; update with personal files byte-identical; rollback of `tools/` and generated files after an induced setup failure; Git-checkout tool folders refused; missing, wrong or invalid SHA-256 and unsafe archives rejected |
| `setup.ps1` | finds Python 3.14+; with no Python and no winget prints install guidance; with winget asks first, installs nothing on "no", runs winget only after "yes"; rejects Python 3.12; `Install.cmd` bypasses execution policy |
| Local test release of all three tools (`build_release.py --local-archives`) | installed Opportunity Discovery alone, Academic Planning alone, and both into disposable folders: `check` exit 0 each time; dashboard served; academic build then check current; adding Academic Planning to an existing workspace kept personal files byte-identical and made a pre-update backup |
| Backups | SQLite copied through the backup API (WAL contents included, sidecars excluded); restore drops stale journals; `tools/` excluded |

Not verified yet: clicking through the visible wizard by hand, Linux, GitHub CI,
and installing from a published release (tags and release assets do not exist
until publication).
