"""Inline markup in resume text, and typographic quotes and dashes.

Students type `**bold**`, `*italic*` and `[link text](https://...)`; a backslash
makes the next character literal. Text becomes a list of segments
`{text, bold, italic, url}` that the Typst templates insert as plain text, so
nothing a student types is ever run as Typst code.
"""

from __future__ import annotations

import re
from typing import Any

ALLOWED_SCHEMES = ("http://", "https://", "mailto:")
_LINK = re.compile(r"\[([^\]]+)\]\(([^)\s]+)\)")


def smarten(text: str) -> str:
    """`--` and `---` become en and em dashes; straight quotes become curly."""
    text = text.replace("---", "—").replace("--", "–")
    out: list[str] = []
    for i, ch in enumerate(text):
        prev = text[i - 1] if i else " "
        opening = prev.isspace() or prev in "([{–—/"
        if ch == '"':
            out.append("“" if opening else "”")
        elif ch == "'":
            out.append("‘" if opening else "’")
        else:
            out.append(ch)
    return "".join(out)


def _flanked(text: str, start: int, end: int) -> bool:
    """Emphasis must not start or end with a space, so `2 * 3 * 4` stays literal."""
    return not text[start].isspace() and not text[end - 1].isspace()


def segments(text: str) -> list[dict[str, Any]]:
    """Parse markup into segments; unmatched markers stay as typed."""
    result: list[dict[str, Any]] = []

    def emit(chunk: str, bold: bool, italic: bool, url: str | None) -> None:
        if chunk:
            result.append({"text": smarten(chunk), "bold": bold, "italic": italic, "url": url})

    def parse(chunk: str, bold: bool, italic: bool, url: str | None) -> None:
        buf = ""
        i = 0
        while i < len(chunk):
            ch = chunk[i]
            if ch == "\\" and i + 1 < len(chunk):
                buf += chunk[i + 1]
                i += 2
                continue
            if url is None and ch == "[":
                match = _LINK.match(chunk, i)
                if match and match.group(2).startswith(ALLOWED_SCHEMES):
                    emit(buf, bold, italic, url)
                    buf = ""
                    parse(match.group(1), bold, italic, match.group(2))
                    i = match.end()
                    continue
            if chunk.startswith("**", i):
                end = chunk.find("**", i + 2)
                if end > i + 2 and _flanked(chunk, i + 2, end):
                    emit(buf, bold, italic, url)
                    buf = ""
                    parse(chunk[i + 2 : end], True, italic, url)
                    i = end + 2
                else:
                    buf += "**"
                    i += 2
                continue
            if ch == "*":
                end = chunk.find("*", i + 1)
                if end > i + 1 and not chunk.startswith("**", end) and _flanked(chunk, i + 1, end):
                    emit(buf, bold, italic, url)
                    buf = ""
                    parse(chunk[i + 1 : end], bold, True, url)
                    i = end + 1
                    continue
            buf += ch
            i += 1
        emit(buf, bold, italic, url)

    parse(text, False, False, None)
    return result


def plain(text: str) -> str:
    """What a reader (or a resume parser) sees: markup removed, typography applied."""
    return "".join(segment["text"] for segment in segments(text))
