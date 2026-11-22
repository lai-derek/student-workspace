"""Application handoffs for board opportunities, built on student-workspace."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from student_workspace.applications import create_application_request, list_application_requests
from student_workspace.state import WorkspaceStateError

from .board import list_workspace_board
from .review import OPPORTUNITY_ID


def opportunity_target(root: Path, opportunity_id: str) -> dict[str, Any]:
    """The board record as a student-workspace target descriptor."""
    if not OPPORTUNITY_ID.fullmatch(opportunity_id):
        raise WorkspaceStateError("opportunity_id must be a stable opportunity ID")
    matches = list_workspace_board(root, view="all", search=opportunity_id, limit=200)["items"]
    item = next((value for value in matches if value["opportunity_id"] == opportunity_id), None)
    if item is None:
        raise WorkspaceStateError(f"{opportunity_id} is not on the private board")
    return {**item, "kind": "opportunity", "id": opportunity_id, "url": None}


def application_folder(opportunity_id: str) -> str:
    if not OPPORTUNITY_ID.fullmatch(opportunity_id):
        raise WorkspaceStateError("opportunity_id must be a stable opportunity ID")
    return f"applications/{opportunity_id}"


def request_for_opportunity(
    root: Path,
    opportunity_id: str,
    artifact_type: str,
    request_text: str,
    *,
    references: tuple[str, ...] = (),
) -> dict[str, Any]:
    """Create a handoff in `applications/<opportunity_id>/` with the board snapshot."""
    return create_application_request(
        root,
        opportunity_target(root, opportunity_id),
        artifact_type,
        request_text,
        application_folder=application_folder(opportunity_id),
        references=references,
    )


def requests_for_opportunity(root: Path, opportunity_id: str) -> list[dict[str, Any]]:
    return list_application_requests(root, application_folder(opportunity_id))
