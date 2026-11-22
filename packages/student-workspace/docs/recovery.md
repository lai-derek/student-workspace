# Backup and recovery

Commands run from PowerShell in your workspace folder:

```powershell
$workspace = (Get-Location).Path
$sw = ".\tools\.venv\Scripts\student-workspace.exe"
```

## Backup and restore

Stop the dashboard and other workspace-changing commands before backing up or restoring.

Create a full backup outside your workspace:

```powershell
$backupFolder = Join-Path (Split-Path $workspace -Parent) "Student-Workspace-Backups"
$backup = Join-Path $backupFolder ("workspace-" + (Get-Date -Format "yyyyMMdd-HHmmss") + ".zip")
& $sw backup $workspace $backup --kind full
```

A full backup preserves your workspace files, including skills and folders you add. The command creates the backup folder if needed.

Left out: `tools/` (setup reinstalls it), Git history, caches and temporary files, earlier backup ZIPs, and files linked from outside your workspace. Databases such as the collector's are copied safely even while a tool is running.

For a smaller backup, use `--kind state`. It keeps instructions, skills, knowledge, applications, `.student-workspace/` (board state, history, collector data) and the folders tools declare as theirs. It omits `inbox/`, `sources/`, and other custom folders.

Backups are **unencrypted ZIP files containing private information**. Store them accordingly and use a new filename for each backup.

On a new computer or after removing your workspace, run the Student Workspace setup first, choosing the same tools. Then run the PowerShell setup at the top of this page with the workspace you want to restore.

Choose the backup ZIP and restore:

```powershell
$backup = Read-Host "Full path to the workspace backup ZIP"
& $sw restore $workspace $backup
```

Restore checks the archive and creates a full backup of your current workspace before replacing matching files. It leaves unrelated files in place and reports the pre-restore backup path. It is not an exact rollback that deletes newer files.

## Recover generated knowledge

Tools save snapshots (for example, opportunity review imports and feedback) of the generated knowledge files they change. These are not backups of everything an agent edits; use a full workspace backup for that.

```powershell
& $sw snapshot list $workspace
```

Choose a snapshot ID from the output, compare it, and restore only if it contains the version you want:

```powershell
$snapshot = Read-Host "Snapshot ID"
& $sw snapshot compare $workspace $snapshot
```

After inspecting the comparison:

```powershell
& $sw snapshot restore $workspace $snapshot
```

Restore saves the current generated knowledge first. Retention keeps the latest daily snapshot for 30 days and one per older month.

