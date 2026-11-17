"""Manual application handoffs with a caller-supplied target, and read-only checks."""

import json
from pathlib import Path

import jsonschema
import pytest

from student_workspace.application_checks import check_application_request
from student_workspace.applications import (
    create_application_request,
    list_application_requests,
    url_target,
    validate_target,
)
from student_workspace.cli import main
from student_workspace.state import WorkspaceStateError
from student_workspace.workspace import initialize_workspace

ROOT = Path(__file__).parent.parent
SCHEMAS = ROOT / "schemas"
TARGET = {
    "kind": "example-tool",
    "id": "item-1",
    "url": None,
    "title": "Fictional embedded internship",
    "official_url": "https://synthetic.example/official/intern-open",
}
FOLDER = "applications/item-1"


def schema(name):
    return json.loads((SCHEMAS / name).read_text(encoding="utf-8"))


def seeded_workspace(tmp_path):
    root = tmp_path / "workspace"
    initialize_workspace(root)
    (root / "sources" / "synthetic-project.md").write_text(
        "# Synthetic project\nA fictional classroom sensor logger.\n", encoding="utf-8"
    )
    return root


def response_for(result, *, status="drafted"):
    return {
        "schema_version": "1.0",
        "request_id": result["request_id"],
        "status": status,
        "artifacts": [{"path": "drafts/answer.txt", "kind": "draft"}] if status == "drafted" else [],
        "source_refs": ["sources/synthetic-project.md"],
        "notes": "Fictional handoff, not a submission.",
        "custom": {},
    }


def prepared(root):
    result = create_application_request(
        root, TARGET, "short-answer", "Draft a fictional answer.", application_folder=FOLDER
    )
    folder = root / result["request_path"]
    (folder / "drafts/answer.txt").write_text("A simple prototype.\n", encoding="utf-8")
    return result, folder


def write_json(path, value):
    path.write_text(json.dumps(value), encoding="utf-8")


def test_request_files_schema_target_snapshot_and_nonoverwrite(tmp_path):
    root = seeded_workspace(tmp_path)
    result = create_application_request(
        root,
        TARGET,
        "resume",
        "Prepare a fictional resume.",
        application_folder=FOLDER,
        references=("sources/synthetic-project.md",),
    )
    folder = root / result["request_path"]
    assert result["request_path"].startswith(FOLDER + "/requests/req_")
    assert (folder / "drafts").is_dir() and (folder / "revisions").is_dir()
    assert not (folder / "response.json").exists()
    request = json.loads((folder / "request.json").read_text(encoding="utf-8"))
    references = json.loads((folder / "references.json").read_text(encoding="utf-8"))
    jsonschema.validate(request, schema("application-request.schema.json"))
    jsonschema.validate(references, schema("application-references.schema.json"))
    assert request["target"] == {"kind": "example-tool", "id": "item-1", "url": None}
    assert json.loads((folder / "target.json").read_text(encoding="utf-8")) == TARGET
    assert [ref["path"] for ref in references["references"]] == [
        "sources/synthetic-project.md",
        "knowledge/PROFILE.md",
        "knowledge/CATALOG.md",
    ]
    assert "WORKSPACE.md" in (folder / "HANDOFF.md").read_text(encoding="utf-8")
    assert list_application_requests(root, FOLDER)[0]["has_response"] is False

    artifact = folder / "drafts" / "resume.md"
    artifact.write_text("User-edited synthetic resume", encoding="utf-8")
    second = create_application_request(
        root, TARGET, "cover-letter", "Second draft.", application_folder=FOLDER
    )
    assert second["request_path"] != result["request_path"]
    assert artifact.read_text(encoding="utf-8") == "User-edited synthetic resume"


def test_url_request_cli_keeps_existing_folder_content(tmp_path, capsys):
    root = seeded_workspace(tmp_path)
    application = root / "applications/community-workshop"
    application.mkdir(parents=True)
    readme = application / "README.md"
    readme.write_text("User-edited fictional context; preserve this.", encoding="utf-8")
    assert (
        main(
            [
                "--json",
                "apply",
                "request-url",
                str(root),
                "applications/community-workshop",
                "https://synthetic.example/apply",
                "short-answer",
                "Draft an answer using the supplied facts.",
            ]
        )
        == 0
    )
    result = json.loads(capsys.readouterr().out)
    folder = root / result["request_path"]
    request = json.loads((folder / "request.json").read_text())
    jsonschema.validate(
        request, schema("application-request.schema.json"), format_checker=jsonschema.FormatChecker()
    )
    assert request["target"] == {"kind": "url", "id": None, "url": "https://synthetic.example/apply"}
    assert json.loads((folder / "target.json").read_text())["verification"] == "not-checked"
    assert readme.read_text() == "User-edited fictional context; preserve this."
    assert check_application_request(root, result["request_path"])["response_status"] == "awaiting-response"


