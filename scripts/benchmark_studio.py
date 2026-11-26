"""Benchmark the Application Studio against Phase 1's success measure.

    python scripts/benchmark_studio.py [--tex RESUME.tex] [--edits 300] [--output report.md]

It starts the real app server on 127.0.0.1 in a throwaway workspace, imports a
Jake's-style resume (the synthetic test fixture unless --tex is given), and
talks to it over HTTP the way the browser does. It measures:

- typesetting alone: cold and warm Typst compiles for each template;
- the structural-edit session: 15 edits like those in a real tailoring session
  (reorder, hide, reword, pick a variant, fit the page), each timed as the
  change request plus the preview the interface then loads;
- endurance: many edits in a row (time per edit and the server's memory);
- the end of the session: export, a byte-for-byte check that the PDF matches its
  source, and the parse check.

Nothing is written outside the throwaway workspace. Run it from a Python
environment with student-workspace installed (pip install -e packages/student-workspace).
"""

from __future__ import annotations

import argparse
import base64
import http.client
import json
import os
import platform
import socket
import statistics
import sys
import tempfile
import threading
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

import uvicorn

from student_workspace.studio.render import Renderer, typst_version
from student_workspace.studio.store import TEMPLATES, Studio
from student_workspace.web.app import create_app
from student_workspace.workspace import initialize_workspace

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "packages" / "student-workspace" / "tests" / "fixtures" / "studio" / "jake-resume.tex"
TOKEN = "benchmark-token"


def stats(samples: list[float]) -> dict[str, float]:
    ordered = sorted(samples)
    return {
        "n": len(ordered),
        "median_ms": round(statistics.median(ordered), 1),
        "p95_ms": round(ordered[min(len(ordered) - 1, int(len(ordered) * 0.95))], 1),
        "max_ms": round(ordered[-1], 1),
    }


class Client:
    """A minimal HTTP client that behaves like the browser: session cookie, write header."""

    def __init__(self, port: int) -> None:
        self.port = port
        self.conn = http.client.HTTPConnection("127.0.0.1", port, timeout=60)
        status, headers, _ = self.raw("GET", f"/api/session/start?token={TOKEN}")
        assert status == 303, status
        self.cookie = headers["set-cookie"].split(";", 1)[0]

    def raw(self, method: str, path: str, body: Any = None) -> tuple[int, dict[str, str], bytes]:
        headers = {"Host": f"127.0.0.1:{self.port}"}
        if getattr(self, "cookie", None):
            headers["Cookie"] = self.cookie
        payload = None
        if method == "POST":
            payload = json.dumps(body or {}).encode()
            headers.update(
                {
                    "Content-Type": "application/json",
                    "Origin": f"http://127.0.0.1:{self.port}",
                    "X-Student-Workspace": "1",
                }
            )
        self.conn.request(method, path, body=payload, headers=headers)
        response = self.conn.getresponse()
        data = response.read()
        return response.status, {k.lower(): v for k, v in response.getheaders()}, data

    def call(self, method: str, path: str, body: Any = None) -> Any:
        status, _headers, data = self.raw(method, f"/api/studio{path}", body)
        if status != 200:
            raise RuntimeError(f"{method} {path}: {status} {data[:200]!r}")
        return json.loads(data)


def start_server(root: Path) -> tuple[uvicorn.Server, threading.Thread, int]:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(create_app(root, TOKEN, port=port), log_level="warning"))
    thread = threading.Thread(target=server.run, kwargs={"sockets": [sock]}, daemon=True)
    thread.start()
    while not server.started:
        time.sleep(0.02)
    return server, thread, port


def rss_mb() -> float | None:
    try:
        import psutil  # optional
    except ImportError:
        return None
    return round(psutil.Process().memory_info().rss / 2**20, 1)


