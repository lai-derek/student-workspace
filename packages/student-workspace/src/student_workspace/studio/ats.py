"""Resume screening checks: what a resume parser reads from the PDF, and posting keyword coverage.

Applicant tracking systems extract a PDF's text into fields. They struggle with
text they can't extract cleanly, columns, unusual headings and text outside the
page body. The parse check reads the compiled PDF the way a parser would and
reports problems; it gives no score, because no standard score exists.
"""

from __future__ import annotations

import io
import re
import unicodedata
from collections import Counter
from typing import Any

from pdfminer.high_level import extract_pages
from pdfminer.layout import LTChar, LTTextContainer, LTTextLine
from pypdf import PdfReader

from .markup import plain

LETTER = (612.0, 792.0)
LIGATURES = re.compile("[ﬀ-ﬆ]")
STANDARD_HEADINGS = {
    "education", "experience", "work experience", "professional experience", "research experience",
    "projects", "leadership", "activities", "leadership & activities", "skills", "technical skills",
    "volunteer", "volunteering", "awards", "honors", "certifications", "publications", "coursework",
    "involvement", "employment", "internships", "research",
}  # fmt: skip
_STOP = frozenset(
    {
        "a",
        "an",
        "and",
        "are",
        "as",
        "at",
        "be",
        "by",
        "for",
        "from",
        "has",
        "have",
        "in",
        "into",
        "is",
        "it",
        "its",
        "of",
        "on",
        "or",
        "our",
        "that",
        "the",
        "their",
        "this",
        "to",
        "we",
        "will",
        "with",
        "you",
        "your",
        "who",
        "what",
        "when",
        "where",
        "which",
        "while",
        "within",
        "about",
        "across",
        "after",
        "all",
        "also",
        "any",
        "can",
        "etc",
        "including",
        "other",
        "such",
        "than",
        "them",
        "they",
        "these",
        "those",
        "through",
        "using",
        "via",
        "work",
        "working",
        "team",
        "teams",
        "role",
        "roles",
        "candidate",
        "candidates",
        "position",
        "positions",
        "job",
        "jobs",
        "company",
        "experience",
        "required",
        "preferred",
        "ability",
        "strong",
        "excellent",
        "skills",
        "skill",
        "knowledge",
        "understanding",
        "plus",
        "must",
        "should",
        "may",
        "not",
        "new",
        "year",
        "years",
        "related",
        "relevant",
        "level",
        "based",
        "help",
        "helps",
        "support",
        "supporting",
    }
)


def _norm(text: str) -> str:
    text = unicodedata.normalize("NFKC", text).replace(" ", " ")
    return re.sub(r"\s+", " ", text).strip().lower()


def _finding(level: str, code: str, message: str) -> dict[str, str]:
    return {"level": level, "code": code, "message": message}


def parse_check(pdf: bytes, data: dict[str, Any], *, margin_in: float | None = None) -> dict[str, Any]:
    """Check the PDF against the data it was rendered from. Levels: error, warning, ok."""
    findings: list[dict[str, str]] = []
    reader = PdfReader(io.BytesIO(pdf))
    pages = len(reader.pages)
    page = reader.pages[0]
    size = (round(float(page.mediabox.width)), round(float(page.mediabox.height)))
    text = "\n".join(p.extract_text() or "" for p in reader.pages)
    flat = _norm(text)

    findings.append(
        _finding("ok", "pages", "One page.")
        if pages == 1
        else _finding("warning", "pages", f"{pages} pages. Most student resumes fit on one.")
    )
    if size != LETTER:
        findings.append(_finding("warning", "page-size", f"Page is {size[0]}x{size[1]} pt, not US Letter."))
    if len(flat) < 200:
        findings.append(
            _finding("error", "no-text", "Almost no text can be extracted; a parser would see a blank page.")
        )
    if LIGATURES.search(text):
        findings.append(
            _finding(
                "error", "ligatures", "Some letter pairs extract as single ligature characters (like 'ﬀ')."
            )
        )

    missing = []
    for section in data["sections"]:
        for entry in section["entries"]:
            for value in [entry["title"], *(b["text"] for b in entry["bullets"] if not b.get("raw"))]:
                if _norm(plain(value)) not in flat:
                    missing.append(plain(value)[:60])
    findings.append(
        _finding(
            "error",
            "missing-text",
            f"{len(missing)} item(s) don't extract as written: " + "; ".join(missing[:3]),
        )
        if missing
        else _finding("ok", "text", "Every title and bullet extracts as written.")
    )

    headings = [section["title"] for section in data["sections"]]
    unusual = [h for h in headings if _norm(plain(h)) not in STANDARD_HEADINGS]
    if unusual:
        findings.append(
            _finding(
                "warning",
                "headings",
                "Parsers recognize standard headings best; unusual: " + ", ".join(unusual),
            )
        )
    positions = [flat.find(_norm(plain(h))) for h in headings]
    if -1 in positions or positions != sorted(positions):
        findings.append(_finding("warning", "heading-order", "Section headings don't extract in page order."))

    contact = data.get("contact", [])
    if not any("@" in plain(c["text"]) or (c.get("url") or "").startswith("mailto:") for c in contact):
        findings.append(_finding("warning", "email", "No email address in the header."))
    expected_links = {
        u
        for u in [
            *(c.get("url") for c in contact),
            *(e.get("url") for s in data["sections"] for e in s["entries"]),
        ]
        if u
    }
    found_links = {
        str(a.get_object().get("/A", {}).get("/URI"))
        for p in reader.pages
        for a in (p.get("/Annots") or [])
        if a.get_object().get("/Subtype") == "/Link"
    }
    lost = sorted(expected_links - found_links)
    findings.append(
        _finding(
            "warning", "links", f"{len(lost)} link(s) aren't clickable in the PDF: " + ", ".join(lost[:3])
        )
        if lost
        else _finding("ok", "links", f"All {len(expected_links)} links are clickable.")
    )

    if margin_in is not None:
        outside = _outside_margins(pdf, margin_in * 72)
        if outside:
            findings.append(
                _finding("error", "margins", "Text runs past the page margin: " + ", ".join(outside[:3]))
            )
    worst = "error" if any(f["level"] == "error" for f in findings) else (
        "warning" if any(f["level"] == "warning" for f in findings) else "ok"
    )  # fmt: skip
    return {"result": worst, "pages": pages, "findings": findings, "extracted_text": text}


