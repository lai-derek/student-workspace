"""Import an existing Jake's-style LaTeX resume and an evidence-matrix table.

Reads the macros Jake's Resume uses (`\\resumeSubheading`, `\\resumeProjectHeading`,
`\\resumeItem`, `\\section`, a header made with `\\resumeHeader` or a `center`
block, and a skills section of `\\textbf{Label:} values` lines). Inline LaTeX
(bold, italics, links, escaped characters) becomes the studio's markup. Anything
else is kept as plain text, so check the imported version once in the studio.
"""

from __future__ import annotations

import re
from datetime import date
from pathlib import Path
from typing import Any

from .store import Studio, StudioError

_DATEISH = re.compile(
    r"\b(19|20)\d\d\b|present|expected|current|\b(jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)\b"
    r"|\b(spring|summer|fall|autumn|winter)\b",
    re.IGNORECASE,
)
_SEPARATORS = re.compile(r"\\textbar\{\}|\\textbar\b|\$\|\$")
_SECTION_KINDS = (
    ("education", "education"),
    ("project", "project"),
    ("experience", "experience"),
    ("employment", "experience"),
    ("work", "experience"),
    ("internship", "experience"),
    ("research", "experience"),
    ("leadership", "leadership"),
    ("activit", "leadership"),
    ("involvement", "leadership"),
    ("volunteer", "leadership"),
)


def _group(text: str, i: int) -> tuple[str, int]:
    """The contents of the {...} group starting at or after i (whitespace skipped), and the index after it."""
    while i < len(text) and text[i] in " \t\r\n":
        i += 1
    if i >= len(text) or text[i] != "{":
        raise StudioError(f"expected '{{' near: {text[i : i + 40]!r}")
    depth = 0
    for j in range(i, len(text)):
        ch = text[j]
        if ch == "\\":
            continue
        if ch == "{" and (j == 0 or text[j - 1] != "\\"):
            depth += 1
        elif ch == "}" and text[j - 1] != "\\":
            depth -= 1
            if depth == 0:
                return text[i + 1 : j], j + 1
    raise StudioError("unbalanced braces in the LaTeX source")


def _replace_macro(text: str, name: str, nargs: int, build: Any) -> str:
    pattern = re.compile(r"\\" + name + r"(?![A-Za-z])")
    while True:
        match = pattern.search(text)
        if not match:
            return text
        args, j = [], match.end()
        try:
            for _ in range(nargs):
                arg, j = _group(text, j)
                args.append(arg)
        except StudioError:
            text = text[: match.start()] + text[match.end() :]
            continue
        text = text[: match.start()] + build(*args) + text[j:]


def to_markup(latex: str) -> str:
    """Inline LaTeX to studio markup: bold, italics, links and escaped characters."""
    s = latex
    for name in ("resumeLink", "href"):
        s = _replace_macro(s, name, 2, lambda url, label: f"[{to_markup(label)}]({url.strip()})")
    s = _replace_macro(s, "textbf", 1, lambda x: f"**{x}**")
    for name in ("textit", "emph"):
        s = _replace_macro(s, name, 1, lambda x: f"*{x}*")
    for name in ("underline", "textnormal", "mbox", "small", "scshape"):
        s = _replace_macro(s, name, 1, lambda x: x)
    for name in ("raisebox", "vspace", "hspace", r"vspace\*", r"hspace\*"):
        s = _replace_macro(s, name, 1, lambda _x: "")  # layout commands: drop with their argument
    # A control word swallows the spaces after it in TeX: it\textquotesingle s -> it's.
    s = re.sub(r"\\textquotesingle(\{\}|\s*)", "'", s)
    replacements = [
        (r"\textbar{}", "|"),
        (r"\textbar", "|"),
        ("$|$", "|"),
        (r"\$", "$"),
        (r"\&", "&"),
        (r"\%", "%"),
        (r"\#", "#"),
        (r"\_", "_"),
        (r"\\", " "),
        (r"\newline", " "),
        (r"\hfill", " "),
        ("``", '"'),
        ("''", '"'),
        ("~", "\u00a0"),
    ]
    for old, new in replacements:
        s = s.replace(old, new)
    s = re.sub(r"\\(Huge|huge|LARGE|Large|large|small|footnotesize|scshape|bfseries|itshape)\b", "", s)
    s = re.sub(r"\\[A-Za-z]+\*?", "", s)  # any other macro name: drop it, keep its text
    s = s.replace("{", "").replace("}", "")
    return re.sub(r"[ \t\r\n]+", " ", s).strip()


def _unwrap(latex: str, *names: str) -> str:
    """`\\textbf{X}` -> `X` when the whole value is one wrapper (templates style titles themselves)."""
    s = latex.strip()
    for name in names:
        prefix = "\\" + name
        if s.startswith(prefix):
            try:
                inner, end = _group(s, len(prefix))
            except StudioError:
                continue
            if not s[end:].strip():
                return _unwrap(inner, *names)
    return s


