"""API routes and static files for the local app.

Routes call the same functions as the command line (for example
`check_workspace`), so the app and the CLI can't disagree about the workspace.
FastAPI publishes the response models in its OpenAPI schema. The React app's
TypeScript types live in frontend/src/api.ts.
"""

from __future__ import annotations

import mimetypes
from collections.abc import Iterable
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from ..check import ERROR, STALE, check_workspace
from ..state import WorkspaceStateError
from ..tools import registered_tools
from .security import LocalGuard
from .studio_api import studio_router

STATIC_DIR = Path(__file__).parent / "static"

# On Windows, Python's mimetypes reads the registry, which can map .js to text/plain;
# browsers refuse to run module scripts served that way.
for _type, _suffix in (("text/javascript", ".js"), ("text/javascript", ".mjs"), ("text/css", ".css")):
    mimetypes.add_type(_type, _suffix)
NOT_BUILT = """<!doctype html><meta charset="utf-8"><title>Student Workspace</title>
<p>The Student Workspace interface is missing. If you installed from source,
build the frontend with <code>npm run build</code> in <code>frontend/</code> and
restart Student Workspace. For a release install, run setup again.</p>
"""

Status = Literal["ok", "stale", "error"]
_STATUS: dict[int, Status] = {0: "ok", STALE: "stale", ERROR: "error"}

# The app is organized by student task. A section appears when its tool is
# registered in the workspace; the others belong to the core and always appear.
_SECTIONS: tuple[tuple[str, str, str | None], ...] = (
    ("home", "Home", None),
    ("applications", "Applications", None),
    ("opportunities", "Opportunities", "opportunity-discovery"),
    ("courses", "Courses", "academic-planning"),
    ("workspace", "Workspace", None),
)


class Section(BaseModel):
    id: str
    label: str
    path: str


class ToolStatus(BaseModel):
    name: str
    version: str | None
    status: Status
    detail: list[str]


class WorkspaceStatus(BaseModel):
    root: str
    status: Literal["current", "stale", "error"]
    findings: list[str]
    tools: list[ToolStatus]


def create_app(root: Path, token: str, *, port: int, dev_origins: Iterable[str] = ()) -> FastAPI:
    """The app for one workspace. `token` is the secret in the launch URL."""
    # No /docs page: FastAPI's docs page loads scripts from a CDN, which the
    # content security policy blocks. The schema itself is served locally.
    app = FastAPI(title="Student Workspace", docs_url=None, redoc_url=None, openapi_url="/api/openapi.json")
    app.add_middleware(LocalGuard, token=token, port=port, dev_origins=tuple(dev_origins))

    @app.exception_handler(WorkspaceStateError)
    async def refused(_request: Request, exc: WorkspaceStateError) -> JSONResponse:
        # The store's messages are written for the student; show them as they are.
        return JSONResponse({"detail": str(exc)}, status_code=400)

    app.include_router(studio_router(root))

    @app.get("/api/sections")
    def sections() -> list[Section]:
        installed = {str(record.get("name")) for record, *_rest in registered_tools(root)}
        return [
            Section(id=key, label=label, path=f"/{key}")
            for key, label, tool in _SECTIONS
            if tool is None or tool in installed
        ]

    @app.get("/api/workspace")
    def workspace() -> WorkspaceStatus:
        # Runs every tool's own check, so this can take a few seconds.
        result = check_workspace(root)
        audit, *tools = result["results"]
        return WorkspaceStatus(
            root=result["workspace"],
            status=result["status"],
            findings=audit["detail"],
            tools=[
                ToolStatus(
                    name=item["name"],
                    version=item.get("version"),
                    status=_STATUS[item["status"]],
                    detail=item["detail"],
                )
                for item in tools
            ],
        )

    _mount_interface(app)
    return app


def _mount_interface(app: FastAPI) -> None:
    """Serve the built React app; any non-API path returns index.html (client-side routing)."""
    index = STATIC_DIR / "index.html"
    if not index.is_file():

        @app.get("/{path:path}", include_in_schema=False)
        def not_built(path: str) -> HTMLResponse:
            _not_an_api_path(path)
            return HTMLResponse(NOT_BUILT)

        return

    app.mount("/assets", StaticFiles(directory=STATIC_DIR / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def interface(path: str) -> FileResponse:
        _not_an_api_path(path)
        return FileResponse(index)


def _not_an_api_path(path: str) -> None:
    if path == "api" or path.startswith("api/"):
        raise HTTPException(status_code=404, detail="no such API route")
