"""Build the files for a Student Workspace release.

    python scripts/build_release.py --release 2026.11.0 \
        --tool ../student-workspace --tool ../opportunity-discovery --tool ../academic-planning

Each --tool is a checkout whose pyproject.toml version is tagged v<version>.
The script zips each tag with `git archive`, records the ZIP's SHA-256 in
release.json and writes Student-Tools-Setup.zip, all into --output (default
dist/). It also writes RELEASE_NOTES.md there, the start of the release
description with a direct setup link. Publish by creating a release on
lai-derek/student-workspace with tag <release> (e.g. 2026.11.0), using
RELEASE_NOTES.md as the description (`--notes-file`) and uploading every other
file from --output; the release.json URLs point at those uploads.

With --local-archives DIR the script instead zips each checkout's Git-visible
working files into DIR and points release.json at them as file: URLs, which is
how the installer is tested before anything is published.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import tomllib
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OWNER = "lai-derek"
SETUP_FILES = {
    "Install.cmd": ROOT / "installer" / "Install.cmd",
    "setup.ps1": ROOT / "installer" / "setup.ps1",
    "install.py": ROOT / "installer" / "install.py",
    "installer.py": ROOT / "src" / "student_workspace" / "installer.py",
}


def tool_info(checkout: Path) -> dict:
    manifest = json.loads((checkout / "student-workspace-tool.json").read_text(encoding="utf-8"))
    project = tomllib.loads((checkout / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    return {
        "name": manifest["name"],
        "display_name": manifest["display_name"],
        "version": project["version"],
        "setup_options": manifest.get("setup_options", []),
    }


def tracked_files(checkout: Path) -> list[str]:
    """Tracked plus not-ignored files: what the next commit would contain."""
    listed = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
        cwd=checkout,
        capture_output=True,
        check=True,
    ).stdout.decode("utf-8")
    return sorted(name for name in listed.split("\0") if name and (checkout / name).is_file())


def local_archive(checkout: Path, info: dict, directory: Path) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    top = f"{info['name']}-{info['version']}"
    archive = directory / f"{top}.zip"
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as bundle:
        for name in tracked_files(checkout):
            bundle.write(checkout / name, f"{top}/{name}")
    return archive


def tag_archive(checkout: Path, info: dict, directory: Path) -> Path:
    """ZIP of the committed tag v<version>, with one top-level folder."""
    directory.mkdir(parents=True, exist_ok=True)
    top = f"{info['name']}-{info['version']}"
    archive = directory / f"{top}.zip"
    subprocess.run(
        ["git", "archive", "--format=zip", f"--prefix={top}/", "-o", str(archive), f"v{info['version']}"],
        cwd=checkout,
        check=True,
    )
    return archive


def release_notes(release: str, tools: list[dict]) -> str:
    """Release description: one obvious download link, then the tested versions."""
    setup = (
        f"https://github.com/{OWNER}/student-workspace/releases/download/{release}/Student-Tools-Setup.zip"
    )
    rows = "\n".join(
        f"| [{tool['display_name']}](https://github.com/{OWNER}/{tool['name']}) | {tool['version']} |"
        for tool in tools
    )
    return (
        f"**Install (Windows):** download **[Student-Tools-Setup.zip]({setup})**, extract it "
        "(right-click, Extract All) and double-click `Install.cmd`. Then choose a folder and the "
        "tools you want. You need Python 3.14 or newer; setup offers to install it with winget "
        "if it's missing.\n\n"
        "The other files below are downloaded by setup; you don't need them.\n\n"
        f"| Tool | Version |\n| --- | --- |\n{rows}\n"
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--release", required=True, help="release name and tag, e.g. 2026.11.0")
    parser.add_argument("--tool", action="append", required=True, type=Path, help="tool checkout")
    parser.add_argument(
        "--local-archives", type=Path, help="zip working files here and reference them as file: URLs"
    )
    parser.add_argument("--output", type=Path, default=ROOT / "dist", help="where the release files go")
    args = parser.parse_args(argv)
    output = args.output.resolve()

    tools = []
    for checkout in args.tool:
        checkout = checkout.resolve()
        info = tool_info(checkout)
        if args.local_archives:
            archive = local_archive(checkout, info, args.local_archives.resolve())
            info["archive"] = archive.as_uri()
        else:
            archive = tag_archive(checkout, info, output)
            info["archive"] = (
                f"https://github.com/{OWNER}/student-workspace/releases/download/{args.release}/{archive.name}"
            )
        info["sha256"] = hashlib.sha256(archive.read_bytes()).hexdigest()
        if not info["setup_options"]:
            del info["setup_options"]
        tools.append(info)
    if "student-workspace" not in {tool["name"] for tool in tools}:
        parser.error("the release must include the student-workspace checkout")
    release = {"schema_version": "1.0", "release": args.release, "tools": tools}
    text = json.dumps(release, indent=2) + "\n"

    output.mkdir(parents=True, exist_ok=True)
    (output / "release.json").write_text(text, encoding="utf-8")
    setup_zip = output / "Student-Tools-Setup.zip"
    with zipfile.ZipFile(setup_zip, "w", compression=zipfile.ZIP_DEFLATED) as bundle:
        for name, source in SETUP_FILES.items():
            bundle.write(source, f"Student-Tools-Setup/{name}")
        bundle.writestr("Student-Tools-Setup/release.json", text)
    (output / "RELEASE_NOTES.md").write_text(release_notes(args.release, tools), encoding="utf-8")
    print(f"wrote release files to {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
