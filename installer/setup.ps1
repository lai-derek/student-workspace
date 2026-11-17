param(
    [switch]$ProbeOnly,
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$WizardArgs
)

# Finds Python 3.14 or newer (3.15 preferred) and starts the setup wizard.
# Installing Python is offered only after an explicit yes.
$ErrorActionPreference = "Stop"

function Test-Python {
    param([string]$Exe, [string[]]$LauncherArgs, [string]$Code)
    try {
        & $Exe @LauncherArgs -c $Code 2>$null | Out-Null
        return ($LASTEXITCODE -eq 0)
    }
    catch {
        return $false
    }
}

function Find-Python {
    $versionCheck = "import sys; raise SystemExit(0 if sys.version_info >= (3, 14) else 1)"
    $candidates = @()
    $launchers = @()
    $onPath = Get-Command py.exe -ErrorAction SilentlyContinue
    if ($onPath) { $launchers += $onPath.Source }
    foreach ($known in @("$env:LOCALAPPDATA\Programs\Python\Launcher\py.exe", "$env:WINDIR\py.exe")) {
        if ((Test-Path -LiteralPath $known) -and ($launchers -notcontains $known)) { $launchers += $known }
    }
    foreach ($launcher in $launchers) {
        foreach ($minor in @("3.15", "3.14")) {
            $candidates += , @($launcher, @("-$minor"))
        }
    }
    foreach ($minor in @("315", "314")) {
        $candidates += , @("$env:LOCALAPPDATA\Programs\Python\Python$minor\python.exe", @())
    }
    $pythonOnPath = Get-Command python.exe -ErrorAction SilentlyContinue
    if ($pythonOnPath) { $candidates += , @($pythonOnPath.Source, @()) }
    foreach ($candidate in $candidates) {
        $exe = $candidate[0]; $launcherArgs = [string[]]$candidate[1]
        if (-not (Get-Command $exe -ErrorAction SilentlyContinue)) { continue }
        if (Test-Python -Exe $exe -LauncherArgs $launcherArgs -Code $versionCheck) {
            return , @($exe, $launcherArgs)
        }
    }
    return $null
}

$python = Find-Python
if (-not $python) {
    Write-Host "Student Workspace needs Python 3.14 or newer (3.15 is recommended)."
    $winget = Get-Command winget -CommandType Application -ErrorAction SilentlyContinue | Select-Object -First 1
    if (-not $winget) {
        Write-Host "Install Python 3.15 from https://www.python.org/downloads/ , then run Install.cmd again."
        exit 1
    }
    $answer = Read-Host "Install Python 3.15 now with winget? [y/N]"
    if ($answer -notmatch '^(y|yes)$') {
        Write-Host "Nothing was installed. Install Python 3.15 from https://www.python.org/downloads/ , then run Install.cmd again."
        exit 1
    }
    & $winget.Source install --id Python.Python.3.15 --exact --source winget
    if ($LASTEXITCODE -ne 0) {
        Write-Host "winget could not install Python (exit code $LASTEXITCODE). Install it from https://www.python.org/downloads/ , then run Install.cmd again."
        exit 1
    }
    $python = Find-Python
    if (-not $python) {
        Write-Host "Python was installed. Close this window and run Install.cmd again."
        exit 1
    }
}

$pyExe = $python[0]; $pyArgs = [string[]]$python[1]
Write-Host ("Using Python: " + (@($pyExe) + $pyArgs -join " "))
if (-not (Test-Python -Exe $pyExe -LauncherArgs $pyArgs -Code "import tkinter; tkinter.Tcl()")) {
    Write-Host "This Python has no tkinter, which the setup window needs."
    Write-Host "Rerun the Python installer, choose Modify, and enable 'tcl/tk and IDLE'. Then run Install.cmd again."
    exit 1
}
if ($ProbeOnly) { exit 0 }

& $pyExe @pyArgs (Join-Path $PSScriptRoot "install.py") @WizardArgs
exit $LASTEXITCODE
