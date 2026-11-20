param(
    [Parameter(Mandatory = $true)]
    [string]$WorkspacePath,
    [string]$TaskName = "Student Workspace - Opportunity Discovery"
)

# Registers a daily Task Scheduler task that runs scripts\run.ps1 for one workspace.
# Setup runs this only when the user chooses daily collection.
$ErrorActionPreference = "Stop"

$scriptPath = Join-Path $PSScriptRoot "run.ps1"
$workspace = (Resolve-Path -LiteralPath $WorkspacePath).Path
if (-not (Test-Path -LiteralPath $scriptPath)) { throw "missing $scriptPath" }

$action = New-ScheduledTaskAction `
    -Execute "powershell.exe" `
    -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$scriptPath`" -WorkspacePath `"$workspace`"" `
    -WorkingDirectory $workspace
$trigger = New-ScheduledTaskTrigger -Daily -At 07:30
$settings = New-ScheduledTaskSettingsSet `
    -StartWhenAvailable `
    -MultipleInstances IgnoreNew `
    -ExecutionTimeLimit (New-TimeSpan -Hours 2)

Register-ScheduledTask -TaskName $TaskName `
    -Action $action -Trigger $trigger -Settings $settings -Force `
    -Description "opportunity-discovery daily collection for $workspace" | Out-Null

Write-Host "Task '$TaskName' registered (daily 07:30)."
Write-Host "Remove or disable it with scripts\unregister-task.ps1."