@pytest.mark.parametrize(
    ("folder", "url"),
    [
        ("../outside", "https://synthetic.example/apply"),
        ("applications/../escape", "https://synthetic.example/apply"),
        ("applications\\example", "https://synthetic.example/apply"),
        ("applications/example", "file:///private"),
        ("applications/example", "https://"),
        ("applications/example", "https://synthetic.example/ space"),
        ("applications/example", "https://synthetic.example:bad/apply"),
    ],
)
def test_url_request_rejects_invalid_inputs_before_writing(tmp_path, folder, url):
    root = seeded_workspace(tmp_path)
    before = set((root / "applications").rglob("*"))
    with pytest.raises(WorkspaceStateError):
        create_application_request(
            root, url_target(url), "essay", "Fictional request", application_folder=folder
        )
    assert set((root / "applications").rglob("*")) == before


@pytest.mark.parametrize(
    "target",
    [
        [],
        {"kind": "Bad Kind", "id": "x", "url": None},
        {"kind": "tool", "id": None, "url": None},
        {"kind": "tool", "id": "", "url": None},
        {"kind": "tool", "id": "x", "url": "ftp://synthetic.example"},
    ],
)
def test_target_descriptor_validation(target):
    with pytest.raises(WorkspaceStateError):
        validate_target(target)


def test_request_rejects_traversal_and_symlink_before_creating_files(tmp_path):
    root = seeded_workspace(tmp_path)
    base = root / FOLDER
    for reference in (
        "../knowledge/PROFILE.md",
        "sources/../knowledge/PROFILE.md",
        "sources\\bad.md",
        "knowledge/missing.md",
    ):
        with pytest.raises(WorkspaceStateError):
            create_application_request(
                root,
                TARGET,
                "resume",
                "Synthetic request",
                application_folder=FOLDER,
                references=(reference,),
            )
    assert not base.exists()
    outside = tmp_path / "outside.md"
    outside.write_text("Private synthetic file", encoding="utf-8")
    try:
        (root / "sources" / "link.md").symlink_to(outside)
    except OSError as exc:
        pytest.skip(f"symlinks unavailable: {exc}")
    with pytest.raises(WorkspaceStateError, match="symlink"):
        create_application_request(
            root,
            TARGET,
            "resume",
            "Synthetic request",
            application_folder=FOLDER,
            references=("sources/link.md",),
        )
    assert not base.exists()


