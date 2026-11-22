"""Application handoffs for board opportunities, built on student-workspace."""

import json
from pathlib import Path
from urllib.request import urlopen

import jsonschema
import pytest
from student_workspace.state import WorkspaceStateError

from opportunity_discovery.board import list_workspace_board
from opportunity_discovery.cli import main
from opportunity_discovery.handoff import request_for_opportunity, requests_for_opportunity
from opportunity_discovery.review import apply_workspace_review
from tests.test_dashboard import dashboard, post
from tests.test_review import make_generation, make_workspace, materialize_review

ROOT = Path(__file__).parent.parent
DEMO = ROOT / "tests" / "fixtures" / "demo"
SCENARIO = json.loads((DEMO / "phase8-application.json").read_text(encoding="utf-8"))
PROMOTED_ID = SCENARIO["opportunity_id"]


def seeded_workspace(tmp_path):
    root = make_workspace(tmp_path)
    manifest = make_generation(tmp_path)
    apply_workspace_review(root, materialize_review(tmp_path), manifest_path=manifest)
    source = root / "sources" / "synthetic-project.md"
    source.write_text("# Synthetic project\nA fictional classroom sensor logger.\n", encoding="utf-8")
    return root


def test_request_snapshots_the_board_record_in_the_opportunity_folder(tmp_path, capsys):
    root = seeded_workspace(tmp_path)
    request = SCENARIO["request"]
    result = request_for_opportunity(
        root,
        PROMOTED_ID,
        request["artifact_type"],
        request["request_text"],
        references=tuple(request["references"]),
    )
    assert result["request_path"].startswith(f"applications/{PROMOTED_ID}/requests/req_")
    assert result["target"] == {"kind": "opportunity", "id": PROMOTED_ID, "url": None}
    folder = root / result["request_path"]
    target = json.loads((folder / "target.json").read_text(encoding="utf-8"))
    board_schema = json.loads((ROOT / "schemas" / "opportunity-board-page.schema.json").read_text())
    snapshot = {key: value for key, value in target.items() if key not in {"kind", "id", "url"}}
    jsonschema.validate(snapshot, board_schema["properties"]["items"]["items"])
    assert target["official_url"] == "https://synthetic.example/official/intern-open"
    assert target["eligibility"]["conclusion"] == "no-known-hard-failure"
    assert requests_for_opportunity(root, PROMOTED_ID)[0]["request_id"] == result["request_id"]
    assert list_workspace_board(root, view="active")["total"] == 2

    assert main(["--json", "request", str(root), PROMOTED_ID, "essay", "Prepare a fake essay."]) == 0
    cli_result = json.loads(capsys.readouterr().out)
    assert (root / cli_result["request_path"] / "request.json").is_file()


def test_request_requires_a_board_record(tmp_path):
    root = seeded_workspace(tmp_path)
    with pytest.raises(WorkspaceStateError, match="not on the private board"):
        request_for_opportunity(root, "opp_" + "0" * 32, "resume", "Synthetic request")
    with pytest.raises(WorkspaceStateError, match="stable opportunity ID"):
        request_for_opportunity(root, "../escape", "resume", "Synthetic request")
    assert not (root / "applications" / ("opp_" + "0" * 32)).exists()


def test_dashboard_creates_manual_request_and_shows_response_states(tmp_path):
    root = seeded_workspace(tmp_path)
    with dashboard(root) as (server, url):
        form = {
            "token": server.form_token,
            "item": PROMOTED_ID,
            "view": "active",
            "action": "application-request",
            "artifact_type": "short-answer",
            "request_text": "Write a synthetic short answer using cited private facts.",
            "references": "sources/synthetic-project.md",
        }
        response = post(url, form)
        assert response.status == 303
        assert "request=" in response.headers["Location"]
        requests = requests_for_opportunity(root, PROMOTED_ID)
        assert len(requests) == 1
        page = urlopen(url + response.headers["Location"]).read().decode()
        assert "Manual request created at" in page
        assert requests[0]["path"] in page
        assert "Awaiting agent response" in page

        folder = root / requests[0]["path"]
        (folder / "response.json").write_text("{invalid", encoding="utf-8")
        page = urlopen(url + f"/?view=active&item={PROMOTED_ID}").read().decode()
        assert "Response needs correction" in page
        (folder / "drafts" / "answer.txt").write_text("A simple prototype.\n", encoding="utf-8")
        draft = {
            "schema_version": "1.0",
            "request_id": requests[0]["request_id"],
            "status": "drafted",
            "artifacts": [{"path": "drafts/answer.txt", "kind": "draft"}],
            "source_refs": ["sources/synthetic-project.md"],
            "notes": "Fictional handoff, not a submission.",
            "custom": {},
        }
        (folder / "response.json").write_text(json.dumps(draft), encoding="utf-8")
        page = urlopen(url + f"/?view=active&item={PROMOTED_ID}").read().decode()
        assert "Draft available" in page
