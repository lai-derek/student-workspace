"""Application Studio API: the editing round trips the interface makes."""

from __future__ import annotations

import base64
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from student_workspace.web.app import create_app
from student_workspace.web.security import CSRF_HEADER, SESSION_START_PATH
from student_workspace.workspace import initialize_workspace

PORT = 8767
TOKEN = "studio-api-test-token"
BASE = f"http://127.0.0.1:{PORT}"
FIXTURES = Path(__file__).parent / "fixtures" / "studio"


class Api:
    """Signed-in client that sends the headers writes need."""

    def __init__(self, root: Path) -> None:
        self.client = TestClient(create_app(root, TOKEN, port=PORT), base_url=BASE)
        assert (
            self.client.get(f"{SESSION_START_PATH}?token={TOKEN}", follow_redirects=False).status_code == 303
        )

    def get(self, path: str) -> object:
        response = self.client.get(f"/api/studio{path}")
        assert response.status_code == 200, response.text
        return response.json()

    def post(self, path: str, body: object = None, *, status: int = 200) -> object:
        response = self.client.post(
            f"/api/studio{path}", json=body or {}, headers={"origin": BASE, CSRF_HEADER: "1"}
        )
        assert response.status_code == status, response.text
        return response.json()


@pytest.fixture
def api(tmp_path: Path) -> tuple[Api, Path]:
    root = tmp_path / "Student Workspace"
    initialize_workspace(root)
    return Api(root), root


def imported(api: Api) -> dict:
    tex = (FIXTURES / "jake-resume.tex").read_text(encoding="utf-8")
    return api.post("/resumes", {"application_folder": "applications/acme", "name": "", "tex": tex})  # type: ignore[return-value]


def project_bullets(version: dict) -> list[dict]:
    return version["sections"][1]["entries"][0]["bullets"]


def test_create_from_tex_then_list(api) -> None:
    client, _root = api
    version = imported(client)
    assert version["application_folder"] == "applications/acme"
    assert version["export"]["state"] == "not-exported"
    assert [v["name"] for v in version["versions"]] == [version["name"]]
    assert client.get("/resumes")[0]["application_folder"] == "applications/acme"  # type: ignore[index]


def test_preview_returns_pdf_and_bullet_boxes(api) -> None:
    client, _root = api
    version = imported(client)
    preview = client.get(f"/versions/{version['id']}/preview")
    assert base64.b64decode(preview["pdf_base64"]).startswith(b"%PDF")  # type: ignore[index]
    assert preview["pages"] == 1 and 0 < preview["fill"] < 1  # type: ignore[index]
    assert {b["id"] for b in project_bullets(version)} <= set(preview["boxes"])  # type: ignore[index]


def test_structural_edits_round_trip(api) -> None:
    client, _root = api
    version = imported(client)
    vid = version["id"]
    first, second = project_bullets(version)
    version = client.post(f"/versions/{vid}/move", {"kind": "bullet", "id": second["id"], "position": 0})
    assert [b["id"] for b in project_bullets(version)] == [second["id"], first["id"]]
    version = client.post(f"/versions/{vid}/hide", {"kind": "bullet", "id": first["id"], "hidden": True})
    assert project_bullets(version)[1]["hidden"]
    version = client.post(
        f"/versions/{vid}/bullets/{second['id']}/edit", {"text": "Benchmarked nine models."}
    )
    assert project_bullets(version)[0]["text"] == "Benchmarked nine models."
    version = client.post(f"/versions/{vid}/bullets/{second['id']}/variants", {"text": "Variant wording."})
    variant = project_bullets(version)[0]["variants"][0]
    version = client.post(f"/versions/{vid}/bullets/{second['id']}/variant", {"variant_id": variant["id"]})
    assert project_bullets(version)[0]["text"] == "Variant wording."
    entry = version["sections"][1]["entries"][0]
    version = client.post(f"/versions/{vid}/entries/{entry['id']}/bullets", {"text": "A brand new bullet."})
    assert project_bullets(version)[-1]["text"] == "A brand new bullet."
    version = client.post(f"/versions/{vid}/entries/{entry['id']}", {"dates": "2025 -- 2026"})
    assert version["sections"][1]["entries"][0]["dates"] == "2025 -- 2026"
    version = client.post(f"/versions/{vid}/template", {"template": "modern"})
    version = client.post(f"/versions/{vid}/settings", {"font_size": 10})
    assert version["template"] == "modern" and version["settings"]["font_size"] == 10
    assert client.get(f"/versions/{vid}/preview")["pages"] == 1  # type: ignore[index]


