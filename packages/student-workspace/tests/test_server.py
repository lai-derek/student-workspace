"""The local app: request checks, API routes, static files and the serve command."""

from __future__ import annotations

import json
import socket
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from student_workspace.web import app as app_module
from student_workspace.web import serve as serve_module
from student_workspace.web.security import CSRF_HEADER, SESSION_START_PATH, cookie_name
from student_workspace.workspace import initialize_workspace

PORT = 8766
TOKEN = "test-token-not-secret"
BASE = f"http://127.0.0.1:{PORT}"
WRITE_HEADERS = {"origin": BASE, CSRF_HEADER: "1"}


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    root = tmp_path / "Student Workspace"
    initialize_workspace(root)
    return root


def make_app(root: Path, **kwargs: object) -> FastAPI:
    app = app_module.create_app(root, TOKEN, port=PORT, **kwargs)  # type: ignore[arg-type]

    @app.post("/api/test-write")
    def test_write() -> dict[str, bool]:
        return {"ok": True}

    return app


def signed_in(app: FastAPI, base_url: str = BASE) -> TestClient:
    client = TestClient(app, base_url=base_url)
    response = client.get(f"{SESSION_START_PATH}?token={TOKEN}", follow_redirects=False)
    assert response.status_code == 303
    return client


def register_name(root: Path, name: str) -> None:
    path = root / ".student-workspace" / "workspace.json"
    metadata = json.loads(path.read_text(encoding="utf-8"))
    metadata["tools"].append({"name": name, "version": "0.0.0", "path": f"tools/{name}", "options": []})
    path.write_text(json.dumps(metadata), encoding="utf-8")


# ---------- request checks ----------


def test_wrong_host_is_refused_before_anything_else(workspace: Path) -> None:
    client = signed_in(make_app(workspace))
    response = client.get("/api/sections", headers={"host": f"attacker.example:{PORT}"})
    assert response.status_code == 400


def test_everything_needs_the_session_cookie(workspace: Path) -> None:
    client = TestClient(make_app(workspace), base_url=BASE)
    api = client.get("/api/sections")
    assert api.status_code == 401 and api.json() == {"detail": "not signed in"}
    page = client.get("/")
    assert page.status_code == 401 and "launcher" in page.text


def test_session_start_checks_the_token_and_sets_a_strict_cookie(workspace: Path) -> None:
    client = TestClient(make_app(workspace), base_url=BASE)
    assert client.get(f"{SESSION_START_PATH}?token=wrong", follow_redirects=False).status_code == 403
    assert client.get(SESSION_START_PATH, follow_redirects=False).status_code == 403

    response = client.get(f"{SESSION_START_PATH}?token={TOKEN}", follow_redirects=False)
    assert response.status_code == 303 and response.headers["location"] == "/"
    cookie = response.headers["set-cookie"]
    assert cookie.startswith(f"{cookie_name(PORT)}={TOKEN}")
    assert "HttpOnly" in cookie and "SameSite=strict" in cookie
    assert client.get("/api/sections").status_code == 200


@pytest.mark.parametrize(
    ("headers", "allowed"),
    [
        ({}, False),
        ({"origin": "http://attacker.example"}, False),
        ({"origin": "http://127.0.0.1:9999", CSRF_HEADER: "1"}, False),
        ({"origin": BASE}, False),
        ({CSRF_HEADER: "1"}, False),
        (WRITE_HEADERS, True),
    ],
)
def test_writes_need_this_origin_and_the_custom_header(
    workspace: Path, headers: dict[str, str], allowed: bool
) -> None:
    client = signed_in(make_app(workspace))
    response = client.post("/api/test-write", headers=headers)
    assert response.status_code == (200 if allowed else 403)


def test_security_headers_on_every_response(workspace: Path) -> None:
    client = signed_in(make_app(workspace))
    for path in ("/api/sections", "/", "/api/no-such-route"):
        response = client.get(path)
        assert "frame-ancestors 'none'" in response.headers["content-security-policy"]
        assert response.headers["x-frame-options"] == "DENY"
        assert response.headers["x-content-type-options"] == "nosniff"
    assert client.get("/api/sections").headers["cache-control"] == "no-store"


