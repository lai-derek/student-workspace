"""GitHub-hosted structured list adapter (Markdown tables or bullet lists).

endpoint_config:
    url: https://raw.githubusercontent.com/{owner}/{repo}/{branch}/{path}
    format: table | bullets | html_table | sectioned_table
    columns:                     # matched case-insensitively by header
        title: Role
        canonical_url: Link
        organization: Company
        location_text: Location
    link_regex: "(?i)apply"      # optional: pick the link whose text matches (bullets)
"""

from __future__ import annotations

import html
import re
from collections.abc import Callable
from typing import Any

from ..models import AdapterResult, RawOpportunity
from .base import bounded_excerpt, outcome_to_result, register_adapter

_MD_TABLE_ROW = re.compile(r"^\|(.+)\|\s*$")
_LINK = re.compile(r"\[([^\]]*)\]\((https?://[^)\s]+)\)")

_COLUMN_ALIASES = {
    "title": ["title", "role", "position", "job title"],
    "canonical_url": ["link", "application", "apply", "url", "application/link"],
    "organization": ["company", "organization", "org"],
    "location_text": ["location", "office"],
    "season": ["term", "season"],
    "deadline": ["deadline", "due date"],
}

_DEFAULT_COLUMNS = {
    "title": "title",
    "canonical_url": "link",
    "organization": "company",
    "location_text": "location",
    "season": "term",
    "deadline": "deadline",
}


def _map_columns(header_lower: list[str], columns: dict) -> dict[str, int]:
    colmap: dict[str, int] = {}
    for logical, wanted in columns.items():
        candidates = {str(wanted).lower()}
        candidates.update(alias.lower() for alias in _COLUMN_ALIASES.get(logical, []))
        for cand in sorted(candidates):
            if cand in header_lower:
                colmap[logical] = header_lower.index(cand)
                break
    return colmap