def typesetting(data: dict[str, Any], runs: int = 20) -> dict[str, Any]:
    result = {}
    for template in TEMPLATES:
        start = time.perf_counter()
        renderer = Renderer()
        renderer.render(data, template)
        cold = (time.perf_counter() - start) * 1000
        warm = []
        for i in range(runs):
            changed = json.loads(json.dumps(data))
            changed["sections"][0]["entries"][0]["title"] += f" {i}"  # a real change each time
            start = time.perf_counter()
            renderer.render(changed, template)
            warm.append((time.perf_counter() - start) * 1000)
        result[template] = {"cold_ms": round(cold, 1), "after_edit": stats(warm)}
    return result


def session_edits(client: Client, vid: str) -> list[tuple[str, Callable[[dict[str, Any]], dict[str, Any]]]]:
    """Fifteen structural edits of the kinds that each took an AI turn in the motivating session."""

    def bullets(v: dict[str, Any]) -> list[dict[str, Any]]:
        return [b for s in v["sections"] for e in s["entries"] for b in e["bullets"]]

    def entries(v: dict[str, Any]) -> list[dict[str, Any]]:
        return [e for s in v["sections"] for e in s["entries"]]

    def post(path: str, body: Any = None) -> dict[str, Any]:
        return client.call("POST", f"/versions/{vid}{path}", body)

    def move(kind: str, item: dict[str, Any], position: int) -> dict[str, Any]:
        return post("/move", {"kind": kind, "id": item["id"], "position": position})

    def hide(item: dict[str, Any], hidden: bool) -> dict[str, Any]:
        return post("/hide", {"kind": "bullet", "id": item["id"], "hidden": hidden})

    def edit(item: dict[str, Any], text: str) -> dict[str, Any]:
        return post(f"/bullets/{item['id']}/edit", {"text": text})

    def pick(item: dict[str, Any]) -> dict[str, Any]:
        return post(f"/bullets/{item['id']}/variant", {"variant_id": item["variants"][0]["id"]})

    skills_line = {"label": "Tools", "value": "Git, Typst"}
    return [
        ("move a bullet up", lambda v: move("bullet", bullets(v)[1], 0)),
        ("reword a bullet", lambda v: edit(bullets(v)[0], bullets(v)[0]["text"] + " Tightened.")),
        ("hide a bullet", lambda v: hide(bullets(v)[-1], True)),
        ("move a section", lambda v: move("section", v["sections"][-1], 1)),
        ("move an entry", lambda v: move("entry", entries(v)[1], 0)),
        ("change entry dates", lambda v: post(f"/entries/{entries(v)[0]['id']}", {"dates": "Expected 2030"})),
        (
            "add a bullet",
            lambda v: post(f"/entries/{entries(v)[2]['id']}/bullets", {"text": "Added a result."}),
        ),
        (
            "add a variant",
            lambda v: post(f"/bullets/{bullets(v)[2]['id']}/variants", {"text": "A shorter one."}),
        ),
        ("pick the variant", lambda v: pick(bullets(v)[2])),
        ("tighten spacing to fit", lambda v: post("/settings", {"spacing": 0.9})),
        ("smaller font", lambda v: post("/settings", {"font_size": 10.25})),
        ("show the hidden bullet", lambda v: hide(bullets(v)[-1], False)),
        ("bold a phrase", lambda v: edit(bullets(v)[1], "**" + bullets(v)[1]["text"].rstrip(".") + "**.")),
        ("edit the skills line", lambda v: post("/skills", [*v["skills"], skills_line])),
        ("remove a bullet", lambda v: post(f"/bullets/{bullets(v)[-1]['id']}/remove")),
    ]


