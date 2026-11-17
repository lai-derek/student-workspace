"""Drive every wizard page in a hidden Tk window (the install step itself is covered by test_installer)."""

import contextlib
import importlib.util
import json
import sys
from pathlib import Path

import pytest

tk = pytest.importorskip("tkinter")
REPO = Path(__file__).parent.parent
RELEASE = {
    "schema_version": "1.0",
    "release": "test",
    "tools": [
        {
            "name": "student-workspace",
            "display_name": "Student Workspace",
            "version": "0.1.0",
            "archive": "file:///x",
        },
        {
            "name": "opportunity-discovery",
            "display_name": "Opportunity Discovery",
            "version": "0.2.0",
            "archive": "file:///y",
            "setup_options": [
                {"name": "schedule", "label": "Daily", "args": ["--schedule"], "default": True}
            ],
        },
        {
            "name": "academic-planning",
            "display_name": "Academic Planning",
            "version": "0.3.0",
            "archive": "file:///z",
        },
    ],
}


@pytest.fixture()
def wizard_module():
    spec = importlib.util.spec_from_file_location("setup_wizard", REPO / "installer" / "install.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture()
def root():
    try:
        window = tk.Tk()
    except tk.TclError as exc:
        pytest.skip(f"no display: {exc}")
    window.withdraw()
    yield window
    window.destroy()


def texts(widget):
    found = []
    for child in widget.winfo_children():
        with contextlib.suppress(tk.TclError):
            found.append(str(child.cget("text")))
        found.extend(texts(child))
    return found


def checkbuttons(widget):
    found = []
    for child in widget.winfo_children():
        if child.winfo_class() == "TCheckbutton":
            found.append((child.cget("text"), "disabled" in child.state()))
        found.extend(checkbuttons(child))
    return found


def test_pages_for_a_new_workspace(tmp_path, wizard_module, root):
    (tmp_path / ".git").mkdir()
    app = wizard_module.Wizard(root, RELEASE, tmp_path / "Student Workspace")
    assert app.heading.cget("text") == "Welcome"
    app.next()
    assert any("inside the Git folder" in text for text in texts(app.body))
    app.next()
    boxes = checkbuttons(app.body)
    assert boxes[0] == ("Student Workspace (required) 0.1.0", True)
    assert ("Daily", False) in boxes
    app.selected["opportunity-discovery"].set(True)
    app.next()
    summary = "\n".join(texts(app.body))
    assert "Install Student Workspace 0.1.0" in summary
    assert "Install Opportunity Discovery 0.2.0" in summary
    assert "Daily" in summary
    assert "Academic Planning" not in summary
    assert app.options() == {"opportunity-discovery": ["schedule"]}

    app.page = app.PAGES.index("finish")
    app.result = {"workspace": str(tmp_path), "check_exit_code": 0, "tools": [], "backup": None, "log": ""}
    app.show()
    assert app.heading.cget("text") == "Finished"
    app.error = "synthetic failure"
    app.show()
    assert app.heading.cget("text") == "Setup stopped"


def test_existing_workspace_shows_installed_tools_as_locked(tmp_path, wizard_module, root):
    state = tmp_path / ".student-workspace"
    state.mkdir()
    tools = [
        {"name": "student-workspace", "version": "0.0.9", "path": "tools/student-workspace"},
        {"name": "academic-planning", "version": "0.3.0", "path": "tools/academic-planning"},
    ]
    (state / "workspace.json").write_text(json.dumps({"tools": tools}), encoding="utf-8")
    app = wizard_module.Wizard(root, RELEASE, tmp_path)
    app.next()
    assert any("Existing workspace found" in text for text in texts(app.body))
    app.next()
    boxes = dict(checkbuttons(app.body))
    assert boxes["Student Workspace (required): installed 0.0.9, will update to 0.1.0"] is True
    assert boxes["Academic Planning: installed 0.3.0"] is True
    app.next()
    summary = "\n".join(texts(app.body))
    assert "Update Student Workspace 0.1.0 (from 0.0.9)" in summary
    assert "Reinstall Academic Planning 0.3.0" in summary
    assert "A full backup is made first" in summary
