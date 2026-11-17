"""Student Workspace setup wizard (tkinter; ships with Windows Python).

Run `Install.cmd` on Windows or `python install.py` elsewhere. The wizard only
collects choices; the shared install core in installer.py does the work.
"""

from __future__ import annotations

import argparse
import importlib.util
import os
import queue
import subprocess
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, ttk
from types import ModuleType
from typing import Any

HERE = Path(__file__).resolve().parent


def _load_core() -> ModuleType:
    for candidate in (HERE / "installer.py", HERE.parent / "src" / "student_workspace" / "installer.py"):
        if candidate.is_file():
            spec = importlib.util.spec_from_file_location("student_workspace_installer", candidate)
            assert spec and spec.loader
            module = importlib.util.module_from_spec(spec)
            sys.modules[spec.name] = module
            spec.loader.exec_module(module)
            return module
    raise SystemExit("installer.py is missing next to install.py")


core = _load_core()


def documents_folder() -> Path:
    if os.name == "nt":
        import ctypes
        from ctypes import wintypes

        class GUID(ctypes.Structure):
            _fields_ = [
                ("Data1", wintypes.DWORD),
                ("Data2", wintypes.WORD),
                ("Data3", wintypes.WORD),
                ("Data4", ctypes.c_ubyte * 8),
            ]

        # FOLDERID_Documents, which follows OneDrive or other redirection.
        folder_id = GUID(
            0xFDD39AD0, 0x238F, 0x46AF, (ctypes.c_ubyte * 8)(0xAD, 0xB4, 0x6C, 0x85, 0x48, 0x03, 0x69, 0xC7)
        )
        pointer = ctypes.c_wchar_p()
        if (
            ctypes.windll.shell32.SHGetKnownFolderPath(
                ctypes.byref(folder_id), 0, None, ctypes.byref(pointer)
            )
            == 0
        ):
            path = Path(pointer.value or "")
            ctypes.windll.ole32.CoTaskMemFree(pointer)
            if path.is_dir():
                return path
    return Path.home() / "Documents"


