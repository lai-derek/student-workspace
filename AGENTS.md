# AGENTS.md: instructions for coding agents

Read this before changing anything in this repository.

## What this repository is

The backbone of a private student workspace: setup and updates, workspace
state, the shared source registry, knowledge snapshots, backup/restore/audit, a
workspace-wide check, tool registration, application handoffs, and the shared
application-writing skills. Tools such as opportunity-discovery and
academic-planning depend on it and join a workspace through their
`student-workspace-tool.json`.

## Hard rules

1. **No model or LLM dependency, no telemetry.** Everything is deterministic
   standard-library Python; the user's own agent does the AI work.
2. **No personal data in this repository.** Skills, fixtures and examples are
   synthetic or generic. Private state lives only in a user-selected workspace.
3. **Updates never touch personal files.** The installer changes only
   `tools/`, backs up the workspace first, and restores the previous `tools/`
   on failure. It refuses to replace a tool folder that is a Git checkout.
4. **`src/student_workspace/installer.py` stays standard-library only and
   imports nothing from this package**: the wizard loads it before anything is
   installed.
5. **Never overwrite user-owned files.** Generated WORKSPACE.md blocks and skill
   pointers are rewritten only when setup created them; text outside the blocks
   and files setup did not write are left alone.
6. **Windows is the primary platform.** Use `pathlib`, `os.replace` for atomic
   writes, and forward slashes in any path written to JSON. WSL/Linux results
   do not verify Windows behavior.
7. **No submissions or authenticated automation.** Application handoffs prepare
   files for the user; nothing is submitted, sent or uploaded.

## Where things live

- `src/student_workspace/`: `state.py` (shared helpers), `workspace.py` (init),
  `sources.py` (registry), `tools.py` (registration, WORKSPACE.md blocks,
  pointers), `recovery.py`, `check.py`, `applications.py`,
  `application_checks.py`, `installer.py` (install/update core), `cli.py`.
- `installer/`: `Install.cmd`, `setup.ps1` (finds Python) and `install.py` (wizard).
- `scripts/build_release.py`: builds the tool ZIPs from version tags, `release.json` with their SHA-256 and `Student-Tools-Setup.zip`; its docstring has the publishing steps.
- `schemas/`, `skills/`, `docs/`, `tests/`.

Run `python -m pytest`, `ruff check .`, `ruff format --check .` and `mypy`
before proposing a change, and record results in `VALIDATION.md`.
