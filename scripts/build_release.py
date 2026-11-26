"""Build the files for a Student Workspace release.

    python scripts/build_release.py --release 2026.12.0

Each package in packages/ (by default all of them; choose with --tool NAME) is
zipped from the release tag with `git archive <tag>:packages/<name>`, so every
ZIP has one top-level folder <name>-<version>/ with the package's
student-workspace-tool.json at its root. The script records each ZIP's SHA-256
in release.json and writes Student-Tools-Setup.zip, all into --output (default
dist/). It also writes RELEASE_NOTES.md there, the start of the release
description with a direct setup link.

The interface (frontend/, React) is built once here with `npm ci` and
`npm run build`, and the result is added to the student-workspace ZIP, so
students install only Python packages. --no-frontend-build reuses an existing
build.

Publish by tagging the release commit <release> (e.g. 2026.12.0), running this
script, and creating a release on lai-derek/student-workspace with that tag,
using RELEASE_NOTES.md as the description (`--notes-file`) and uploading every
other file from --output; the release.json URLs point at those uploads.

With --local-archives DIR the script instead zips each package's Git-visible
working files into DIR and points release.json at them as file: URLs, which is
how the installer is tested before anything is committed or published.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import tomllib
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACKAGES = ROOT / "packages"
CORE = PACKAGES / "student-workspace"
FRONTEND = ROOT / "frontend"
# The built interface: produced by `npm run build`, ignored by Git, added to the core's ZIP here.
STATIC = CORE / "src" / "student_workspace" / "web" / "static"
OWNER = "lai-derek"
DEFAULT_TOOLS = ("student-workspace", "opportunity-discovery", "academic-planning")
SETUP_FILES = {
    "Install.cmd": CORE / "installer" / "Install.cmd",
    "setup.ps1": CORE / "installer" / "setup.ps1",
    "install.py": CORE / "installer" / "install.py",
    "installer.py": CORE / "src" / "student_workspace" / "installer.py",
}


def tool_info(package: Path) -> dict:
    manifest = json.loads((package / "student-workspace-tool.json").read_text(encoding="utf-8"))
    project = tomllib.loads((package / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    return {
        "name": manifest["name"],
        "display_name": manifest["display_name"],
        "version": project["version"],
        "setup_options": manifest.get("setup_options", []),
    }


def tracked_files(package: Path) -> list[str]:
    """Tracked plus not-ignored files under the package: what the next commit would contain."""
    listed = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
        cwd=package,
        capture_output=True,
        check=True,
    ).stdout.decode("utf-8")
    return sorted(name for name in listed.split("\0") if name and (package / name).is_file())


def local_archive(package: Path, info: dict, directory: Path) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    top = f"{info['name']}-{info['version']}"
    archive = directory / f"{top}.zip"
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as bundle:
        for name in tracked_files(package):
            bundle.write(package / name, f"{top}/{name}")
    return archive


def release_archive(package: Path, info: dict, directory: Path, ref: str) -> Path:
    """ZIP of packages/<name> at the committed ref, with one top-level folder.

    Only the package's own .gitattributes applies to a subtree archive, so each
    package carries its line-ending and binary rules; core.autocrlf is turned off
    so the archive is the same whichever machine builds it.
    """
    directory.mkdir(parents=True, exist_ok=True)
    top = f"{info['name']}-{info['version']}"
    archive = directory / f"{top}.zip"
    tree = f"{ref}:{package.relative_to(ROOT).as_posix()}"
    subprocess.run(
        [
            "git",
            "-c",
            "core.autocrlf=false",
            "archive",
            "--format=zip",
            f"--prefix={top}/",
            "-o",
            str(archive),
            tree,
        ],
        cwd=ROOT,
        check=True,
    )
    return archive


def build_frontend() -> None:
    """Install the pinned packages from package-lock.json and build the interface into STATIC."""
    npm = shutil.which("npm")
    if npm is None:
        raise SystemExit(
            "npm is needed to build the interface (install Node.js), or pass --no-frontend-build"
        )
    subprocess.run([npm, "ci", "--no-fund", "--no-audit"], cwd=FRONTEND, check=True)
    subprocess.run([npm, "run", "build"], cwd=FRONTEND, check=True)


def add_built_interface(archive: Path, top: str) -> int:
    """Copy the built interface into the core package's ZIP, where the server looks for it."""
    files = sorted(p for p in STATIC.rglob("*") if p.is_file())
    if not (STATIC / "index.html").is_file():
        raise SystemExit(f"no built interface in {STATIC}; run without --no-frontend-build")
    with zipfile.ZipFile(archive, "a", compression=zipfile.ZIP_DEFLATED) as bundle:
        for path in files:
            bundle.write(path, f"{top}/{path.relative_to(CORE).as_posix()}")
    return len(files)


def release_notes(release: str, tools: list[dict]) -> str:
    """Release description: one obvious download link, then the tested versions."""
    base = f"https://github.com/{OWNER}/student-workspace"
    setup = f"{base}/releases/download/{release}/Student-Tools-Setup.zip"
    rows = "\n".join(
        f"| [{tool['display_name']}]({base}/tree/{release}/packages/{tool['name']}) | {tool['version']} |"
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
    parser.add_argument("--release", required=True, help="release name and tag, e.g. 2026.12.0")
    parser.add_argument(
        "--tool", action="append", choices=DEFAULT_TOOLS, help="package to include (default: all)"
    )
    parser.add_argument("--ref", help="git ref to archive (default: the --release tag)")
    parser.add_argument(
        "--local-archives", type=Path, help="zip working files here and reference them as file: URLs"
    )
    parser.add_argument("--output", type=Path, default=ROOT / "dist", help="where the release files go")
    parser.add_argument(
        "--no-frontend-build",
        action="store_true",
        help="reuse the interface already built into the core package",
    )
    args = parser.parse_args(argv)
    output = args.output.resolve()
    names = args.tool or list(DEFAULT_TOOLS)
    if "student-workspace" not in names:
        parser.error("the release must include student-workspace")
    if not args.no_frontend_build:
        build_frontend()

    tools = []
    for name in names:
        package = PACKAGES / name
        info = tool_info(package)
        if args.local_archives:
            archive = local_archive(package, info, args.local_archives.resolve())
            info["archive"] = archive.as_uri()
        else:
            archive = release_archive(package, info, output, args.ref or args.release)
            info["archive"] = (
                f"https://github.com/{OWNER}/student-workspace/releases/download/{args.release}/{archive.name}"
            )
        if name == "student-workspace":
            add_built_interface(archive, f"{info['name']}-{info['version']}")
        info["sha256"] = hashlib.sha256(archive.read_bytes()).hexdigest()
        if not info["setup_options"]:
            del info["setup_options"]
        tools.append(info)
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