def _split_top(latex: str) -> list[str]:
    """Split on | separators that aren't inside braces."""
    parts, depth, start, i = [], 0, 0, 0
    while i < len(latex):
        if latex[i] == "{" and (i == 0 or latex[i - 1] != "\\"):
            depth += 1
        elif latex[i] == "}" and latex[i - 1] != "\\":
            depth -= 1
        elif depth == 0:
            match = _SEPARATORS.match(latex, i)
            if match:
                parts.append(latex[start:i])
                start = i = match.end()
                continue
        i += 1
    parts.append(latex[start:])
    return [p for p in (part.strip() for part in parts) if p]


def _link_and_label(latex: str) -> tuple[str | None, str]:
    for name in ("resumeLink", "href"):
        match = re.search(r"\\" + name + r"(?![A-Za-z])", latex)
        if match:
            url, j = _group(latex, match.end())
            label, _ = _group(latex, j)
            return url.strip(), _unwrap(label, "textbf", "underline")
    return None, latex


def _kind(title: str) -> str:
    lowered = title.lower()
    for word, kind in _SECTION_KINDS:
        if word in lowered:
            return kind
    return "other"


def parse_resume(tex: str) -> dict[str, Any]:
    """The resume's structure as plain data (no database), for review or import."""
    start, end = tex.find("\\begin{document}"), tex.find("\\end{document}")
    body = tex[start + len("\\begin{document}") : end if end != -1 else None] if start != -1 else tex
    body = re.sub(r"(?<!\\)%.*", "", body)  # comments
    result: dict[str, Any] = {"name": "", "contact": [], "sections": [], "skills": []}
    section: dict[str, Any] | None = None
    entry: dict[str, Any] | None = None

    def contact_items(latex: str) -> list[dict[str, Any]]:
        items = []
        for part in _split_top(latex.replace("\\\\", " ")):
            url, label = _link_and_label(part)
            text = to_markup(_unwrap(label, "underline"))
            if text:
                items.append({"text": text, "url": url})
        return items

    def add_entry(new: dict[str, Any]) -> dict[str, Any]:
        nonlocal section
        if section is None:
            section = {"title": "Experience", "kind": "experience", "entries": []}
            result["sections"].append(section)
        new.setdefault("bullets", [])
        section["entries"].append(new)
        return new

    i = 0
    while i < len(body):
        if body[i] != "\\":
            i += 1
            continue
        rest = body[i:]
        if rest.startswith("\\resumeHeader"):
            name, j = _group(body, i + len("\\resumeHeader"))
            contact, i = _group(body, j)
            result["name"] = to_markup(name)
            result["contact"] = contact_items(contact)
        elif rest.startswith("\\begin{center}") and not result["name"]:
            close = body.find("\\end{center}", i)
            block = body[i + len("\\begin{center}") : close]
            lines = [line for line in re.split(r"\\\\", block) if line.strip()]
            if lines:
                result["name"] = to_markup(_unwrap(lines[0], "textbf"))
                result["contact"] = contact_items(" ".join(lines[1:]))
            i = close + len("\\end{center}") if close != -1 else len(body)
        elif rest.startswith("\\section"):
            title, i = _group(body, i + len("\\section"))
            title = to_markup(title)
            entry = None
            if "skill" in title.lower():
                section = None
                result["skills_title"] = title
                i = _parse_skills(body, i, result["skills"])
            else:
                section = {"title": title, "kind": _kind(title), "entries": []}
                result["sections"].append(section)
        elif rest.startswith("\\resumeSubheading") and not rest.startswith("\\resumeSubHeadingList"):
            args, j = [], i + len("\\resumeSubheading")
            for _ in range(4):
                arg, j = _group(body, j)
                args.append(_unwrap(arg, "textit", "emph", "textbf"))
            i = j
            title, b, subtitle, d = (to_markup(a) for a in args)
            url, label = _link_and_label(args[0])
            if url:
                title = to_markup(label)
            dates_first = bool(_DATEISH.search(b)) and not _DATEISH.search(d)
            entry = add_entry(
                {
                    "title": title,
                    "url": url,
                    "subtitle": subtitle,
                    "dates": b if dates_first else d,
                    "location": d if dates_first else b,
                }
            )
        elif rest.startswith("\\resumeProjectHeading"):
            heading, j = _group(body, i + len("\\resumeProjectHeading"))
            dates, i = _group(body, j)
            parts = _split_top(heading)
            url, label = _link_and_label(parts[0] if parts else heading)
            tech = " | ".join(to_markup(_unwrap(p, "textit", "emph")) for p in parts[1:])
            entry = add_entry(
                {
                    "title": to_markup(_unwrap(label, "textbf")),
                    "url": url,
                    "tech": tech,
                    "dates": to_markup(dates),
                    "kind": "project",
                }
            )
        elif rest.startswith("\\resumeItem") and not rest.startswith("\\resumeItemList"):
            text, i = _group(body, i + len("\\resumeItem"))
            if entry is not None and to_markup(text):
                entry["bullets"].append(to_markup(text))
        elif rest.startswith("\\newline") and entry is not None:
            j = i + len("\\newline")
            line_end = body.find("\n", j)
            line = body[j : line_end if line_end != -1 else None]
            entry["note"] = to_markup(line)
            i = line_end if line_end != -1 else len(body)
        elif re.match(r"\\item(?![A-Za-z])", rest) and section is not None:
            line_end = body.find("\n", i)
            line = body[i + len("\\item") : line_end if line_end != -1 else None]
            left, _, right = line.partition("\\hfill")
            parts = _split_top(left)
            if parts:
                url, label = _link_and_label(parts[0])
                entry = add_entry(
                    {
                        "title": to_markup(_unwrap(label, "textbf")),
                        "url": url,
                        "details": " | ".join(to_markup(p) for p in parts[1:]),
                        "dates": to_markup(right),
                    }
                )
            i = line_end if line_end != -1 else len(body)
        else:
            i += 1
    if not result["name"]:
        raise StudioError("couldn't find the resume's name (\\resumeHeader or a center block)")
    return result


