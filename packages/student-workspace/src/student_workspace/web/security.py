"""Request checks for a server that only this computer's browser should reach.

Binding to 127.0.0.1 keeps other computers out, but not other web pages: any
site open in the browser can try to send requests to localhost. Each request
must therefore pass, in order:

1. Host check: the Host header must name this server (127.0.0.1:PORT or
   localhost:PORT). This blocks DNS rebinding, where an attacker's domain is
   pointed at 127.0.0.1 so the browser treats their page as same-origin.
2. Session check: the browser must present the session cookie. It is set only
   when someone opens the launch URL, which contains a random token printed by
   `student-workspace serve`. The cookie is HttpOnly (page scripts can't read
   it) and SameSite=Strict (other sites' pages don't send it).
3. Origin check, for requests that change something (POST, PUT, PATCH,
   DELETE): the Origin header must be this server, and the request must carry
   the `X-Student-Workspace` header. Other localhost ports count as the same
   site for cookies, so SameSite alone doesn't stop a page served from another
   local port; the custom header also forces a CORS preflight, which this
   server never approves.
"""

from __future__ import annotations

import secrets
from collections.abc import Iterable
from urllib.parse import urlsplit

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import HTMLResponse, JSONResponse, RedirectResponse, Response
from starlette.types import ASGIApp

SESSION_START_PATH = "/api/session/start"
CSRF_HEADER = "X-Student-Workspace"
SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})
CONTENT_SECURITY_POLICY = (
    "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
    "img-src 'self' data: blob:; connect-src 'self'; worker-src 'self' blob:; "
    "object-src 'none'; base-uri 'none'; form-action 'self'; frame-ancestors 'none'"
)
NOT_SIGNED_IN = """<!doctype html><meta charset="utf-8"><title>Student Workspace</title>
<p>Open Student Workspace from its launcher (or the link printed by
<code>student-workspace serve</code>). This page needs that link to sign in.</p>
"""


def cookie_name(port: int) -> str:
    """One cookie per server port, so two workspaces open at once don't collide."""
    return f"sw_session_{port}"


def allowed_hosts(port: int, dev_origins: Iterable[str] = ()) -> frozenset[str]:
    hosts = {f"127.0.0.1:{port}", f"localhost:{port}"}
    hosts.update(urlsplit(origin).netloc for origin in dev_origins)
    return frozenset(hosts)


class LocalGuard(BaseHTTPMiddleware):
    """Applies the three checks above to every request, including static files."""

    def __init__(self, app: ASGIApp, *, token: str, port: int, dev_origins: Iterable[str] = ()) -> None:
        super().__init__(app)
        self.token = token
        self.cookie = cookie_name(port)
        self.hosts = allowed_hosts(port, dev_origins)
        self.origins = frozenset(f"http://{host}" for host in self.hosts)

    def _matches(self, value: str | None) -> bool:
        return value is not None and secrets.compare_digest(value.encode(), self.token.encode())

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        if request.headers.get("host", "") not in self.hosts:
            return JSONResponse({"detail": "unexpected Host header"}, status_code=400)

        if request.url.path == SESSION_START_PATH:
            response = self._start_session(request)
        elif not self._matches(request.cookies.get(self.cookie)):
            if request.url.path.startswith("/api/"):
                response = JSONResponse({"detail": "not signed in"}, status_code=401)
            else:
                response = HTMLResponse(NOT_SIGNED_IN, status_code=401)
        elif request.method not in SAFE_METHODS and not self._same_origin_write(request):
            response = JSONResponse({"detail": "cross-origin request refused"}, status_code=403)
        else:
            response = await call_next(request)

        response.headers["Content-Security-Policy"] = CONTENT_SECURITY_POLICY
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        if request.url.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store"
        return response

    def _start_session(self, request: Request) -> Response:
        if request.method != "GET" or not self._matches(request.query_params.get("token")):
            return JSONResponse({"detail": "invalid or missing token"}, status_code=403)
        # Redirect to a clean URL so the token doesn't stay in the address bar.
        response = RedirectResponse("/", status_code=303)
        response.set_cookie(self.cookie, self.token, httponly=True, samesite="strict", path="/")
        return response

    def _same_origin_write(self, request: Request) -> bool:
        return request.headers.get("origin") in self.origins and request.headers.get(CSRF_HEADER) == "1"