def test_dev_origin_is_accepted_only_when_given(workspace: Path) -> None:
    dev = "http://localhost:5173"
    plain = signed_in(make_app(workspace))
    assert plain.get("/api/sections", headers={"host": "localhost:5173"}).status_code == 400

    client = signed_in(make_app(workspace, dev_origins=[dev]), base_url=dev)
    assert client.get("/api/sections").status_code == 200
    assert client.post("/api/test-write", headers={"origin": dev, CSRF_HEADER: "1"}).status_code == 200


# ---------- API routes ----------


def test_sections_follow_registered_tools(workspace: Path) -> None:
    client = signed_in(make_app(workspace))
    assert [s["id"] for s in client.get("/api/sections").json()] == ["home", "applications", "workspace"]

    register_name(workspace, "academic-planning")
    sections = client.get("/api/sections").json()
    assert [s["id"] for s in sections] == ["home", "applications", "courses", "workspace"]
    assert sections[2] == {"id": "courses", "label": "Courses", "path": "/courses"}


def test_workspace_status_reports_the_check(workspace: Path) -> None:
    register_name(workspace, "missing-tool")
    body = signed_in(make_app(workspace)).get("/api/workspace").json()
    assert body["root"] == str(workspace.resolve())
    assert body["status"] == "error"
    assert isinstance(body["findings"], list)
    [tool] = body["tools"]
    assert tool["name"] == "missing-tool" and tool["status"] == "error" and tool["version"] is None


def test_unknown_api_path_is_404_not_the_interface(workspace: Path) -> None:
    client = signed_in(make_app(workspace))
    assert client.get("/api/no-such-route").status_code == 404
    assert client.get("/api").status_code == 404


def test_schema_is_served_and_docs_page_is_off(workspace: Path) -> None:
    client = signed_in(make_app(workspace))
    schema = client.get("/api/openapi.json").json()
    assert "/api/workspace" in schema["paths"]
    assert client.get("/docs").text == client.get("/").text  # falls through to the interface


# ---------- static files ----------


def test_missing_frontend_page_explains_recovery(workspace: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(app_module, "STATIC_DIR", workspace / "no-build")
    response = signed_in(make_app(workspace)).get("/")
    assert response.status_code == 200
    assert "npm run build" in response.text and "run setup again" in response.text


def test_built_interface_is_served_for_any_page_path(
    workspace: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    static = tmp_path / "static"
    (static / "assets").mkdir(parents=True)
    (static / "index.html").write_text("<div id=root></div>", encoding="utf-8")
    (static / "assets" / "app.js").write_text("console.log(1)", encoding="utf-8")
    monkeypatch.setattr(app_module, "STATIC_DIR", static)
    client = signed_in(make_app(workspace))
    assert client.get("/").text == "<div id=root></div>"
    assert client.get("/applications").text == "<div id=root></div>"
    assert client.get("/assets/app.js").text == "console.log(1)"
    assert client.get("/assets/../index.html").status_code in (200, 404)  # never outside static/


# ---------- serve ----------


def test_serve_binds_localhost_and_announces_a_tokened_link(
    workspace: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    seen: dict[str, object] = {}

    def fake_run(self: object, sockets: list[socket.socket]) -> None:
        seen["address"] = sockets[0].getsockname()
        sockets[0].close()

    opened: list[str] = []
    monkeypatch.setattr(serve_module.uvicorn.Server, "run", fake_run)
    monkeypatch.setattr(serve_module.webbrowser, "open", opened.append)
    lines: list[str] = []
    serve_module.serve(workspace, open_browser=False, announce=lines.append)

    host, port = seen["address"]  # type: ignore[misc]
    assert host == "127.0.0.1" and port > 0
    link = next(line for line in lines if line.startswith("Open: "))
    assert link.startswith(f"Open: http://127.0.0.1:{port}{SESSION_START_PATH}?token=")
    assert len(link.split("token=")[1]) >= 40
    assert opened == []
