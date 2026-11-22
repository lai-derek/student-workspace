"""Registration with student-workspace: setup, check, and workspace-local collector paths."""

import json
import os
import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from student_workspace.check import check_workspace as check_all
from student_workspace.tools import load_manifest, register_tool
from student_workspace.workspace import initialize_workspace

from opportunity_discovery.cli import main
from opportunity_discovery.config import collector_dir, load_workspace_config
from opportunity_discovery.tool_setup import DASHBOARD_CMD, check_workspace

REPO_ROOT = Path(__file__).parent.parent


def registered(tmp_path: Path) -> Path:
    root = tmp_path / "workspace"
    initialize_workspace(root)
    register_tool(root, REPO_ROOT)
    return root


def test_manifest_is_valid_and_matches_the_package():
    manifest = load_manifest(REPO_ROOT)
    assert manifest["name"] == "opportunity-discovery"
    assert manifest["check_command"] == ["opdisc", "check", "{workspace}"]
    assert (REPO_ROOT / manifest["instructions"]).is_file()
    assert manifest["sqlite_files"] == [".student-workspace/opportunity-discovery/data/opdisc.sqlite3"]


def test_registration_runs_setup_and_writes_instructions(tmp_path):
    root = registered(tmp_path)
    state = collector_dir(root)
    assert (root / "opportunities").is_dir()
    assert all((state / name).is_dir() for name in ("data", "output", "logs"))
    database = state / "data" / "opdisc.sqlite3"
    with sqlite3.connect(database) as connection:
        assert connection.execute("SELECT COUNT(*) FROM sources").fetchone()[0] > 0
    workspace_md = (root / "WORKSPACE.md").read_text(encoding="utf-8")
    assert "<!-- student-workspace:begin opportunity-discovery -->" in workspace_md
    assert "opdisc screen WORKSPACE" in workspace_md
    if os.name == "nt":
        assert (root / "Open Dashboard.cmd").read_bytes() == DASHBOARD_CMD.encode("utf-8")
    metadata = json.loads((root / ".student-workspace" / "workspace.json").read_text(encoding="utf-8"))
    assert [tool["name"] for tool in metadata["tools"]] == ["opportunity-discovery"]
    assert check_all(root)["exit_code"] == 0


def test_setup_keeps_a_user_owned_dashboard_launcher(tmp_path):
    root = tmp_path / "workspace"
    initialize_workspace(root)
    launcher = root / "Open Dashboard.cmd"
    launcher.write_bytes(b"@echo off\r\necho my own launcher\r\n")
    register_tool(root, REPO_ROOT)
    assert launcher.read_bytes() == b"@echo off\r\necho my own launcher\r\n"


def test_workspace_config_uses_the_registered_tool_and_workspace_paths(tmp_path):
    root = registered(tmp_path)
    cfg, errors = load_workspace_config(root)
    assert errors == []
    assert cfg.config_path == REPO_ROOT.resolve() / "config" / "default.toml"
    assert cfg.paths.data_dir == collector_dir(root) / "data"
    assert cfg.paths.output_dir == collector_dir(root) / "output"
    assert cfg.paths.logs_dir == collector_dir(root) / "logs"


def test_cli_workspace_option_reads_collector_state_from_any_folder(tmp_path, monkeypatch, capsys):
    root = registered(tmp_path)
    monkeypatch.chdir(tmp_path)
    assert main(["--json", "--workspace", str(root), "status"]) == 0
    status = json.loads(capsys.readouterr().out)
    assert status["database"] == str(collector_dir(root) / "data" / "opdisc.sqlite3")


def test_check_reports_missing_current_stale_and_broken_state(tmp_path, capsys):
    root = registered(tmp_path)
    assert check_workspace(root)[0] == 0
    manifest = collector_dir(root) / "output" / "export_manifest.json"
    now = datetime(2026, 11, 1, tzinfo=UTC)
    manifest.write_text(json.dumps({"generated_at": (now - timedelta(days=1)).isoformat()}), encoding="utf-8")
    assert check_workspace(root, now=now)[0] == 0
    manifest.write_text(json.dumps({"generated_at": (now - timedelta(days=5)).isoformat()}), encoding="utf-8")
    code, messages = check_workspace(root, now=now)
    assert code == 2
    assert "5 days old" in messages[-1]
    (root / ".student-workspace" / "board.json").write_text("{broken", encoding="utf-8")
    assert check_workspace(root)[0] == 1
    assert main(["check", str(root)]) == 1


@pytest.mark.skipif(os.name != "nt", reason="the stale exit code is checked through the Windows launcher")
def test_student_workspace_check_reports_stale_collection(tmp_path):
    root = registered(tmp_path)
    manifest = collector_dir(root) / "output" / "export_manifest.json"
    old = datetime.now(UTC) - timedelta(days=10)
    manifest.write_text(json.dumps({"generated_at": old.isoformat()}), encoding="utf-8")
    report = check_all(root)
    assert report["exit_code"] == 2
    assert report["status"] == "stale"