def test_store_errors_are_400_with_the_message(api) -> None:
    client, _root = api
    version = imported(client)
    bullet = project_bullets(version)[0]
    error = client.post(f"/versions/{version['id']}/bullets/{bullet['id']}/edit", {"text": "  "}, status=400)
    assert error == {"detail": "bullet can't be empty"}
    error = client.post(f"/versions/{version['id']}/settings", {"font_size": 30}, status=400)
    assert "font_size" in error["detail"]  # type: ignore[index]


def test_sections_entries_and_new_resume_from_a_version(api) -> None:
    client, _root = api
    version = imported(client)
    vid = version["id"]
    version = client.post(f"/versions/{vid}/sections", {"title": "Experience", "kind": "experience"})
    section = version["sections"][-1]
    version = client.post(
        f"/versions/{vid}/sections/{section['id']}/entries",
        {"kind": "experience", "title": "Research Assistant", "subtitle": "Example Lab", "dates": "2026"},
    )
    assert version["sections"][-1]["entries"][0]["title"] == "Research Assistant"
    copy = client.post(
        "/resumes", {"application_folder": "applications/globex", "name": "x", "copy_from": vid}
    )
    assert [s["title"] for s in copy["sections"]] == [s["title"] for s in version["sections"]]  # type: ignore[index]
    assert copy["header"]["name"] == "Alex Rivera"  # type: ignore[index]


def test_versions_export_and_checks(api) -> None:
    client, root = api
    version = imported(client)
    vid = version["id"]
    newer = client.post(f"/versions/{vid}/new-version")
    assert len(newer["versions"]) == 2  # type: ignore[index]
    result = client.post(f"/versions/{vid}/export")
    assert result["version"]["export"]["state"] == "current"  # type: ignore[index]
    assert (root / result["result"]["pdf_path"]).is_file()  # type: ignore[index]
    checks = client.get(f"/versions/{vid}/checks")
    assert checks["parse"]["result"] == "ok"  # type: ignore[index]
    client.post(
        f"/versions/{vid}/posting",
        {"text": "Interns use Python, Rust and Kubernetes. Rust and Kubernetes daily."},
    )
    terms = {t["term"]: t["covered"] for t in client.get(f"/versions/{vid}/checks")["keywords"]["terms"]}  # type: ignore[index]
    assert terms["Python"] and not terms["Rust"]
    remaining = client.post(f"/versions/{newer['id']}/delete")  # type: ignore[index]
    assert len(remaining["versions"]) == 1  # type: ignore[index]


def test_ask_ai_and_import_variants(api) -> None:
    client, root = api
    version = imported(client)
    vid = version["id"]
    section = version["sections"][1]
    request = client.post(
        f"/versions/{vid}/ask-ai", {"section_id": section["id"], "request": "Tighten these"}
    )
    folder = root / request["request_path"]  # type: ignore[index]
    bullet = project_bullets(version)[0]
    (folder / "drafts" / "variants.json").write_text(
        json.dumps(
            {"schema_version": "1.0", "variants": [{"bullet_id": bullet["id"], "text": "Tighter wording."}]}
        ),
        encoding="utf-8",
    )
    (folder / "response.json").write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "request_id": folder.name,
                "status": "drafted",
                "artifacts": [{"path": "drafts/variants.json", "kind": "draft"}],
                "source_refs": [],
                "notes": "",
                "custom": {},
            }  # fmt: skip
        ),
        encoding="utf-8",
    )
    assert client.get(f"/versions/{vid}/requests")[0]["status"] == "drafted"  # type: ignore[index]
    result = client.post(f"/versions/{vid}/import-variants", {"request_path": request["request_path"]})  # type: ignore[index]
    assert result["result"]["added"] == 1  # type: ignore[index]
    assert project_bullets(result["version"])[0]["variants"][0]["text"] == "Tighter wording."  # type: ignore[index]


def test_evidence_import_and_links(api) -> None:
    client, root = api
    version = imported(client)
    folder = root / "applications" / "acme"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "evidence-matrix.md").write_text(
        "| Claim | Evidence |\n| --- | --- |\n| Nine models | Benchmark notes |\n", encoding="utf-8"
    )
    ids = client.post("/evidence/import", {"path": "applications/acme/evidence-matrix.md"})["ids"]  # type: ignore[index]
    bullet = project_bullets(version)[1]
    client.post(f"/evidence/{ids[0]}/links", {"kind": "bullet", "target_id": bullet["id"]})
    linked = project_bullets(client.get(f"/versions/{version['id']}"))[1]["evidence"]  # type: ignore[arg-type]
    assert linked[0]["title"] == "Nine models"
    client.post("/evidence/import", {"path": "../outside.md"}, status=400)