def _parse_skills(body: str, i: int, skills: list[dict[str, str]]) -> int:
    """Read `\\textbf{Label:} values` lines until the next section or the end."""
    stop = body.find("\\section", i)
    stop = len(body) if stop == -1 else stop
    j = i
    while True:
        match = re.compile(r"\\textbf(?![A-Za-z])").search(body, j, stop)
        if not match:
            return stop
        label, k = _group(body, match.end())
        rest = body[k:stop].lstrip()
        if rest.startswith("{"):  # original Jake's: \textbf{Languages}{: Java, Python}
            value, k = _group(body, k)
        else:
            nxt = re.compile(r"\\\\|\\textbf(?![A-Za-z])|\n\s*\n").search(body, k, stop)
            end = nxt.start() if nxt else stop
            value, k = body[k:end], end
        label_text = to_markup(label).rstrip(":").strip()
        value_text = to_markup(value).lstrip(":").strip()
        if label_text and value_text:
            skills.append({"label": label_text, "value": value_text})
        j = max(k, match.end())


def import_resume(
    studio: Studio,
    application_folder: str,
    tex: str,
    *,
    template: str = "jake",
    day: date | None = None,
) -> dict[str, Any]:
    """Create a resume (and library entries and bullets) from a LaTeX resume."""
    parsed = parse_resume(tex)
    resume_id, version_id = studio.create_resume(
        application_folder,
        header={"name": parsed["name"], "contact": parsed["contact"]},
        skills=parsed["skills"],
        template=template,
        day=day,
    )
    library = studio.library()
    reused = created = bullets = 0
    for section in parsed["sections"]:
        if not section["entries"]:
            continue
        section_id = studio.add_section(version_id, section["title"], section["kind"])
        for item in section["entries"]:
            kind = item.pop("kind", section["kind"])
            texts = item.pop("bullets")
            fields = {k: v for k, v in item.items() if v not in (None, "")}
            match = next(
                (
                    e
                    for e in library
                    if e["kind"] == kind
                    and e["title"] == fields["title"]
                    and e["subtitle"] == fields.get("subtitle", "")
                ),
                None,
            )
            if match:
                entry_id = match["id"]
                studio.update_entry(entry_id, **{k: v for k, v in fields.items() if k != "title"})
                reused += 1
            else:
                entry_id = studio.create_entry(kind, **fields)
                created += 1
            studio.add_entry_to_section(section_id, entry_id, with_bullets=False)
            existing = {b["text"]: b["id"] for b in match["bullets"]} if match else {}
            for text in texts:
                if text in existing:
                    studio.include_bullet(version_id, existing[text])
                else:
                    studio.add_bullet(version_id, entry_id, text)
                bullets += 1
    return {
        "resume_id": resume_id,
        "version_id": version_id,
        "sections": sum(1 for s in parsed["sections"] if s["entries"]),
        "entries_created": created,
        "entries_reused": reused,
        "bullets": bullets,
        "skills": len(parsed["skills"]),
    }


def _md_cell(cell: str) -> str:
    cell = re.sub(r"\[([^\]]+)\]\(([^)\s]+)\)", r"\1 (\2)", cell)
    return cell.replace("\\|", "|").strip()


def import_evidence_matrix(studio: Studio, path: Path, *, source_label: str | None = None) -> list[str]:
    """Each row of the markdown table becomes an evidence note (first column = title)."""
    rows = [
        [cell for cell in re.split(r"(?<!\\)\|", line.strip())[1:-1]]
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip().startswith("|")
    ]
    note_ids = []
    for row in rows[1:]:
        if all(set(c.strip()) <= set("-: ") for c in row):
            continue  # the |---| separator row
        cells = [_md_cell(c) for c in row]
        if not cells or not cells[0]:
            continue
        body = "\n".join(c for c in cells[1:] if c)
        note_ids.append(studio.add_evidence(cells[0][:500], body[:5000], source_label or path.name))
    return note_ids
