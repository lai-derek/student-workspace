"""Typesetting with Typst: compile a version, report where each bullet landed, build export source.

Typst runs inside this Python process (the `typst` package). Each template keeps
one compiler alive, which caches work between compiles, so a recompile after a
small edit takes milliseconds. A lock serializes compiles of the same template,
because the app's server handles requests on several threads.
"""

from __future__ import annotations

import json
import threading
from dataclasses import dataclass, field
from importlib.metadata import version as package_version
from pathlib import Path
from typing import Any

import typst

from .markup import segments
from .store import TEMPLATES, StudioError

TEMPLATE_DIR = Path(__file__).parent / "templates"
# Values the templates read as-is; every other string is user text and becomes segments.
_PLAIN_KEYS = frozenset({"id", "url", "kind", "raw", "date"})
_IMPORT_LINE = '#import "common.typ": *'
_DATA_LINE = "#let data = resume-data()"


@dataclass
class Rendered:
    pdf: bytes
    pages: int
    fill: float  # how much of the last page's text area is used (0 to 1)
    page_width: float
    page_height: float
    boxes: dict[str, dict[str, float]]  # id -> {page, x, top, bottom} in points from the page's top left
    warnings: list[str] = field(default_factory=list)


def prepare(data: Any, key: str | None = None) -> Any:
    """Turn user text into segments; keep ids, links, numbers and raw overrides as they are."""
    if isinstance(data, dict):
        return {k: prepare(v, k) for k, v in data.items()}
    if isinstance(data, list):
        return [prepare(v, key) for v in data]
    if isinstance(data, str) and key not in _PLAIN_KEYS:
        return segments(data)
    return data


def typst_version() -> str:
    return package_version("typst")


class Renderer:
    """One per process; thread-safe."""

    def __init__(self) -> None:
        self._compilers: dict[str, typst.Compiler] = {}
        self._locks = {name: threading.Lock() for name in TEMPLATES}

    def render(self, data: dict[str, Any], template: str) -> Rendered:
        if template not in TEMPLATES:
            raise StudioError(f"template must be one of {', '.join(TEMPLATES)}")
        payload = json.dumps(prepare(data), ensure_ascii=False)
        with self._locks[template]:
            compiler = self._compilers.get(template)
            if compiler is None:
                compiler = typst.Compiler(str(TEMPLATE_DIR / f"{template}.typ"), root=str(TEMPLATE_DIR))
                self._compilers[template] = compiler
            try:
                pdf, warnings = compiler.compile_with_warnings(sys_inputs={"data-json": payload})
                raw_positions = compiler.query("<sw-positions>", field="value", one=True)
            except typst.TypstError as exc:
                raise StudioError(f"typesetting failed: {exc.message}") from exc
        assert isinstance(pdf, bytes)
        positions = json.loads(raw_positions)
        return Rendered(
            pdf=pdf,
            warnings=[w.message for w in warnings],
            **layout(positions, data["settings"]["margin"] * 72),
        )


def layout(positions: dict[str, Any], margin: float) -> dict[str, Any]:
    """Boxes per tracked id, and the page-fill measure, from the template's position markers."""
    ends = {item["id"]: item for item in positions["ends"]}
    boxes = {}
    for start in positions["starts"]:
        end = ends.get(start["id"], start)
        boxes[start["id"]] = {
            "page": start["page"],
            "x": start["x"],
            "top": start["y"],
            # The end marker sits on the last line's top; add roughly one line of height.
            "bottom": end["y"] + 13.0 if end["page"] == start["page"] else positions["page-height"] - margin,
        }
    height = positions["page-height"]
    usable = height - 2 * margin
    fill = (positions["end"]["y"] - margin) / usable if usable > 0 else 1.0
    return {
        "pages": positions["pages"],
        "fill": round(max(0.0, min(fill, 1.0)), 3),
        "page_width": positions["page-width"],
        "page_height": height,
        "boxes": boxes,
    }


def _typst_string(text: str) -> str:
    out = []
    for ch in text:
        if ch == "\\":
            out.append("\\\\")
        elif ch == '"':
            out.append('\\"')
        elif ch == "\n":
            out.append("\\n")
        elif ch == "\r":
            out.append("\\r")
        elif ch == "\t":
            out.append("\\t")
        elif ord(ch) < 32:
            out.append(f"\\u{{{ord(ch):x}}}")
        else:
            out.append(ch)
    return '"' + "".join(out) + '"'


def export_source(data: dict[str, Any], template: str) -> str:
    """One self-contained .typ file: the template, its helpers and the data, inlined.

    It compiles on its own (typst compile, or typst.app) to the same resume.
    """
    if template not in TEMPLATES:
        raise StudioError(f"template must be one of {', '.join(TEMPLATES)}")
    common = (TEMPLATE_DIR / "common.typ").read_text(encoding="utf-8")
    body = (TEMPLATE_DIR / f"{template}.typ").read_text(encoding="utf-8")
    if _IMPORT_LINE not in body or _DATA_LINE not in body:
        raise StudioError(f"template {template} is missing its import or data line")
    payload = json.dumps(prepare(data), ensure_ascii=False)
    body = body.replace(_IMPORT_LINE, common, 1).replace(
        _DATA_LINE, f"#let data = json(bytes({_typst_string(payload)}))", 1
    )
    header = (
        f"// Generated by Student Workspace's Application Studio with Typst {typst_version()}.\n"
        "// Edit the resume in the studio; changes made here are detected and not imported.\n\n"
    )
    return (header + body).replace("\r\n", "\n")


def compile_source(source: str) -> bytes:
    """Compile a standalone .typ source (an export) to PDF bytes."""
    try:
        pdf = typst.compile(source.encode("utf-8"))
    except typst.TypstError as exc:
        raise StudioError(f"typesetting failed: {exc.message}") from exc
    assert isinstance(pdf, bytes)
    return pdf