def run(tex_path: Path, endurance: int) -> dict[str, Any]:
    tmp = Path(tempfile.mkdtemp(prefix="studio-bench-"))
    root = tmp / "workspace"
    initialize_workspace(root)
    tex = tex_path.read_text(encoding="utf-8")
    report: dict[str, Any] = {
        "machine": f"{platform.system()} {platform.release()}, {platform.processor() or platform.machine()}",
        "python": sys.version.split()[0],
        "typst": typst_version(),
        "resume": "synthetic test fixture" if tex_path == FIXTURE else "a real resume (content not recorded)",
    }

    start = time.perf_counter()
    server, thread, port = start_server(root)
    report["server_start_ms"] = round((time.perf_counter() - start) * 1000, 1)
    client = Client(port)

    start = time.perf_counter()
    version = client.call(
        "POST", "/resumes", {"application_folder": "applications/benchmark", "name": "", "tex": tex}
    )
    report["import_ms"] = round((time.perf_counter() - start) * 1000, 1)
    vid = version["id"]
    report["resume_size"] = {
        "sections": len(version["sections"]),
        "entries": sum(len(s["entries"]) for s in version["sections"]),
        "bullets": sum(len(e["bullets"]) for s in version["sections"] for e in s["entries"]),
    }

    start = time.perf_counter()
    first = client.call("GET", f"/versions/{vid}/preview")
    report["first_preview_ms"] = round((time.perf_counter() - start) * 1000, 1)
    report["preview_payload_kb"] = round(len(json.dumps(first)) / 1024, 1)

    with Studio(root) as studio:
        report["typesetting"] = typesetting(studio.render_data(vid))

    rows = []
    for name, edit in session_edits(client, vid):
        start = time.perf_counter()
        version = edit(version)
        middle = time.perf_counter()
        preview = client.call("GET", f"/versions/{vid}/preview")
        end = time.perf_counter()
        rows.append(
            {
                "edit": name,
                "change_ms": round((middle - start) * 1000, 1),
                "preview_ms": round((end - middle) * 1000, 1),
                "total_ms": round((end - start) * 1000, 1),
                "pages": preview["pages"],
                "fill": preview["fill"],
            }
        )
    report["session"] = {
        "edits": rows,
        "ai_turns": 0,
        "total_ms": round(sum(r["total_ms"] for r in rows), 1),
        "per_edit": stats([r["total_ms"] for r in rows]),
    }

    start = time.perf_counter()
    exported = client.call("POST", f"/versions/{vid}/export", {"replace": False})
    report["export_ms"] = round((time.perf_counter() - start) * 1000, 1)
    with Studio(root) as studio:
        from student_workspace.studio.export import verify_export

        start = time.perf_counter()
        matches = verify_export(studio, vid)
        report["verify_ms"] = round((time.perf_counter() - start) * 1000, 1)
    pdf = (root / exported["result"]["pdf_path"]).read_bytes()
    report["pdf_matches_source"] = matches
    report["pdf_kb"] = round(len(pdf) / 1024, 1)
    start = time.perf_counter()
    checks = client.call("GET", f"/versions/{vid}/checks")
    report["checks_ms"] = round((time.perf_counter() - start) * 1000, 1)
    report["parse_check"] = {
        "result": checks["parse"]["result"],
        "findings": [f"{f['level']}: {f['message']}" for f in checks["parse"]["findings"]],
    }

    bullet = version["sections"][0]["entries"][0]["bullets"] or [
        b for s in version["sections"] for e in s["entries"] for b in e["bullets"]
    ]
    target = bullet[0]["id"]
    memory_before = rss_mb()
    times = []
    for i in range(endurance):
        start = time.perf_counter()
        client.call("POST", f"/versions/{vid}/bullets/{target}/edit", {"text": f"Endurance edit number {i}."})
        preview = client.call("GET", f"/versions/{vid}/preview")
        times.append((time.perf_counter() - start) * 1000)
        assert base64.b64decode(preview["pdf_base64"]).startswith(b"%PDF")
    report["endurance"] = {
        "edit_plus_preview": stats(times),
        "first_10_median_ms": round(statistics.median(times[:10]), 1),
        "last_10_median_ms": round(statistics.median(times[-10:]), 1),
        "memory_mb_before": memory_before,
        "memory_mb_after": rss_mb(),
    }

    server.should_exit = True
    thread.join(timeout=10)
    return report


def markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Application Studio benchmark",
        "",
        f"Measured on {report['machine']}, Python {report['python']}, Typst {report['typst']}, "
        f"with {report['resume']} ({report['resume_size']['sections']} sections, "
        f"{report['resume_size']['entries']} entries, {report['resume_size']['bullets']} bullets). "
        "Requests go over HTTP to the real server on 127.0.0.1, as the browser's do.",
        "",
        "## Success measure",
        "",
        f"- **Structural edits without AI:** {len(report['session']['edits'])} edits, "
        f"{report['session']['ai_turns']} AI turns, {report['session']['total_ms']:.0f} ms in total "
        f"(median {report['session']['per_edit']['median_ms']} ms per edit including the new preview).",
        f"- **PDF matches its source:** {'yes' if report['pdf_matches_source'] else 'NO'} "
        "(the exported .typ recompiled from disk reproduces the exported PDF byte for byte).",
        f"- **Parse check:** {report['parse_check']['result']}.",
        "",
        "## Edit session (change + preview)",
        "",
        "| Edit | Change | Preview | Total | Pages | Fill |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for row in report["session"]["edits"]:
        lines.append(
            f"| {row['edit']} | {row['change_ms']} ms | {row['preview_ms']} ms | {row['total_ms']} ms "
            f"| {row['pages']} | {round(row['fill'] * 100)}% |"
        )
    lines += [
        "",
        "## Typesetting alone (Typst, in process)",
        "",
        "| Template | First compile | After an edit (median / p95) |",
        "| --- | --- | --- |",
    ]
    for template, t in report["typesetting"].items():
        after = t["after_edit"]
        lines.append(f"| {template} | {t['cold_ms']} ms | {after['median_ms']} / {after['p95_ms']} ms |")
    e = report["endurance"]
    lines += [
        "",
        "## Other operations",
        "",
        "| Operation | Time |",
        "| --- | --- |",
        f"| Server start | {report['server_start_ms']} ms |",
        f"| Import the LaTeX resume | {report['import_ms']} ms |",
        f"| First preview (includes loading fonts) | {report['first_preview_ms']} ms |",
        f"| Export (.typ + .pdf) | {report['export_ms']} ms |",
        f"| Verify export (recompile and compare) | {report['verify_ms']} ms |",
        f"| Screening checks | {report['checks_ms']} ms |",
        "",
        f"Preview response: {report['preview_payload_kb']} KB; exported PDF: {report['pdf_kb']} KB.",
        "",
        "## Endurance",
        "",
        f"{e['edit_plus_preview']['n']} edits in a row, each followed by a preview: median "
        f"{e['edit_plus_preview']['median_ms']} ms, p95 {e['edit_plus_preview']['p95_ms']} ms, "
        f"max {e['edit_plus_preview']['max_ms']} ms (first 10: {e['first_10_median_ms']} ms, last 10: "
        f"{e['last_10_median_ms']} ms).",
    ]
    if e["memory_mb_before"] is not None:
        lines.append(f"Process memory: {e['memory_mb_before']} MB before, {e['memory_mb_after']} MB after.")
    lines += ["", "Parse check findings:", ""] + [f"- {f}" for f in report["parse_check"]["findings"]]
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--tex", type=Path, default=FIXTURE, help="a Jake's-style resume to import")
    parser.add_argument("--edits", type=int, default=300, help="edits in the endurance run")
    parser.add_argument("--output", type=Path, help="write the Markdown report here")
    parser.add_argument("--json", type=Path, help="write the raw measurements here")
    args = parser.parse_args(argv)
    report = run(args.tex.resolve(), args.edits)
    text = markdown(report)
    if args.output:
        args.output.write_text(text, encoding="utf-8")
    if args.json:
        args.json.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(text)
    return 0 if report["pdf_matches_source"] else 1


if __name__ == "__main__":
    os.environ.setdefault("PYTHONUTF8", "1")
    raise SystemExit(main())
