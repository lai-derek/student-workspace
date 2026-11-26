# AGENTS.md: instructions for coding agents

Read this before changing anything in this repository.

## What this repository is

Student Workspace and its tools. The core package is the backbone of a private
student workspace: setup and updates, workspace state, the shared source
registry, knowledge snapshots, backup/restore/audit, a workspace-wide check,
tool registration, application handoffs, and the shared application-writing
skills. The tools (opportunity-discovery, academic-planning) depend on it and
join a workspace through their `student-workspace-tool.json`. The hard rules
below apply to the core; each tool's own rules add to them.

## Hard rules

1. **No model or LLM dependency, no telemetry.** The code is deterministic;
   the user's own agent does the AI work. Third-party packages are added only
   for a feature that needs them (the local app uses FastAPI and uvicorn).
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
8. **The local app listens only on 127.0.0.1**, and every request passes the
   checks in `web/security.py`: Host, session cookie, and for writes the Origin
   plus the `X-Student-Workspace` header. Don't add routes that bypass them.

## Where things live

One repository, separate installable packages. Each package keeps its own
`pyproject.toml`, tests and `student-workspace-tool.json`, and is zipped and
installed on its own. A package reaches another only through that package's
public functions, never its files or data. `packages/opportunity-discovery/`
has its own `AGENTS.md` with rules for that tool.

- `packages/student-workspace/` (the core):
  - `src/student_workspace/`: `state.py` (shared helpers), `workspace.py` (init),
    `sources.py` (registry), `tools.py` (registration, WORKSPACE.md blocks,
    pointers), `recovery.py`, `check.py`, `applications.py`,
    `application_checks.py`, `installer.py` (install/update core), `cli.py`.
  - `src/student_workspace/web/`: the local app (`serve` command): `app.py`
    (routes), `security.py` (request checks), `serve.py` (startup).
  - `installer/`: `Install.cmd`, `setup.ps1` (finds Python) and `install.py` (wizard).
  - `schemas/`, `skills/`, `docs/`, `tests/`.
- `packages/opportunity-discovery/`, `packages/academic-planning/`: the tools.
- `scripts/build_release.py`: zips each package from the release tag, writes `release.json` with their SHA-256 and `Student-Tools-Setup.zip`; its docstring has the publishing steps.
- `.github/workflows/ci.yml`: one CI run for all packages.

Before proposing a change, run each affected package's checks from its folder
(the core: `python -m pytest`, `ruff check .`, `ruff format --check .`, `mypy`;
the tools: as in `ci.yml`), and record results in that package's `VALIDATION.md`.
