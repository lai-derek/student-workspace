# Removes (or disables) the daily collection task created by register-task.ps1.
# Usage:
#   powershell -ExecutionPolicy Bypass -File scripts\unregister-task.ps1          # remove
#   powershell -ExecutionPolicy Bypass -File scripts\unregister-task.ps1 -Disable # disable only
param(
    [switch]$Disable,
    [string]$TaskName = "Student Workspace - Opportunity Discovery"
)
$ErrorActionPreference = "Stop"

if ($Disable) {
    Disable-ScheduledTask -TaskName $TaskName | Out-Null
    Write-Host "Task '$TaskName' disabled."
} else {
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
    Write-Host "Task '$TaskName' removed."
}
