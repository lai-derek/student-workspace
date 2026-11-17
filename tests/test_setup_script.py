"""Native-Windows contracts for Install.cmd and setup.ps1 (Python discovery, no unasked installs)."""

import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).parent.parent
SETUP = REPO / "installer" / "setup.ps1"
pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="native Windows installer test")


def base_python() -> Path:
    return Path(getattr(sys, "_base_executable", sys.executable))


def run_setup(
    tmp_path: Path,
    path_dirs: list[Path],
    stdin: str = "",
    winget: bool = False,
    hide_user_python: bool = True,
):
    """Run setup.ps1 with only `path_dirs` on PATH and no per-user Python locations."""
    shims = tmp_path / "shims"
    shims.mkdir(exist_ok=True)
    if winget:
        # A batch shim records each call and fails, so nothing is ever installed.
        (shims / "winget.cmd").write_bytes(b'@echo %*>> "%~dp0winget-calls.txt"\r\n@exit /b 5\r\n')
    env = os.environ.copy()
    env["PATH"] = os.pathsep.join(str(path) for path in [shims, *path_dirs])
    if hide_user_python:
        env["LOCALAPPDATA"] = str(tmp_path / "localappdata")
        env["WINDIR"] = str(tmp_path / "windir")
    command = [
        str(Path(os.environ["SYSTEMROOT"]) / "System32" / "WindowsPowerShell" / "v1.0" / "powershell.exe"),
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        str(SETUP),
        "-ProbeOnly",
    ]
    return subprocess.run(command, input=stdin, text=True, capture_output=True, env=env, check=False)


def test_install_cmd_bypasses_execution_policy_and_keeps_errors_visible():
    text = (REPO / "installer" / "Install.cmd").read_bytes().decode("ascii")
    assert "\r\n" in text
    assert 'powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0setup.ps1"' in text
    assert 'if not "%SETUP_EXIT%"=="0" pause' in text


def test_install_cmd_alone_says_to_extract_the_zip(tmp_path):
    # Opening Install.cmd from inside the ZIP runs it without the other setup files.
    (tmp_path / "Install.cmd").write_bytes((REPO / "installer" / "Install.cmd").read_bytes())
    result = subprocess.run(
        ["cmd.exe", "/c", str(tmp_path / "Install.cmd")],
        input="\r\n",
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 1
    assert "Extract the whole ZIP first" in result.stdout
    assert "-File parameter" not in result.stdout + result.stderr


def test_setup_messages_say_314_or_newer():
    script = SETUP.read_text(encoding="utf-8")
    assert "Python 3.14 or newer (3.15 is recommended)" in script
    assert "3.11" not in script
    assert "sys.version_info >= (3, 14)" in script


def test_probe_finds_a_compatible_python_on_path(tmp_path):
    result = run_setup(tmp_path, [base_python().parent], hide_user_python=False)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "Using Python:" in result.stdout


def test_missing_python_without_winget_installs_nothing(tmp_path):
    result = run_setup(tmp_path, [])
    assert result.returncode == 1
    assert "needs Python 3.14 or newer" in result.stdout
    assert "https://www.python.org/downloads/" in result.stdout


def test_missing_python_with_winget_asks_and_respects_no(tmp_path):
    result = run_setup(tmp_path, [], stdin="n\n", winget=True)
    assert result.returncode == 1
    # Read-Host shows its prompt on the console host, not in redirected output.
    assert "Nothing was installed" in result.stdout
    assert not (tmp_path / "shims" / "winget-calls.txt").exists()


def test_missing_python_with_winget_runs_it_only_after_yes(tmp_path):
    result = run_setup(tmp_path, [], stdin="y\n", winget=True)
    assert result.returncode == 1
    assert "winget could not install Python (exit code 5)" in result.stdout
    calls = (tmp_path / "shims" / "winget-calls.txt").read_text().strip()
    assert calls == "install --id Python.Python.3.15 --exact --source winget"


def test_old_python_on_path_is_not_accepted(tmp_path):
    old = Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Python" / "Python312"
    if not (old / "python.exe").is_file():
        pytest.skip("Python 3.12 is not installed here")
    result = run_setup(tmp_path, [old])  # old Python is never run with a hidden LOCALAPPDATA
    assert result.returncode == 1
    assert "needs Python 3.14 or newer" in result.stdout
