"""Install/update core: real venvs and pip installs from local test releases.

These tests take a few minutes: every install creates tools/.venv and installs
the local archives with pip (third-party build requirements may be downloaded).
"""

import hashlib
import importlib.util
import json
import os
import subprocess
import zipfile
from pathlib import Path

import jsonschema
import pytest

from student_workspace import installer

REPO = Path(__file__).parent.parent
BUILD_RELEASE = REPO.parent.parent / "scripts" / "build_release.py"
SPEC = importlib.util.spec_from_file_location("build_release", BUILD_RELEASE)
assert SPEC and SPEC.loader
build_release = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(build_release)

FAKE_CLI = """import sys
from pathlib import Path

VERSION = "{version}"


def main():
    command, workspace = sys.argv[1], Path(sys.argv[2])
    if command == "setup":
        if {fail_setup}:
            print("synthetic setup failure", file=sys.stderr)
            return 1
        marker = workspace / "fake-tool-data" / "setup.txt"
        marker.parent.mkdir(exist_ok=True)
        marker.write_text(VERSION + " " + " ".join(sys.argv[3:]), encoding="utf-8")
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
"""


def fake_tool_archive(directory: Path, version: str, *, fail_setup: bool = False) -> Path:
    top = f"fake-tool-{version}"
    archive = directory / f"{top}.zip"
    manifest = {
        "schema_version": "1.0",
        "name": "fake-tool",
        "display_name": "Fake Tool",
        "package": "fake-tool",
        "owned_paths": ["fake-tool-data/"],
        "check_command": ["fake-tool", "check", "{workspace}"],
        "setup_command": ["fake-tool", "setup", "{workspace}"],
        "setup_options": [{"name": "flag", "label": "Flag", "args": ["--flag"], "default": False}],
        "instructions": "section.md",
        "skills": [],
    }
    pyproject = f"""[build-system]
requires = ["setuptools>=77"]
build-backend = "setuptools.build_meta"

[project]
name = "fake-tool"
version = "{version}"
requires-python = ">=3.14"
dependencies = ["student-workspace>=0.1,<0.2"]

[project.scripts]
fake-tool = "fake_tool:main"
"""
    with zipfile.ZipFile(archive, "w") as bundle:
        bundle.writestr(f"{top}/pyproject.toml", pyproject)
        bundle.writestr(f"{top}/fake_tool.py", FAKE_CLI.format(version=version, fail_setup=fail_setup))
        bundle.writestr(f"{top}/student-workspace-tool.json", json.dumps(manifest))
        bundle.writestr(f"{top}/section.md", f"## Fake tool {version}\n")
    return archive


def core_archive(directory: Path, version: str) -> Path:
    """The real student-workspace checkout, optionally relabelled as another version."""
    current = build_release.tool_info(REPO)["version"]
    info = {"name": "student-workspace", "version": current}
    built = build_release.local_archive(REPO, info, directory / "built")
    if version == current:
        return built
    archive = directory / f"student-workspace-{version}.zip"
    with zipfile.ZipFile(built) as source, zipfile.ZipFile(archive, "w") as target:
        for item in source.infolist():
            data = source.read(item)
            name = item.filename.replace(f"student-workspace-{current}/", f"student-workspace-{version}/", 1)
            if name.endswith(("pyproject.toml", "student_workspace/__init__.py")):
                data = data.replace(f'"{current}"'.encode(), f'"{version}"'.encode())
            target.writestr(name, data)
    return archive


def release(directory: Path, name: str, core: str, fake: str | None, *, fail_setup=False) -> dict:
    # Each release gets its own folder: two releases with the same core version must not
    # overwrite each other's archive (zip entry timestamps would change its checksum).
    own = directory / name
    own.mkdir()
    core_zip = core_archive(own, core)
    tools = [
        {
            "name": "student-workspace",
            "display_name": "Student Workspace",
            "version": core,
            "archive": core_zip.as_uri(),
            "sha256": hashlib.sha256(core_zip.read_bytes()).hexdigest(),
        }
    ]
    if fake:
        archive = fake_tool_archive(own, fake, fail_setup=fail_setup)
        tools.append(
            {
                "name": "fake-tool",
                "display_name": "Fake Tool",
                "version": fake,
                "archive": archive.as_uri(),
                "sha256": hashlib.sha256(archive.read_bytes()).hexdigest(),
            }
        )
    document = {"schema_version": "1.0", "release": name, "tools": tools}
    path = directory / f"{name}.json"
    path.write_text(json.dumps(document), encoding="utf-8")
    return installer.load_release(path)


