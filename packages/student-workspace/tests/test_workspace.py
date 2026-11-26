"""Workspace initialization, tool registration, generated instructions, pointers and check."""

import json
import os
from pathlib import Path

import pytest

from student_workspace.check import check_workspace
from student_workspace.cli import main
from student_workspace.state import STATE_DIR, WorkspaceStateError, require_workspace
from student_workspace.tools import (
    load_manifest,
    refresh_workspace,
    register_tool,
    render_workspace_md,
    unregister_tool,
)
from student_workspace.workspace import APP_LAUNCHER, initialize_workspace

REPO = Path(__file__).parent.parent
STARTERS = {
    "WORKSPACE.md",
    "AGENTS.md",
    "CLAUDE.md",
    "knowledge/PROFILE.md",
    "knowledge/CATALOG.md",
    f"{STATE_DIR}/source-manifest.json",
    f"{STATE_DIR}/workspace.json",
}


@pytest.mark.skipif(os.name != "nt", reason="The launcher is a Windows command file")
def test_initializer_keeps_a_user_owned_launcher(tmp_path):
    launcher = tmp_path / APP_LAUNCHER
    original = b"@echo off\r\necho My launcher\r\n"
    launcher.write_bytes(original)

    result = initialize_workspace(tmp_path)

    assert launcher.read_bytes() == original
    assert APP_LAUNCHER not in result.updated_files


def fake_tool(tmp_path: Path, *, name="fake-tool", check=None, skills=(), instructions=None) -> Path:
    """A tool folder whose package is student-workspace itself, so no install is needed."""
    folder = tmp_path / name
    folder.mkdir()
    manifest = {
        "schema_version": "1.0",
        "name": name,
        "display_name": name.replace("-", " ").title(),
        "package": "student-workspace",
        "owned_paths": [f"{name}-data/"],
        "check_command": check,
        "setup_command": None,
        "skills": list(skills),
        "instructions": None,
    }
    if instructions is not None:
        (folder / "section.md").write_text(instructions, encoding="utf-8")
        manifest["instructions"] = "section.md"
    for skill in skills:
        (folder / "skills" / skill).mkdir(parents=True)
        (folder / "skills" / skill / "SKILL.md").write_text(
            f"---\nname: {skill}\ndescription: Synthetic {skill} skill.\n---\n\n# {skill}\n", encoding="utf-8"
        )
    (folder / "student-workspace-tool.json").write_text(json.dumps(manifest), encoding="utf-8")
    return folder


def test_initializer_builds_layout_and_generated_instructions(tmp_path):
    root = tmp_path / "Student Workspace"
    result = initialize_workspace(root)
    for folder in ("inbox", "sources", "knowledge", "applications", "tools", STATE_DIR):
        assert (root / folder).is_dir()
    launcher = {"Open Student Workspace.cmd"} if os.name == "nt" else set()
    assert set(result.created_files) == STARTERS | launcher
    metadata = json.loads((root / STATE_DIR / "workspace.json").read_text(encoding="utf-8"))
    assert metadata == {
        "schema_version": "1.0",
        "private_state_root": str(root.resolve()),
        "tools": [],
        "custom": {},
    }
    manifest = json.loads((root / STATE_DIR / "source-manifest.json").read_text(encoding="utf-8"))
    assert manifest == {"schema_version": "1.0", "imports": [], "external_references": [], "custom": {}}
    assert (root / "AGENTS.md").read_text() == (root / "CLAUDE.md").read_text()
    workspace_md = (root / "WORKSPACE.md").read_text(encoding="utf-8")
    assert "<!-- student-workspace:begin student-workspace -->" in workspace_md
    assert "student-workspace check WORKSPACE" in workspace_md


def test_initializer_preserves_user_files_custom_metadata_and_tools(tmp_path):
    root = tmp_path / "workspace"
    initialize_workspace(root)
    (root / "WORKSPACE.md").write_text("# My instructions\n", encoding="utf-8")
    (root / "CLAUDE.md").unlink()
    metadata_path = root / STATE_DIR / "workspace.json"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    metadata["custom"] = {"synthetic": {"nested": True}}
    metadata["tools"] = [{"name": "kept", "version": "1", "path": "tools/kept"}]
    metadata_path.write_text(json.dumps(metadata), encoding="utf-8")

    result = initialize_workspace(root)

    assert result.created_files == ()
    assert (root / "WORKSPACE.md").read_text(encoding="utf-8") == "# My instructions\n"
    assert not (root / "CLAUDE.md").exists()
    saved = json.loads(metadata_path.read_text(encoding="utf-8"))
    assert saved["custom"] == {"synthetic": {"nested": True}}
    assert saved["tools"] == metadata["tools"]
    assert any("no generated blocks" in warning for warning in result.warnings)


def test_initializer_warns_when_workspace_is_inside_git(tmp_path):
    (tmp_path / ".git").mkdir()
    result = initialize_workspace(tmp_path / "private")
    assert any("inside Git checkout" in warning for warning in result.warnings)


