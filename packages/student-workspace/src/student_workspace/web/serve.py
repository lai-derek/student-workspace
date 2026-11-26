"""Start the local app for one workspace and open it in the browser."""

from __future__ import annotations

import secrets
import socket
import webbrowser
from collections.abc import Callable, Iterable
from pathlib import Path

import uvicorn

from ..state import require_workspace
from .app import create_app
from .security import SESSION_START_PATH


def serve(
    root: Path,
    *,
    port: int = 0,
    open_browser: bool = True,
    dev_origins: Iterable[str] = (),
    announce: Callable[[str], None] = print,
) -> None:
    """Run until interrupted. Port 0 lets the system pick a free port."""
    root, _metadata = require_workspace(root)
    # Bind first so the launch URL names the real port, then hand the socket to uvicorn.
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(("127.0.0.1", port))
    actual_port = sock.getsockname()[1]
    token = secrets.token_urlsafe(32)
    app = create_app(root, token, port=actual_port, dev_origins=dev_origins)

    url = f"http://127.0.0.1:{actual_port}{SESSION_START_PATH}?token={token}"
    announce(f"Student Workspace is running for {root}")
    announce(f"Open: {url}")
    announce("Close this window or press Ctrl+C to stop it.")
    if open_browser:
        webbrowser.open(url)

    server = uvicorn.Server(uvicorn.Config(app, log_level="warning", access_log=False))
    server.run(sockets=[sock])