@register_adapter("githublist")
class GithubListAdapter:
    name = "githublist"

    def run(self, ctx) -> AdapterResult:  # type: ignore[no-untyped-def]
        cfg = ctx.source.endpoint_config
        url = cfg.get("url")
        if not url:
            return AdapterResult(
                ok=False, state="check-failed", detail="githublist adapter requires endpoint_config.url"
            )
        out = ctx.fetcher.fetch(url)
        if out.not_modified and not out.text:
            # Unchanged upstream but no cached body available.
            return AdapterResult(ok=True, empty_ok=True, http_status=304, detail="not modified")
        # A 304 carries the cached body in out.text; parse it like a normal
        # response so observations continue and closures stay accurate.
        if not out.ok:
            return outcome_to_result(out)
        text = out.text or ""
        fmt = cfg.get("format", "table")
        default_org = cfg.get("organization") or ctx.source.organization
        if fmt == "sectioned_table":
            result = self._parse_sectioned_tables(text, cfg, default_org, ctx.excerpt_chars)
            result.http_status = out.status
            return result
        if fmt == "table":
            records, rows_seen = self._parse_table(text, cfg, default_org)
        elif fmt == "html_table":
            records, rows_seen = self._parse_html_table(text, cfg, default_org)
        else:
            records, rows_seen = self._parse_bullets(text, cfg, default_org)
        empty_ok = bool(records) or rows_seen == 0
        return AdapterResult(
            ok=empty_ok,
            records=records,
            empty_ok=True,
            state="healthy" if empty_ok else "format-changed",
            detail=None if empty_ok else "content present but no recognizable entries",
            http_status=out.status,
        )

    def _parse_table(self, text: str, cfg: dict, default_org: str | None) -> tuple[list[RawOpportunity], int]:
        columns = {**_DEFAULT_COLUMNS, **(cfg.get("columns") or {})}
        header: list[str] | None = None
        colmap: dict[str, int] | None = None
        records: list[RawOpportunity] = []
        rows_seen = 0
        last_organization: str | None = None

        def make_cell(bound_cells: list[str], bound_map: dict[str, int]) -> Callable[[str], str | None]:
            def cell(logical: str) -> str | None:
                idx = bound_map.get(logical)
                if idx is None or idx >= len(bound_cells):
                    return None
                return bound_cells[idx].strip() or None

            return cell

        for line in text.splitlines():
            m = _MD_TABLE_ROW.match(line.strip())
            if not m:
                continue
            cells = [c.strip() for c in m.group(1).split("|")]
            if all(re.fullmatch(r":?-{2,}:?", c) for c in cells):
                continue  # separator row
            rows_seen += 1
            if header is None:
                header = cells
                colmap = _map_columns([c.lower() for c in cells], columns)
                continue
            if not colmap:
                continue
            cell = make_cell(cells, dict(colmap))
            organization = cell("organization")
            if organization and organization != "↳":
                last_organization = organization

            title_raw = cell("title")
            links = _LINK.findall(cell("canonical_url") or "")
            url = links[-1][1] if links else cell("canonical_url")
            if title_raw and url and url.startswith("http"):
                deadline_raw = re.sub(r"<[^>]+>", "", cell("deadline") or "")[:10]
                records.append(
                    RawOpportunity(
                        title=_LINK.sub("", title_raw).strip() or title_raw,
                        canonical_url=url,
                        organization=last_organization or default_org,
                        provider=None,
                        location_text=cell("location_text"),
                        deadline=deadline_raw or None,
                        season=cell("season"),
                    )
                )
        return records, rows_seen

    def _parse_sectioned_tables(
        self, text: str, cfg: dict, default_org: str | None, excerpt_chars: int
    ) -> AdapterResult:
        """Parse independently headed Markdown tables; reject partial coverage.

        Opt-in so existing feeds retain their parsing and candidate identities.
        Community status/date-added text stays in excerpts, never official state
        or employer posted_date. Natural-language deadlines stay source language.
        """
        from bs4 import BeautifulSoup

        aliases = {
            **_COLUMN_ALIASES,
            "title": ["role", "program", "scholarship", "opportunity", "name", "title"],
            "organization": ["organization", "university/organization", "company"],
        }
        columns = {**_DEFAULT_COLUMNS, **(cfg.get("columns") or {})}
        records: list[RawOpportunity] = []
        tables = 0
        lines = text.splitlines()

        def cells(line: str) -> list[str]:
            match = _MD_TABLE_ROW.match(line.strip())
            return [c.strip().replace(r"\|", "|") for c in re.split(r"(?<!\\)\|", match[1])] if match else []

        def plain(value: str) -> str:
            value = _LINK.sub(lambda m: m[1], value)
            if "<" in value:
                return BeautifulSoup(value, "html.parser").get_text(" ", strip=True)
            return html.unescape(value).strip()

        def link(value: str) -> str | None:
            links = _LINK.findall(value)
            if links:
                return links[-1][1]
            if value.startswith(("https://", "http://")):
                return value
            for anchor in BeautifulSoup(value, "html.parser").find_all("a", href=True):
                href = str(anchor["href"])
                if href.startswith(("https://", "http://")):
                    return href
            return None

        def failure(detail: str, state: str = "format-changed") -> AdapterResult:
            return AdapterResult(ok=False, state=state, detail=detail)

        index = 0
        while index + 1 < len(lines):
            header = cells(lines[index])
            separator = cells(lines[index + 1])
            if not header or not separator or not all(re.fullmatch(r":?-{2,}:?", c) for c in separator):
                index += 1
                continue
            tables += 1
            if len(header) != len(separator):
                return failure(f"table {tables}: header/separator width mismatch")
            lowered = [plain(c).lower() for c in header]
            colmap = {}
            for logical, wanted in columns.items():
                names = [str(wanted).lower(), *aliases.get(logical, [])]
                found = next((lowered.index(name) for name in names if name in lowered), None)
                if found is not None:
                    colmap[logical] = found
            if "title" not in colmap or "canonical_url" not in colmap:
                return failure(f"table {tables}: missing title/application columns")
            # The list labels each table by its title column. "Program" and
            # "Scholarship" tables state the job type for every row, which the
            # titles themselves often do not ("Discover", "Career Prep").
            table_engagement = "program" if lowered[colmap["title"]] in {"program", "scholarship"} else None
            last_org = None
            index += 2
            while index < len(lines):
                row = cells(lines[index])
                if not row:
                    break
                if len(row) != len(header):
                    return failure(f"table {tables}, line {index + 1}: row width mismatch")

                def cell(logical: str, bound_row=row, bound_map=colmap) -> str:
                    return bound_row[bound_map[logical]] if logical in bound_map else ""

                title = plain(cell("title"))
                url = link(cell("canonical_url"))
                if not title or not url:
                    if cfg.get("allow_unlinked_rows") and title and not url:
                        index += 1
                        continue
                    return failure(f"table {tables}, line {index + 1}: missing title/application link")
                org = plain(cell("organization"))
                if org and org != "↳":
                    last_org = org
                # Keep labels and eligibility language even when a title is long.
                details = "\n".join(
                    f"{plain(label)}: {plain(value)}"
                    for position, (label, value) in enumerate(zip(header, row, strict=True))
                    if value and (position != colmap["canonical_url"] or position == colmap["title"])
                )
                deadline = plain(cell("deadline"))
                records.append(
                    RawOpportunity(
                        title=bounded_excerpt(title, 240) or title,
                        canonical_url=url,
                        organization=last_org or default_org,
                        location_text=plain(cell("location_text")) or None,
                        deadline=deadline if re.fullmatch(r"\d{4}-\d{2}-\d{2}", deadline) else None,
                        requirements_text=bounded_excerpt(details, 2400),
                        description_excerpt=bounded_excerpt(details, excerpt_chars),
                        season=plain(cell("season")) or None,
                        engagement_type=table_engagement,
                    )
                )
                if len(records) > cfg.get("max_results", 1000):
                    return failure("sectioned tables exceeded max_results", "coverage-warning")
                index += 1
        if not tables:
            return failure("no Markdown tables with header separators found")
        if "expected_tables" in cfg and tables != cfg["expected_tables"]:
            return failure(f"expected {cfg['expected_tables']} tables, found {tables}", "coverage-warning")
        if len(records) < cfg.get("min_results", 0):
            return failure("sectioned tables below min_results", "coverage-warning")
        return AdapterResult(ok=True, records=records, empty_ok=not records)

    def _parse_html_table(
        self, text: str, cfg: dict, default_org: str | None
    ) -> tuple[list[RawOpportunity], int]:
        """Parse simple HTML <table> markup embedded in GitHub READMEs."""
        from bs4 import BeautifulSoup

        columns = {**_DEFAULT_COLUMNS, **(cfg.get("columns") or {})}
        soup = BeautifulSoup(text, "html.parser")
        rows_seen = 0
        records: list[RawOpportunity] = []
        for table in soup.find_all("table"):
            header_cells = [th.get_text(strip=True).lower() for th in table.find_all("th")]
            if not header_cells:
                continue
            colmap = _map_columns(header_cells, columns)
            if not colmap:
                continue
            last_organization: str | None = None
            body = table.find("tbody") or table
            for tr in body.find_all("tr"):
                row_cells = list(tr.find_all("td"))
                if not row_cells:
                    continue
                rows_seen += 1

                bound_cells = tuple(row_cells)
                bound_map = dict(colmap)

                def cell(logical: str, _cells=bound_cells, _map_d=bound_map) -> str | None:
                    idx = _map_d.get(logical)
                    if idx is None or idx >= len(_cells):
                        return None
                    return _cells[idx].get_text(strip=True) or None

                def link(logical: str, _cells=bound_cells, _map_d=bound_map, _cell=cell) -> str | None:
                    idx = _map_d.get(logical)
                    if idx is None or idx >= len(_cells):
                        return None
                    anchor = _cells[idx].find("a")
                    if anchor and anchor.get("href"):
                        return str(anchor["href"])
                    text_val = _cell(logical)
                    return text_val if text_val and text_val.startswith("http") else None

                organization = cell("organization")
                if organization and organization != "↳":
                    last_organization = organization
                title = cell("title")
                url = link("canonical_url")
                if not title or not url:
                    continue
                records.append(
                    RawOpportunity(
                        title=title,
                        canonical_url=url,
                        organization=last_organization or default_org,
                        provider=None,
                        location_text=cell("location_text"),
                        season=cell("season"),
                    )
                )
        return records, rows_seen

    def _parse_bullets(
        self, text: str, cfg: dict, default_org: str | None
    ) -> tuple[list[RawOpportunity], int]:
        link_regex: Any = cfg.get("link_regex")
        records: list[RawOpportunity] = []
        rows_seen = 0
        for line in text.splitlines():
            stripped = line.strip()
            if not stripped.startswith(("-", "*")):
                continue
            links = _LINK.findall(stripped)
            if not links:
                continue
            rows_seen += 1
            chosen = links[0]
            if link_regex:
                for link_text, href in links:
                    if re.search(link_regex, link_text):
                        chosen = (link_text, href)
                        break
            title = _LINK.sub("", stripped).strip(" -–—:")
            title = re.split(r"\s+[–—-]\s+", title)[0].strip()
            if chosen[1].startswith("http"):
                records.append(
                    RawOpportunity(
                        title=title or chosen[0], canonical_url=chosen[1], organization=default_org
                    )
                )
        return records, rows_seen