def _outside_margins(pdf: bytes, margin: float, tolerance: float = 1.0) -> list[str]:
    """Text lines whose characters cross the left or right margin."""
    outside = []
    for layout in extract_pages(io.BytesIO(pdf)):
        width = layout.width
        for element in layout:
            if not isinstance(element, LTTextContainer):
                continue
            for line in element:
                if not isinstance(line, LTTextLine):
                    continue
                # Only visible characters: a line can end in a space that sits past the margin.
                chars = [c for c in line if isinstance(c, LTChar) and c.get_text().strip()]
                if chars and (
                    min(c.x0 for c in chars) < margin - tolerance
                    or max(c.x1 for c in chars) > width - margin + tolerance
                ):
                    outside.append(line.get_text().strip()[:40])
    return outside


def _terms(text: str) -> Counter[str]:
    """Candidate keywords: technical tokens, capitalized names, and repeated two-word phrases."""
    counts: Counter[str] = Counter()
    for match in re.finditer(r"[A-Za-z][A-Za-z0-9+#./-]*[A-Za-z0-9+#]", text):
        token = match.group().strip(".")
        if token.lower() in _STOP or len(token) < 2:
            continue
        technical = bool(re.search(r"[A-Z].*[A-Z]|[0-9+#/]|\.[a-z]", token))
        sentence_start = re.search(r"(^|[.!?:;\n•\-]\s*)$", text[max(0, match.start() - 3) : match.start()])
        if technical or (token[0].isupper() and not sentence_start):
            counts[token] += 1
    words = [w.lower() for w in re.findall(r"[A-Za-z][A-Za-z-]+", text)]
    for a, b in zip(words, words[1:], strict=False):
        if a not in _STOP and b not in _STOP and len(a) > 2 and len(b) > 2:
            counts[f"{a} {b}"] += 1
    return Counter({term: n for term, n in counts.items() if n >= 2 or " " not in term})


def keyword_coverage(
    posting: str, resume_text: str, evidence: list[dict[str, Any]] | None = None, *, limit: int = 40
) -> dict[str, Any]:
    """Which posting terms appear in the resume, and evidence notes that mention the missing ones."""
    if not posting.strip():
        return {"terms": [], "covered": 0, "missing": 0}
    resume = _norm(resume_text)
    rows = []
    seen: set[str] = set()
    for term, count in _terms(posting).most_common():
        key = term.lower()
        if key in seen:
            continue
        seen.add(key)
        pattern = r"(?<![a-z0-9])" + re.escape(key) + r"(?![a-z0-9])"
        covered = re.search(pattern, resume) is not None
        notes = []
        if not covered and evidence:
            notes = [
                {"id": n["id"], "title": n["title"]}
                for n in evidence
                if re.search(pattern, _norm(f"{n['title']} {n.get('body', '')}"))
            ][:3]
        rows.append({"term": term, "count": count, "covered": covered, "evidence": notes})
        if len(rows) >= limit:
            break
    return {
        "terms": rows,
        "covered": sum(1 for r in rows if r["covered"]),
        "missing": sum(1 for r in rows if not r["covered"]),
    }
