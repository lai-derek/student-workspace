"""Static and native-Windows contracts for Windows entry points."""

import shutil
import subprocess
import sys
import venv
from pathlib import Path

import pytest
from student_workspace.workspace import initialize_workspace

from opportunity_discovery.cli import build_parser
from opportunity_discovery.tool_setup import DASHBOARD_CMD, TASK_NAME, register_task

REPO_ROOT = Path(__file__).parent.parent


def _script(name: str) -> str:
    return (REPO_ROOT / "scripts" / name).read_text(encoding="utf-8")


def test_scheduled_run_uses_the_workspace_environment_and_global_options_first():
    script = _script("run.ps1")

    assert '"tools\\.venv\\Scripts\\opdisc.exe"' in script
    assert "& $opdisc --quiet --workspace $workspace run *>> $log" in script
    assert '".student-workspace\\opportunity-discovery\\logs"' in script


def test_scheduled_run_argument_order_matches_cli_parser():
    args = build_parser().parse_args(["--quiet", "--workspace", "W", "run"])

    assert args.quiet is True
    assert args.collector_workspace == "W"
    assert args.command == "run"
    with pytest.raises(SystemExit) as exc_info:
        build_parser().parse_args(["run", "--quiet"])
    assert exc_info.value.code == 2


def test_scheduled_run_preserves_opdisc_exit_code():
    script = _script("run.ps1")

    capture = script.index("$code = $LASTEXITCODE")
    exit_statement = script.index("exit $code")
    assert capture < exit_statement


def test_task_registration_targets_one_workspace_and_never_runs_unasked(tmp_path):
    script = _script("register-task.ps1")

    assert "[string]$WorkspacePath" in script
    assert '-WorkspacePath `"$workspace`"' in script
    assert "-Force" in script
    command = register_task(tmp_path, script=tmp_path / "register-task.ps1")
    assert command[-4:] == ["-WorkspacePath", str(tmp_path), "-TaskName", TASK_NAME]
    assert TASK_NAME != "OpportunityDiscovery"


def _launcher_workspace(root: Path, *, installed: bool) -> Path:
    initialize_workspace(root)
    (root / "Open Dashboard.cmd").write_bytes(DASHBOARD_CMD.encode("utf-8"))
    if installed:
        # A fresh venv's python.exe stands in for opdisc.exe: "dashboard" is not a script file,
        # so it exits with code 2 and opens no window or server. Creating the venv here keeps
        # the test independent of whether pytest itself runs inside one.
        venv_dir = root / "tools" / ".venv"
        venv.create(venv_dir, with_pip=False)
        shutil.copyfile(venv_dir / "Scripts" / "python.exe", venv_dir / "Scripts" / "opdisc.exe")
    return root


def _run_launcher(root: Path, stdin: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        f'cmd.exe /d /s /c ""{root / "Open Dashboard.cmd"}""',
        input=stdin,
        text=True,
        capture_output=True,
        check=False,
    )


@pytest.mark.skipif(sys.platform != "win32", reason="native Windows dashboard launcher test")
def test_dashboard_launcher_handles_spaces_and_returns_the_exit_code(tmp_path):
    root = _launcher_workspace(tmp_path / "workspace & student's files", installed=True)

    result = _run_launcher(root, "\r\n")

    assert result.returncode == 2, result.stdout + result.stderr
    assert "Opening dashboard" in result.stdout
    assert "dashboard" in result.stderr


@pytest.mark.skipif(sys.platform != "win32", reason="native Windows dashboard launcher test")
def test_dashboard_launcher_reports_a_missing_installation(tmp_path):
    root = _launcher_workspace(tmp_path / "workspace", installed=False)

    result = _run_launcher(root, "\r\n")

    assert result.returncode == 1
    assert "Run the Student Workspace setup again" in result.stdout