def personal_digest(root: Path) -> dict[str, str]:
    """Every file outside tools/ and the files setup regenerates."""
    generated = {
        ".student-workspace/workspace.json",
        ".student-workspace/generated.json",
        ".student-workspace/checkpoint.json",
        ".student-workspace/install.log",
        "WORKSPACE.md",
        "fake-tool-data/setup.txt",
    }
    result = {}
    for path in root.rglob("*"):
        relative = path.relative_to(root).as_posix()
        if (
            path.is_file()
            and not relative.startswith(("tools/", ".student-workspace/backups/"))
            and relative not in generated
        ):
            result[relative] = hashlib.sha256(path.read_bytes()).hexdigest()
    return result


def cli(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    exe = root / "tools" / ".venv" / ("Scripts" if os.name == "nt" else "bin") / "student-workspace"
    return subprocess.run([str(exe), *args], capture_output=True, text=True, check=False)


@pytest.fixture(scope="module")
def releases(tmp_path_factory):
    directory = tmp_path_factory.mktemp("releases")
    return {
        "core-only": release(directory, "r1-core", "0.1.0", None),
        "r1": release(directory, "r1", "0.1.0", "0.1.0"),
        "r2": release(directory, "r2", "0.1.1", "0.2.0"),
        "broken": release(directory, "r3", "0.1.1", "0.3.0", fail_setup=True),
    }


def test_release_documents_validate_against_the_schema(releases):
    schema = json.loads((REPO / "schemas" / "release.schema.json").read_text(encoding="utf-8"))
    registry_schema = json.loads((REPO / "schemas" / "tool-manifest.schema.json").read_text(encoding="utf-8"))
    from referencing import Registry, Resource

    registry = Registry().with_resource("tool-manifest.schema.json", Resource.from_contents(registry_schema))
    for document in releases.values():
        jsonschema.Draft202012Validator(schema, registry=registry).validate(document)
    jsonschema.validate(json.loads((REPO / "student-workspace-tool.json").read_text()), registry_schema)


def test_fresh_install_with_a_tool_and_option(tmp_path, releases):
    root = tmp_path / "Student Workspace"
    result = installer.install(root, releases["r1"], {"fake-tool"}, options={"fake-tool": ["flag"]})

    assert [(row["name"], row["action"]) for row in result["tools"]] == [
        ("student-workspace", "install"),
        ("fake-tool", "install"),
    ]
    assert result["backup"] is None
    assert result["check_exit_code"] == 0
    metadata = json.loads((root / ".student-workspace" / "workspace.json").read_text())
    assert [(t["name"], t["version"], t["path"], t["options"]) for t in metadata["tools"]] == [
        ("student-workspace", "0.1.0", "tools/student-workspace", []),
        ("fake-tool", "0.1.0", "tools/fake-tool", ["flag"]),
    ]
    assert (root / "fake-tool-data" / "setup.txt").read_text() == "0.1.0 --flag"
    assert "## Fake tool 0.1.0" in (root / "WORKSPACE.md").read_text(encoding="utf-8")
    assert (root / ".agents" / "skills" / "humanizer" / "SKILL.md").is_file()
    assert not list((root / "tools").glob(".previous-*")) and not list((root / "tools").glob(".staging-*"))
    assert cli(root, "check", str(root)).returncode == 0


def test_add_tool_then_update_keeps_personal_files_and_rolls_back_a_failure(tmp_path, releases):
    root = tmp_path / "workspace"
    installer.install(root, releases["core-only"], set())
    (root / "knowledge" / "PROFILE.md").write_bytes(b"# Synthetic profile\r\nKeep these bytes.\r\n")
    (root / "sources" / "originals").mkdir()
    (root / "sources" / "originals" / "resume.pdf").write_bytes(b"%PDF synthetic \x00\xff")
    (root / "inbox" / "new.txt").write_text("unsorted", encoding="utf-8")
    (root / "applications" / "acme").mkdir()
    (root / "applications" / "acme" / "draft.md").write_text("draft", encoding="utf-8")
    with open(root / "WORKSPACE.md", "a", encoding="utf-8") as handle:
        handle.write("\n## My notes\n\nUser-owned text outside generated blocks.\n")
    personal = personal_digest(root)

    added = installer.install(root, releases["r1"], {"fake-tool"})
    assert [(row["name"], row["action"]) for row in added["tools"]] == [
        ("student-workspace", "keep"),
        ("fake-tool", "install"),
    ]
    assert Path(added["backup"]).is_file()
    assert personal_digest(root) == personal

    updated = installer.install(root, releases["r2"], set())
    assert [(row["name"], row["action"]) for row in updated["tools"]] == [
        ("student-workspace", "update"),
        ("fake-tool", "update"),
    ]
    assert personal_digest(root) == personal
    assert "User-owned text outside generated blocks." in (root / "WORKSPACE.md").read_text()
    assert "## Fake tool 0.2.0" in (root / "WORKSPACE.md").read_text()
    assert cli(root, "--version").stdout.strip() == "student-workspace 0.1.1"
    before_failure = {
        path: path.read_bytes()
        for path in (root / ".student-workspace" / "workspace.json", root / "WORKSPACE.md")
    }
    tool_manifest = (root / "tools" / "fake-tool" / "student-workspace-tool.json").read_bytes()

    with pytest.raises(installer.InstallError, match="synthetic setup failure"):
        installer.install(root, releases["broken"], set())

    assert personal_digest(root) == personal
    assert {path: path.read_bytes() for path in before_failure} == before_failure
    assert (root / "tools" / "fake-tool" / "student-workspace-tool.json").read_bytes() == tool_manifest
    assert "## Fake tool 0.2.0" in (root / "tools" / "fake-tool" / "section.md").read_text()
    assert cli(root, "--version").stdout.strip() == "student-workspace 0.1.1"
    assert cli(root, "check", str(root)).returncode == 0
    backups = root / ".student-workspace" / "backups"
    assert len(list(backups.glob("pre-update-*.zip"))) == 3

    # Already current: the command line does nothing unless asked to reinstall.
    release_path = str(tmp_path / "r2.json")
    _write(Path(release_path), releases["r2"])
    current = cli(root, "update", str(root), "--release", release_path)
    assert current.returncode == 0 and "Already current" in current.stdout
    assert len(list(backups.glob("pre-update-*.zip"))) == 3
    reinstall = cli(root, "update", str(root), "--release", release_path, "--reinstall")
    assert reinstall.returncode == 0, reinstall.stderr
    # Each successful run keeps only the most recent automatic backups.
    assert len(list(backups.glob("pre-update-*.zip"))) == installer.KEEP_UPDATE_BACKUPS
    assert personal_digest(root) == personal


def test_git_checkout_tools_are_never_replaced(tmp_path, releases):
    root = tmp_path / "workspace"
    (root / "tools" / "student-workspace" / ".git").mkdir(parents=True)
    with pytest.raises(installer.InstallError, match="Git checkout"):
        installer.install(root, releases["core-only"], set())
    assert sorted(path.name for path in (root / "tools").iterdir()) == ["student-workspace"]


def test_plan_and_release_validation(tmp_path, releases):
    assert [row["action"] for row in installer.plan(tmp_path, releases["r1"], set())] == ["install"]
    with pytest.raises(installer.InstallError, match="lists no tools"):
        installer.load_release(_write(tmp_path / "bad.json", {"schema_version": "1.0", "tools": []}))
    only_tool = {"schema_version": "1.0", "tools": [dict(releases["r1"]["tools"][1])]}
    with pytest.raises(installer.InstallError, match="student-workspace once"):
        installer.load_release(_write(tmp_path / "no-core.json", only_tool))
    unchecked = {"schema_version": "1.0", "tools": [dict(releases["r1"]["tools"][0])]}
    del unchecked["tools"][0]["sha256"]
    with pytest.raises(installer.InstallError, match="sha256"):
        installer.load_release(_write(tmp_path / "unchecked.json", unchecked))
    with pytest.raises(installer.InstallError, match="does not include"):
        installer.plan(tmp_path, releases["core-only"], {"fake-tool"})


def test_download_rejects_checksum_mismatch_and_unsafe_archives(tmp_path):
    archive = fake_tool_archive(tmp_path, "9.9.9")
    entry = {
        "name": "fake-tool",
        "display_name": "Fake Tool",
        "version": "9.9.9",
        "archive": archive.as_uri(),
        "sha256": "0" * 64,
    }
    staging = tmp_path / "staging"
    staging.mkdir()
    with pytest.raises(installer.InstallError, match="checksum"):
        installer._download(entry, staging)
    unsafe = tmp_path / "unsafe.zip"
    with zipfile.ZipFile(unsafe, "w") as bundle:
        bundle.writestr("top/../../escape.txt", "x")
    with pytest.raises(installer.InstallError, match="unsafe path"):
        installer._extract(unsafe, tmp_path / "out")
    assert not (tmp_path / "escape.txt").exists()


def _write(path: Path, value: dict) -> Path:
    path.write_text(json.dumps(value), encoding="utf-8")
    return path
