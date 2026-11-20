# Collection on Windows

Opportunity Discovery is installed with Student Workspace: download
[Student-Tools-Setup.zip](https://github.com/lai-derek/student-workspace/releases/latest/download/Student-Tools-Setup.zip),
extract it, run `Install.cmd` and choose Opportunity Discovery. Running setup
again adds tools or updates them; it backs up the workspace first and changes
only `tools/`.

Collector data lives in your workspace, not in the tool folder:

| Path | Contents |
| --- | --- |
| `.student-workspace/opportunity-discovery/data/` | SQLite database and fetch cache |
| `.student-workspace/opportunity-discovery/output/` | exports, `source_health.json`, `run_summary.json` |
| `.student-workspace/opportunity-discovery/logs/` | scheduled-run logs |

The collector configuration (`config/default.toml`) and source registry
(`config/sources.toml`) belong to the release in `tools/opportunity-discovery/`
and are replaced on update. Propose source changes to the repository instead of
editing the installed copy.

## Run collection

From the workspace folder in PowerShell:

```powershell
.\tools\.venv\Scripts\opdisc.exe --workspace . run
```

The first run checks every source and takes about 10 minutes; later runs reuse
cached responses and are faster. It ends with a one-line summary of sources
checked and leads found. A source that succeeded recently isn't checked again
until it's due, so running collection twice in a row mostly retries sources
that failed last time.

## Daily collection

Setup offers a daily 7:30 a.m. Task Scheduler task (off unless you check it). It runs only
`scripts\run.ps1` for that workspace: collection, not AI review, and it never
changes code, source rules or configuration. To add it later or remove it:

```powershell
powershell -ExecutionPolicy Bypass -File .\tools\opportunity-discovery\scripts\register-task.ps1 -WorkspacePath .
powershell -ExecutionPolicy Bypass -File .\tools\opportunity-discovery\scripts\unregister-task.ps1
```

The task is named `Student Workspace - Opportunity Discovery`; registering again
replaces it, so one computer collects for one workspace at a time.

`.\tools\.venv\Scripts\opdisc.exe check .` (also part of
`student-workspace check`) reports collection as stale after three days without
a new export. For failed runs, check the newest `logs\run-YYYYMMDD.log` and
`output\source_health.json` under `.student-workspace\opportunity-discovery\`. Some sources can
fail while a run still succeeds; their earlier results are retained. See
[Troubleshooting](TROUBLESHOOTING.md) for common errors and
[Private workspace operations](PRIVATE_WORKSPACE_OPERATIONS.md) for review commands.