def test_init_cli_json_and_file_path_rejection(tmp_path, capsys):
    root = tmp_path / "workspace"
    assert main(["--json", "init", str(root)]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["workspace"] == str(root.resolve())
    target = tmp_path / "not-a-directory"
    target.write_text("occupied", encoding="utf-8")
    assert main(["init", str(target)]) == 1
    assert "not a directory" in capsys.readouterr().err


def test_render_keeps_user_text_replaces_blocks_and_drops_retired_ones():
    text = (
        "# Mine\n\nUser intro.\n\n"
        "<!-- student-workspace:begin a -->\nold a\n<!-- student-workspace:end a -->\n\n"
        "User middle.\n\n"
        "<!-- student-workspace:begin gone -->\nretired\n<!-- student-workspace:end gone -->\n"
    )
    rendered = render_workspace_md(text, {"a": "new a\n", "b": "new b\n"})
    assert "User intro." in rendered and "User middle." in rendered
    assert "new a" in rendered and "old a" not in rendered
    assert "retired" not in rendered
    assert rendered.index("new a") < rendered.index("User middle.") < rendered.index("new b")
    assert render_workspace_md(rendered, {"a": "new a\n", "b": "new b\n"}) == rendered


def test_register_generates_pointers_blocks_and_respects_user_files(tmp_path):
    root = tmp_path / "workspace"
    initialize_workspace(root)
    user_skill = root / ".claude" / "skills" / "beta" / "SKILL.md"
    user_skill.parent.mkdir(parents=True)
    user_skill.write_text("my own beta skill\n", encoding="utf-8")
    tool = fake_tool(tmp_path, skills=("alpha", "beta"), instructions="## Fake tool\n\nUse it.\n")

    result = register_tool(root, tool)

    assert result["tool"]["name"] == "fake-tool"
    pointer = (root / ".agents" / "skills" / "alpha" / "SKILL.md").read_text(encoding="utf-8")
    assert "name: alpha" in pointer and "description: Synthetic alpha skill." in pointer
    assert (root / ".claude" / "skills" / "alpha" / "SKILL.md").read_text(encoding="utf-8") == pointer
    assert user_skill.read_text(encoding="utf-8") == "my own beta skill\n"
    assert any(".claude/skills/beta/SKILL.md is not a generated pointer" in w for w in result["warnings"])
    workspace_md = (root / "WORKSPACE.md").read_text(encoding="utf-8")
    assert "<!-- student-workspace:begin fake-tool -->\n## Fake tool" in workspace_md
    assert "**Fake Tool**" in workspace_md
    assert refresh_workspace(root) == {"created": [], "updated": [], "warnings": result["warnings"]}

    unregister_tool(root, "fake-tool")
    assert not (root / ".agents" / "skills" / "alpha").exists()
    assert user_skill.is_file()
    assert "fake-tool" not in (root / "WORKSPACE.md").read_text(encoding="utf-8")


def test_registration_rejects_bad_manifests_and_unknown_options(tmp_path):
    root = tmp_path / "workspace"
    initialize_workspace(root)
    tool = fake_tool(tmp_path)
    with pytest.raises(WorkspaceStateError, match="unknown setup options"):
        register_tool(root, tool, options=("nope",))
    manifest = json.loads((tool / "student-workspace-tool.json").read_text())
    manifest["owned_paths"] = ["../escape"]
    (tool / "student-workspace-tool.json").write_text(json.dumps(manifest))
    with pytest.raises(WorkspaceStateError, match="inside its base folder"):
        load_manifest(tool)
    manifest["owned_paths"] = []
    manifest["package"] = "not-an-installed-package"
    (tool / "student-workspace-tool.json").write_text(json.dumps(manifest))
    with pytest.raises(WorkspaceStateError, match="not installed"):
        register_tool(root, tool)
    assert require_workspace(root)[1]["tools"] == []


def test_core_manifest_lists_existing_skills():
    manifest = load_manifest(REPO)
    assert manifest["name"] == "student-workspace"
    for skill in manifest["skills"]:
        assert (REPO / "skills" / skill / "SKILL.md").is_file()


@pytest.mark.parametrize(
    ("code", "expected"),
    [("0", ("current", 0)), ("2", ("stale", 2)), ("5", ("error", 1))],
)
def test_check_combines_tool_exit_codes(tmp_path, capsys, code, expected):
    root = tmp_path / "workspace"
    initialize_workspace(root)
    register_tool(root, fake_tool(tmp_path, check=["python", "-c", f"import sys; sys.exit({code})"]))
    report = check_workspace(root)
    assert (report["status"], report["exit_code"]) == expected
    assert main(["check", str(root)]) == expected[1]


def test_check_reports_missing_tool_folder_and_version_drift(tmp_path):
    root = tmp_path / "workspace"
    initialize_workspace(root)
    tool = fake_tool(tmp_path)
    register_tool(root, tool)
    metadata_path = root / STATE_DIR / "workspace.json"
    metadata = json.loads(metadata_path.read_text())
    metadata["tools"][0]["version"] = "0.0.0"
    metadata_path.write_text(json.dumps(metadata))
    assert check_workspace(root)["exit_code"] == 2
    metadata["tools"][0]["path"] = str(tmp_path / "missing")
    metadata_path.write_text(json.dumps(metadata))
    assert check_workspace(root)["exit_code"] == 1