class Wizard(ttk.Frame):
    PAGES = ("welcome", "location", "tools", "summary", "install", "finish")

    def __init__(self, master: tk.Tk, release: dict[str, Any], default_location: Path) -> None:
        super().__init__(master, padding=16)
        self.master = master
        self.release = release
        self.location = tk.StringVar(value=str(default_location))
        self.selected: dict[str, tk.BooleanVar] = {}
        self.option_vars: dict[tuple[str, str], tk.BooleanVar] = {}
        self.page = 0
        self.result: dict[str, Any] | None = None
        self.error: str | None = None
        self.events: queue.Queue[tuple[str, Any]] = queue.Queue()
        master.title("Student Workspace Setup")
        master.minsize(560, 400)
        self.grid(sticky="nsew")
        master.columnconfigure(0, weight=1)
        master.rowconfigure(0, weight=1)
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)
        self.heading = ttk.Label(self, font=("Segoe UI", 14, "bold"))
        self.heading.grid(row=0, column=0, sticky="w", pady=(0, 12))
        self.body = ttk.Frame(self)
        self.body.grid(row=1, column=0, sticky="nsew")
        self.body.columnconfigure(0, weight=1)
        buttons = ttk.Frame(self)
        buttons.grid(row=2, column=0, sticky="e", pady=(12, 0))
        self.back_button = ttk.Button(buttons, text="< Back", command=self.back)
        self.next_button = ttk.Button(buttons, text="Next >", command=self.next)
        self.cancel_button = ttk.Button(buttons, text="Cancel", command=master.destroy)
        self.back_button.grid(row=0, column=0, padx=4)
        self.next_button.grid(row=0, column=1, padx=4)
        self.cancel_button.grid(row=0, column=2, padx=4)
        self.show()

    # Navigation ---------------------------------------------------------------
    def workspace(self) -> Path:
        return Path(self.location.get()).expanduser()

    def installed(self) -> dict[str, dict[str, Any]]:
        try:
            return core.installed_tools(self.workspace())
        except core.InstallError:
            return {}

    def chosen(self) -> set[str]:
        return {name for name, var in self.selected.items() if var.get()}

    def options(self) -> dict[str, list[str]]:
        result: dict[str, list[str]] = {}
        for (tool, option), var in self.option_vars.items():
            if tool in self.chosen() and tool not in self.installed():
                result.setdefault(tool, [])
                if var.get():
                    result[tool].append(option)
        return result

    def back(self) -> None:
        if self.page > 0:
            self.page -= 1
            self.show()

    def next(self) -> None:
        name = self.PAGES[self.page]
        if name == "finish":
            self.master.destroy()
            return
        if name == "location" and not self.location.get().strip():
            return
        self.page += 1
        self.show()

    def clear(self) -> None:
        for child in self.body.winfo_children():
            child.destroy()

    def show(self) -> None:
        self.clear()
        name = self.PAGES[self.page]
        self.back_button.state(["!disabled"] if 0 < self.page < 4 else ["disabled"])
        self.next_button.state(["!disabled"])
        self.next_button.configure(text="Next >")
        self.cancel_button.state(["!disabled"])
        getattr(self, f"page_{name}")()

    def text(self, value: str, row: int, **grid: Any) -> ttk.Label:
        label = ttk.Label(self.body, text=value, wraplength=520, justify="left")
        label.grid(row=row, column=0, sticky="w", **{"pady": (0, 8), **grid})
        return label

    # Pages --------------------------------------------------------------------
    def page_welcome(self) -> None:
        self.heading.configure(text="Welcome")
        self.text(
            "This sets up a private Student Workspace folder for your AI agent (Claude Code or Codex) "
            "and the tools you choose. Your personal files stay in that folder on this computer.",
            0,
        )
        self.text(
            f"Release {self.release.get('release', '')}. Running setup again later adds tools or "
            "updates them; it backs up the workspace first and changes only its tools folder.",
            1,
        )

    def page_location(self) -> None:
        self.heading.configure(text="Location")
        self.text("Workspace folder:", 0)
        row = ttk.Frame(self.body)
        row.grid(row=1, column=0, sticky="ew")
        row.columnconfigure(0, weight=1)
        entry = ttk.Entry(row, textvariable=self.location)
        entry.grid(row=0, column=0, sticky="ew")
        ttk.Button(row, text="Browse...", command=self.browse).grid(row=0, column=1, padx=(6, 0))
        self.location_note = self.text("", 2, pady=(8, 0))
        self.location.trace_add("write", lambda *_: self.update_location_note())
        self.update_location_note()

    def browse(self) -> None:
        chosen = filedialog.askdirectory(initialdir=str(self.workspace().parent), mustexist=False)
        if chosen:
            self.location.set(str(Path(chosen)))

    def update_location_note(self) -> None:
        notes = []
        installed = self.installed()
        if installed:
            versions = ", ".join(f"{name} {item.get('version')}" for name, item in sorted(installed.items()))
            notes.append(f"Existing workspace found ({versions}). Setup will update it.")
        git_root = core.inside_git_checkout(self.workspace())
        if git_root is not None:
            notes.append(
                f"Warning: this folder is inside the Git folder {git_root}. Private files could be "
                "committed and published by accident. Choose a folder outside Git unless you intend this."
            )
        if hasattr(self, "location_note") and self.location_note.winfo_exists():
            self.location_note.configure(text="\n\n".join(notes))

    def page_tools(self) -> None:
        self.heading.configure(text="Tools")
        installed = self.installed()
        row = 0
        for entry in self.release["tools"]:
            name = entry["name"]
            current = installed.get(name, {}).get("version")
            required = name == core.CORE
            label = entry["display_name"]
            if required:
                label += " (required)"
            if current and current != entry["version"]:
                label += f": installed {current}, will update to {entry['version']}"
            elif current:
                label += f": installed {current}"
            else:
                label += f" {entry['version']}"
            var = self.selected.setdefault(name, tk.BooleanVar(value=required or bool(current)))
            if required or current:
                var.set(True)
            box = ttk.Checkbutton(self.body, text=label, variable=var)
            box.grid(row=row, column=0, sticky="w", pady=2)
            if required or current:
                box.state(["disabled"])
            row += 1
            if not current:
                for option in entry.get("setup_options", []):
                    key = (name, option["name"])
                    option_var = self.option_vars.setdefault(key, tk.BooleanVar(value=option["default"]))
                    ttk.Checkbutton(self.body, text=option["label"], variable=option_var).grid(
                        row=row, column=0, sticky="w", padx=(28, 0), pady=1
                    )
                    row += 1

    def page_summary(self) -> None:
        self.heading.configure(text="Summary")
        try:
            rows = core.plan(self.workspace(), self.release, self.chosen())
        except core.InstallError as exc:
            self.text(str(exc), 0)
            self.next_button.state(["disabled"])
            return
        lines = [f"Folder: {self.workspace()}", ""]
        for row in rows:
            verb = {"install": "Install", "update": "Update", "keep": "Reinstall"}[row["action"]]
            before = f" (from {row['installed_version']})" if row["action"] == "update" else ""
            lines.append(f"{verb} {row['display_name']} {row['version']}{before}")
            for option in self.options().get(row["name"], []):
                labels = {item["name"]: item["label"] for item in row.get("setup_options", [])}
                lines.append(f"    {labels.get(option, option)}")
        if self.installed():
            lines += ["", "A full backup is made first in .student-workspace/backups/."]
        self.text("\n".join(lines), 0)
        self.next_button.configure(text="Install")

    def page_install(self) -> None:
        self.heading.configure(text="Installing")
        for button in (self.back_button, self.next_button, self.cancel_button):
            button.state(["disabled"])
        self.progress = ttk.Progressbar(self.body, maximum=1.0, length=500)
        self.progress.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        self.status = self.text("Starting...", 1)
        workspace, chosen, options = self.workspace(), self.chosen(), self.options()

        def work() -> None:
            try:
                result = core.install(
                    workspace,
                    self.release,
                    chosen,
                    options=options,
                    progress=lambda fraction, message: self.events.put(("progress", (fraction, message))),
                )
                self.events.put(("done", result))
            except Exception as exc:  # Shown to the user on the finish page.
                self.events.put(("error", str(exc)))

        threading.Thread(target=work, daemon=True).start()
        self.after(100, self.poll)

    def poll(self) -> None:
        try:
            while True:
                kind, value = self.events.get_nowait()
                if kind == "progress":
                    self.progress["value"], message = value
                    self.status.configure(text=message)
                else:
                    if kind == "done":
                        self.result = value
                    else:
                        self.error = value
                    self.page += 1
                    self.show()
                    return
        except queue.Empty:
            self.after(100, self.poll)

    def page_finish(self) -> None:
        self.next_button.configure(text="Close")
        self.back_button.state(["disabled"])
        self.cancel_button.state(["disabled"])
        if self.error:
            self.heading.configure(text="Setup stopped")
            self.text(self.error, 0)
            self.text(
                "Your previous tools were left in place. Nothing outside the tools folder was removed.", 1
            )
            return
        assert self.result is not None
        self.heading.configure(text="Finished")
        check = {0: "current", 2: "stale (see the log)", 1: "reported problems (see the log)"}
        self.text(
            f"Student Workspace is ready in {self.result['workspace']}.\n"
            f"Workspace check: {check.get(self.result['check_exit_code'], 'unknown')}.\n"
            "Open the folder with your AI agent and ask it what to do next.",
            0,
        )
        buttons = ttk.Frame(self.body)
        buttons.grid(row=1, column=0, sticky="w", pady=(8, 0))
        ttk.Button(buttons, text="Open folder", command=self.open_folder).grid(row=0, column=0, padx=(0, 6))
        dashboard = self.workspace() / "Open Dashboard.cmd"
        if dashboard.is_file():
            ttk.Button(buttons, text="Open dashboard", command=self.open_dashboard).grid(row=0, column=1)

    def open_folder(self) -> None:
        if os.name == "nt":
            os.startfile(self.workspace())  # type: ignore[attr-defined]
        else:
            subprocess.Popen(["xdg-open", str(self.workspace())])

    def open_dashboard(self) -> None:
        if os.name == "nt":
            os.startfile(self.workspace() / "Open Dashboard.cmd")  # type: ignore[attr-defined]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Student Workspace setup wizard")
    parser.add_argument("--release", default=str(HERE / "release.json"), help="release.json path or URL")
    parser.add_argument("--location", type=Path, help="initial workspace folder")
    args = parser.parse_args(argv)
    try:
        release = core.load_release(args.release)
    except core.InstallError as exc:
        print(f"ERROR {exc}", file=sys.stderr)
        return 1
    root = tk.Tk()
    Wizard(root, release, args.location or documents_folder() / "Student Workspace")
    root.mainloop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
