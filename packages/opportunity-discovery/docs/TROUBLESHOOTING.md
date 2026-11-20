# Troubleshooting

## Installation

Setup problems (Python, the wizard, updates) are covered in the
[Student Workspace troubleshooting notes](https://github.com/lai-derek/student-workspace/blob/main/docs/troubleshooting.md).
Setup keeps a log in `.student-workspace/install.log`.

## Running and viewing results

**Open Dashboard.cmd reports an error.** Keep the window open to read it. If
the dashboard is missing, run the Student Workspace setup again for this workspace.
If port 8765 is already in use, close the earlier dashboard window.

**Your AI cannot read files or run commands.** Open the workspace as a project
in a tool with local file access and command execution. Opportunity review also
needs web access. You can still open the dashboard and search collected leads
in Explore.

**`opdisc` is not recognized.** From the workspace folder, use `.\tools\.venv\Scripts\opdisc.exe` (or run setup again if `tools\.venv` is missing).

**The dashboard says no leads are collected yet.** Collection hasn't run in this workspace. Ask your AI to create your first board, or run `.\tools\.venv\Scripts\opdisc.exe --workspace . run` (about 10 minutes the first time), then reload the page.

**Dashboard Home is empty.** Home needs imported review decisions. Check **Explore** for the current public queue. If Explore says its export is unavailable, run `.\tools\.venv\Scripts\opdisc.exe --workspace . run` and check `.student-workspace\opportunity-discovery\output\source_health.json`.

**A scheduled run failed.** Check the newest `.student-workspace\opportunity-discovery\logs\run-YYYYMMDD.log` and `output\source_health.json` beside it. Result code `1` means every source the run tried failed and none is still current from a recent successful check (for example, no internet connection); `2` means a configuration or workflow error; `3` means another run is active. A partial source failure can still return `0`; check the health file for details.

**`another run appears active`.** Confirm no collection process is running before removing `.student-workspace\opportunity-discovery\data\run.lock`. A stale lock normally clears itself after a crashed process exits.

**`unrecognized arguments: --quiet` or `--json`.** Put these options before the command: `.\tools\.venv\Scripts\opdisc.exe --quiet --workspace . run` or `.\tools\.venv\Scripts\opdisc.exe --json --workspace . source-health`.

For a source whose format or rate limit has changed, see [adapter and source diagnostics](ADAPTERS.md).