@pytest.mark.parametrize("status", ["drafted", "needs-input"])
def test_valid_response_states_and_cli_are_read_only(tmp_path, capsys, status):
    root = seeded_workspace(tmp_path)
    result, folder = prepared(root)
    write_json(folder / "response.json", response_for(result, status=status))
    before = {p: p.read_bytes() for p in folder.rglob("*") if p.is_file()}
    row = list_application_requests(root, FOLDER)[0]
    assert (row["has_response"], row["response_status"], row["response_errors"]) == (True, status, [])
    assert main(["--json", "apply", "check", str(root), result["request_path"]]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["valid"] is True
    jsonschema.validate(report, schema("application-check-report.schema.json"))
    assert {p: p.read_bytes() for p in folder.rglob("*") if p.is_file()} == before


@pytest.mark.parametrize(
    ("change", "message"),
    [
        (lambda value: value.update(request_id="req_20000101T000000Z_000000000000"), "request_id"),
        (lambda value: value.update(status="submitted"), "status"),
        (lambda value: value.update(artifacts=[]), "at least one"),
        (lambda value: value.update(custom=[]), "types"),
        (lambda value: value.update(unknown=True), "fields"),
        (lambda value: value["artifacts"][0].update(path="drafts/missing.md"), "missing"),
        (lambda value: value["artifacts"][0].update(path="../outside.md"), "path"),
        (lambda value: value["artifacts"][0].update(kind="revision"), "directory"),
        (lambda value: value.update(source_refs=["knowledge/missing.md"]), "source"),
        (lambda value: value.update(source_refs=["sources/../knowledge/PROFILE.md"]), "source"),
        (lambda value: value.update(source_refs=["applications/old-draft.md"]), "source"),
        (lambda value: value.update(source_refs=[8]), "strings"),
    ],
)
def test_invalid_response_does_not_become_a_draft(tmp_path, change, message):
    root = seeded_workspace(tmp_path)
    result, folder = prepared(root)
    response = response_for(result)
    change(response)
    write_json(folder / "response.json", response)
    row = list_application_requests(root, FOLDER)[0]
    assert row["response_status"] == "invalid-response"
    assert message in row["response_errors"][0]
    assert check_application_request(root, result["request_path"])["valid"] is False


def test_field_limits_links_anchors_and_changed_reference_warning(tmp_path, capsys):
    root = seeded_workspace(tmp_path)
    result, folder = prepared(root)
    source = root / "sources/synthetic-project.md"
    source.write_text("# Prototype\n# Prototype\n", encoding="utf-8")
    markdown = folder / "drafts/context.md"
    relative_source = "../../../../../sources/synthetic-project.md"
    markdown.write_text(
        f"[reason]({relative_source}#prototype-1)\n[external](https://synthetic.example/no-fetch)\n",
        encoding="utf-8",
    )
    response = response_for(result)
    response["artifacts"].append({"path": "drafts/context.md", "kind": "draft"})
    response["source_refs"] = ["sources/synthetic-project.md#prototype"]
    write_json(folder / "response.json", response)
    text = "Café marker.\n"
    (folder / "drafts/answer.txt").write_text(text, encoding="utf-8")
    checks = {
        "schema_version": "1.0",
        "fields": [{"path": "drafts/answer.txt", "max_words": 2, "max_characters": len(text)}],
        "custom": {"synthetic": True},
    }
    jsonschema.validate(checks, schema("application-checks.schema.json"))
    write_json(folder / "checks.json", checks)
    report = check_application_request(root, result["request_path"])
    assert report["valid"] is True
    assert report["fields"] == [{"path": "drafts/answer.txt", "words": 2, "characters": len(text)}]
    assert report["local_links_checked"] == 1
    with (root / "knowledge/PROFILE.md").open("a", encoding="utf-8") as handle:
        handle.write("\nA later fictional clarification.\n")
    report = check_application_request(root, result["request_path"])
    assert any("Reference changed" in warning for warning in report["warnings"])
    checks["fields"][0]["max_words"] = 1
    checks["fields"][0]["max_characters"] = len(text) - 1
    write_json(folder / "checks.json", checks)
    assert main(["--json", "apply", "check", str(root), result["request_path"]]) == 1
    report = json.loads(capsys.readouterr().out)
    assert len(report["errors"]) == 2
    markdown.write_text(f"[reason]({relative_source}#nonexistent)\n", encoding="utf-8")
    report = check_application_request(root, result["request_path"])
    assert any("missing Markdown anchor" in error for error in report["errors"])


@pytest.mark.parametrize("link", ["../../../../../sources/missing.md", "../../../../../../outside.md"])
def test_local_links_cannot_be_missing_or_escape_workspace(tmp_path, link):
    root = seeded_workspace(tmp_path)
    result, folder = prepared(root)
    (folder / "drafts/context.md").write_text(f"[link]({link})\n", encoding="utf-8")
    response = response_for(result)
    response["artifacts"] = [{"path": "drafts/context.md", "kind": "draft"}]
    write_json(folder / "response.json", response)
    assert check_application_request(root, result["request_path"])["valid"] is False


@pytest.mark.parametrize("limit", [True, -1, "150"])
def test_limits_schema_and_runtime_reject_invalid_types(tmp_path, limit):
    root = seeded_workspace(tmp_path)
    result, folder = prepared(root)
    write_json(folder / "response.json", response_for(result))
    checks = {
        "schema_version": "1.0",
        "fields": [{"path": "drafts/answer.txt", "max_words": limit}],
        "custom": {},
    }
    assert not jsonschema.Draft202012Validator(schema("application-checks.schema.json")).is_valid(checks)
    write_json(folder / "checks.json", checks)
    assert check_application_request(root, result["request_path"])["valid"] is False


def test_drafted_response_requires_artifact_in_schema(tmp_path):
    root = seeded_workspace(tmp_path)
    result, _folder = prepared(root)
    response = response_for(result)
    response["artifacts"] = []
    validator = jsonschema.Draft202012Validator(schema("application-response.schema.json"))
    assert not validator.is_valid(response)
    response["status"] = "needs-input"
    assert validator.is_valid(response)
