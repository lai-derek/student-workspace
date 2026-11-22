param(
    [Parameter(Mandatory = $true)]
    [string]$WorkspacePath
)

# Scheduled-run entry point for opportunity-discovery in a student workspace.
# The Task Scheduler task executes ONLY this script. It never modifies
# source rules, code, weights, or configuration.
$ErrorActionPreference = "Continue"

$workspace = (Resolve-Path -LiteralPath $WorkspacePath).Path
$opdisc = Join-Path $workspace "tools\.venv\Scripts\opdisc.exe"
$logsDir = Join-Path $workspace ".student-workspace\opportunity-discovery\logs"
New-Item -ItemType Directory -Force -Path $logsDir | Out-Null
$log = Join-Path $logsDir ("run-" + (Get-Date -Format "yyyyMMdd") + ".log")

Add-Content -Path $log -Value ("=== run start " + (Get-Date -Format o) + " ===")
& $opdisc --quiet --workspace $workspace run *>> $log
$code = $LASTEXITCODE
Add-Content -Path $log -Value ("=== run end " + (Get-Date -Format o) + " exit=$code ===")

# Retain ~14 days of logs
Get-ChildItem -Path $logsDir -Filter "run-*.log" |
    Where-Object { $_.LastWriteTime -lt (Get-Date).AddDays(-14) } |
    Remove-Item -ErrorAction SilentlyContinue

exit $code
