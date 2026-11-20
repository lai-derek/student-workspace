"""Portable presentation views. Formulas include Python-verified cached results."""

from __future__ import annotations

import math
from datetime import datetime
import re
from xml.sax.saxutils import escape

from .planning import (
    recognition_options,
    recognition_summary,
    useful_requirements,
    research_lines,
)

from .totals import total_description

import xlsxwriter
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    LongTable,
    TableStyle,
    PageBreak,
)


def text(value):
    return "" if value is None else str(value)


def plain(value):
    value = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text(value))
    return re.sub(r"^#{1,6}\s+", "", value, flags=re.M)


def goal_summary(value):
    match = re.search(
        r"^## Workload preference\s*\n(.*?)(?=^## |\Z)", value, re.M | re.S
    )
    if match:
        return match[1].strip()
    paragraphs = [
        p.strip()
        for p in value.split("\n\n")
        if p.strip() and not p.strip().startswith("#")
    ]
    return paragraphs[0] if paragraphs else "See the shared goals record."


def rows_for_requirements(data):
    assignments = {r["requirement_id"]: r for r in data.get("assignments", [])}
    result = []
    for row in data.get("requirements", []):
        assignment = assignments.get(row["id"], {})
        result.append(
            [
                row["requirement"],
                assignment.get("units", row.get("units")),
                assignment.get("status", row["status"]),
                assignment.get("course") or row.get("selected_course") or "Unselected",
                assignment.get("term"),
                row.get("prerequisites"),
                row.get("notes", ""),
            ]
        )
    return result


def workbook(ws, destination):
    data, abroad = ws.data, ws.abroad
    # Disable implicit formulas/URLs in source-derived strings.
    with xlsxwriter.Workbook(
        destination, {"strings_to_formulas": False, "strings_to_urls": False}
    ) as book:
        book.set_properties(
            {
                "title": "Academic planning",
                "comments": "Generated from shared workspace records",
            }
        )
        book.set_calc_mode("auto")
        heading = book.add_format(
            {
                "font_name": "Arial",
                "font_size": 17,
                "bold": True,
                "font_color": "#243B53",
            }
        )
        note = book.add_format(
            {
                "font_name": "Arial",
                "font_size": 10,
                "font_color": "#526479",
                "text_wrap": True,
                "valign": "top",
            }
        )
        body = book.add_format(
            {"font_name": "Arial", "font_size": 10, "text_wrap": True, "valign": "top"}
        )
        numeric = book.add_format(
            {
                "font_name": "Arial",
                "font_size": 10,
                "num_format": "0.0",
                "valign": "top",
                "indent": 1,
            }
        )
        date_format = book.add_format(
            {
                "font_name": "Arial",
                "font_size": 10,
                "num_format": "yyyy-mm-dd",
                "valign": "top",
            }
        )
        table_heading = book.add_format(
            {
                "font_name": "Arial",
                "font_size": 10,
                "bold": True,
                "font_color": "#FFFFFF",
                "bg_color": "#243B53",
                "text_wrap": True,
            }
        )
        section = book.add_format(
            {
                "font_name": "Arial",
                "font_size": 10,
                "bold": True,
                "bg_color": "#E8EDF2",
                "text_wrap": True,
                "valign": "top",
            }
        )
        formulas = []

        def sheet(name, title, headers, rows, widths, numeric_column):
            sh = book.add_worksheet(name)
            sh.hide_gridlines(2)
            sh.freeze_panes(5, 0)
            sh.set_landscape()
            sh.fit_to_pages(1, 0)
            sh.repeat_rows(0, 4)
            sh.write_string(0, 0, title, heading)
            sh.set_row(0, 29)
            sh.merge_range(
                1,
                0,
                1,
                len(headers) - 1,
                "Generated view: edit shared YAML/Markdown records and rebuild. Manual output changes are detected.",
                note,
            )
            sh.set_row(1, 33)
            sh.merge_range(
                2,
                0,
                2,
                len(headers) - 1,
                f"Saved record date: {data.get('updated', 'not supplied')}; units: {ws.unit_label}. Totals require evidence for each domain.",
                note,
            )
            for i, width in enumerate(widths):
                sh.set_column(i, i, width, numeric if i == numeric_column else body)
            if rows:
                # Table data is written explicitly to retain literal source text.
                sh.add_table(
                    4,
                    0,
                    4 + len(rows),
                    len(headers) - 1,
                    {
                        "name": name.replace(" ", ""),
                        "columns": [
                            {"header": h, "header_format": table_heading}
                            for h in headers
                        ],
                        "style": "Table Style Light 9",
                    },
                )
                for i, row in enumerate(rows, 5):
                    for col, value in enumerate(row):
                        if value is None or value == "":
                            sh.write_blank(i, col, None, body)
                        elif (
                            name == "Credit Record"
                            and col == 4
                            and re.fullmatch(r"\d{4}-\d{2}-\d{2}", text(value))
                        ):
                            sh.write_datetime(
                                i, col, datetime.fromisoformat(value), date_format
                            )
                        elif isinstance(value, (int, float)) and not isinstance(
                            value, bool
                        ):
                            sh.write_number(
                                i,
                                col,
                                value,
                                numeric if col == numeric_column else body,
                            )
                        else:
                            sh.write_string(i, col, text(value), body)
                    lines = max(
                        [1]
                        + [
                            sum(
                                max(1, math.ceil(len(line) / max(10, widths[c] - 2)))
                                for line in text(v).splitlines()
                            )
                            for c, v in enumerate(row)
                        ]
                    )
                    sh.set_row(i, max(30, 13 * lines + 7))
            else:
                sh.write_row(4, 0, headers, section)
                sh.write_string(5, 0, "No records supplied", note)
            return sh, 5 + len(rows)

        def formula(sh, row, column, value, cached):
            sh.write_formula(row, column, value, numeric, cached)
            formulas.append(
                {
                    "sheet": sh.name,
                    "row": row + 1,
                    "column": column + 1,
                    "formula": value,
                    "cached_result": cached,
                }
            )

        requirements, end = sheet(
            "Requirements",
            "Degree requirements",
            [
                "Requirement",
                "Units",
                "Status",
                "Required / selected course",
                "Assigned term",
                "Requisites",
                "Notes",
            ],
            rows_for_requirements(data),
            [34, 9, 20, 27, 18, 34, 48],
            1,
        )
        requirements.write_string(end + 2, 0, "Source register", section)
        for i, ref in enumerate(sorted(ws.evidence), end + 3):
            requirements.merge_range(i, 0, i, 6, ref, note)
            requirements.set_row(i, 30)
        assignments = sorted(
            data.get("assignments", []), key=lambda r: ws.term_key(r["term"])
        )
        plan, end = sheet(
            "Quarter Plan",
            "Course plan",
            ["Term", "Course", "Units", "Status", "Requirement / basis"],
            [
                [r["term"], r["course"], r["units"], r["status"], r["requirement_id"]]
                for r in assignments
            ],
            [21, 38, 10, 20, 59],
            2,
        )
        row = end + 2
        plan.write_row(row, 0, ["Assigned term totals", "", "Units"], section)
        for term in dict.fromkeys(r["term"] for r in assignments):
            row += 1
            plan.write_string(row, 0, term)
            formula(
                plan,
                row,
                2,
                f"=SUMIFS(C6:C{5 + len(assignments)},A6:A{5 + len(assignments)},A{row + 1})",
                sum(r["units"] for r in assignments if r["term"] == term),
            )
        proposal = data.get("term_proposal")
        if proposal:
            row += 3
            plan.write_row(
                row,
                0,
                [proposal["term"], "Proposed courses", "Units", "Status", "Basis"],
                section,
            )
            start = row + 1
            for course in proposal["courses"]:
                row += 1
                plan.write_row(
                    row,
                    0,
                    [
                        proposal["term"],
                        course["course"],
                        course["units"],
                        "Proposed",
                        course.get("basis", "See planning record"),
                    ],
                )
                plan.set_row(row, 64)
            row += 1
            plan.write_string(row, 0, "Proposed total", section)
            formula(
                plan,
                row,
                2,
                f"=SUM(C{start + 1}:C{row})" if proposal["courses"] else "=0",
                sum(c["units"] for c in proposal["courses"]),
            )
        row += 3
        plan.write_row(
            row,
            0,
            ["Completion targets", "Course", "", "Target only", "Commitment"],
            section,
        )
        for target in data.get("planning_targets", []):
            row += 1
            plan.write_row(
                row,
                0,
                [
                    target["target_term"],
                    target["course"],
                    None,
                    "Target",
                    target.get("commitment", "Requested"),
                ],
            )
            plan.set_row(row, 40)
        if ws.abroad_enabled:
            row += 3
            plan.write_row(
                row,
                0,
                [
                    "Abroad goal",
                    abroad.get("term") or "Unassigned",
                    None,
                    "Goal",
                    " > ".join(abroad.get("destination_preference", [])),
                ],
                section,
            )
        credits = data.get("credits", [])
        ledger, end = sheet(
            "Credit Record",
            "Awarded credit",
            [
                "Original course / exam",
                "Kind",
                "Awarded units",
                "Requirement recognition",
                "Evidence date",
            ],
            [
                [
                    r["course"],
                    r["kind"],
                    r["awarded_units"],
                    r.get("recognition", "Unresolved"),
                    r["evidence_date"],
                ]
                for r in credits
            ],
            [43, 17, 17, 69, 19],
            2,
        )
        row = end + 2
        ledger.write_row(row, 0, ["Credit reconciliation", "", ws.unit_label], section)
        row += 1
        earned_row = row + 1
        ledger.write_string(row, 0, "Earned units")
        earned = ws.summary["earned_units"]
        progress = ws.summary["in_progress_units"]
        if earned is None:
            ledger.write_string(row, 2, "Unknown", note)
        elif earned == ws.summary["recorded_earned_units"]:
            formula(
                ledger,
                row,
                2,
                f"=SUM(C6:C{5 + len(credits)})" if credits else "=0",
                earned,
            )
        else:
            ledger.write_number(row, 2, earned, numeric)
        row += 1
        progress_row = row + 1
        ledger.write_string(row, 0, "In progress (not earned)")
        if progress is None:
            ledger.write_string(row, 2, "Unknown", note)
        else:
            ledger.write_number(row, 2, progress, numeric)
        for label, field, domain in [
            ("Recorded award subtotal", "recorded_earned_units", "credits"),
            (
                "Recorded coursework subtotal",
                "recorded_in_progress_units",
                "current_coursework",
            ),
        ]:
            row += 1
            ledger.write_string(row, 0, label)
            ledger.write_string(
                row,
                1,
                ws.summary["unit_coverage"][domain]["status"].replace("-", " "),
                note,
            )
            ledger.write_number(row, 2, ws.summary[field], numeric)
        if data.get("audit_snapshot"):
            row += 1
            minimum_row = row + 1
            minimum = ws.summary["minimum_degree_units"]
            ledger.write_string(row, 0, "Degree minimum")
            if minimum is None:
                ledger.write_string(row, 2, "Unknown", note)
            else:
                ledger.write_number(row, 2, minimum, numeric)
            for label, field, expression in [
                (
                    "Remaining on earned basis",
                    "remaining_earned_units_to_minimum",
                    f"=MAX(0,C{minimum_row}-C{earned_row})",
                ),
                (
                    "Remaining if current work completes",
                    "remaining_units_if_in_progress_completed",
                    f"=MAX(0,C{minimum_row}-C{earned_row}-C{progress_row})",
                ),
            ]:
                row += 1
                ledger.write_string(row, 0, label)
                if ws.summary[field] is None:
                    ledger.write_string(row, 2, "Unknown", note)
                else:
                    formula(ledger, row, 2, expression, ws.summary[field])
        for kind in sorted(set(r["kind"] for r in credits)):
            row += 1
            ledger.write_string(row, 0, "Recorded subtotal: " + kind)
            ledger.write_string(row, 1, kind)
            formula(
                ledger,
                row,
                2,
                f"=SUMIFS(C6:C{5 + len(credits)},B6:B{5 + len(credits)},B{row + 1})",
                sum(r["awarded_units"] for r in credits if r["kind"] == kind),
            )
        for option in recognition_options(data):
            row += 3
            ledger.merge_range(row, 0, row, 4, recognition_summary(option), note)
            ledger.set_row(row, 86)
            if option.get("implementation_notes"):
                row += 1
                ledger.merge_range(row, 0, row, 4, option["implementation_notes"], note)
                ledger.set_row(row, 60)
        ledger.set_print_scale(60)
    return formulas


def pdf_views(ws, folder):
    styles = getSampleStyleSheet()
    styles.add(
        ParagraphStyle(
            name="AcademicBody",
            fontName="Helvetica",
            fontSize=10,
            leading=14,
            spaceAfter=8,
        )
    )
    styles.add(
        ParagraphStyle(
            name="AcademicSmall",
            fontName="Helvetica",
            fontSize=8,
            leading=11,
            spaceAfter=5,
            textColor=colors.HexColor("#526479"),
        )
    )
    styles["Title"].fontSize = 22
    styles["Title"].textColor = colors.HexColor("#243B53")
    styles["Heading2"].textColor = colors.HexColor("#243B53")

    def para(value, small=False):
        return Paragraph(
            escape(plain(value)).replace("\n", "<br/>"),
            styles["AcademicSmall" if small else "AcademicBody"],
        )

    def title(value):
        return Paragraph(escape(value), styles["Title"])

    def heading(value):
        return Paragraph(escape(value), styles["Heading2"])

    def table(rows, widths):
        wrapped = [[para(cell, True) for cell in row] for row in rows]
        value = LongTable(wrapped, colWidths=widths, repeatRows=1, hAlign="LEFT")
        value.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E8EDF2")),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
                    ("TOPPADDING", (0, 0), (-1, -1), 7),
                    ("LINEBELOW", (0, 0), (-1, 0), 0.5, colors.HexColor("#A4B1C0")),
                ]
            )
        )
        return value

    def save(name, story):
        def footer(canvas, document):
            canvas.setFont("Helvetica", 8)
            canvas.setFillColor(colors.HexColor("#526479"))
            canvas.drawString(
                44, 24, "Generated view - edit shared records and rebuild"
            )
            canvas.drawRightString(568, 24, str(document.page))

        SimpleDocTemplate(
            str(folder / name),
            pagesize=letter,
            leftMargin=44,
            rightMargin=44,
            topMargin=36,
            bottomMargin=43,
            title=name.replace(".pdf", ""),
        ).build(story, onFirstPage=footer, onLaterPages=footer)

    data, abroad = ws.data, ws.abroad
    profile = data.get("profile", {})
    gpa = profile.get("current_gpa", profile.get("current_ucla_gpa"))
    story = [
        title("Academic advising"),
        para(
            f"Record date: {data.get('updated', 'not supplied')}. {profile.get('institution', 'Institution not supplied')} - {profile.get('major', 'Major not supplied')}."
        ),
        para(total_description(ws.summary, "credits", ws.unit_label)),
        para(total_description(ws.summary, "current_coursework", ws.unit_label)),
        para(f"GPA: {gpa if gpa is not None else 'not supplied'}."),
        heading("Course plan"),
    ]
    proposal = data.get("term_proposal")
    if proposal:
        story += [
            para(proposal["term"] + " proposal; not confirmed enrollment."),
            table(
                [["Course", "Units", "Decision status"]]
                + [[c["course"], c["units"], "Proposed"] for c in proposal["courses"]],
                [310, 65, 149],
            ),
        ]
    else:
        story.append(para("No next-term proposal recorded."))
    assignments = data.get("assignments", [])
    if assignments:
        story += [
            heading("Active assignments"),
            table(
                [["Term / course", "Status"]]
                + [
                    [r["term"] + ": " + r["course"], r["status"]]
                    for r in sorted(assignments, key=lambda r: ws.term_key(r["term"]))
                ],
                [365, 159],
            ),
        ]
    story += [heading("Goals and decisions"), para(goal_summary(ws.goals))]
    for question in data.get("open_questions", []):
        story.append(para(question))
    story += [
        heading("Evidence"),
        para(
            "See knowledge/academics/academic.yaml and its dated source references. Research dates and unresolved approvals remain material.",
            True,
        ),
    ]
    options = recognition_options(data)
    if options:
        story.append(heading("Conditional existing-credit use"))
        for option in options:
            story += [
                para(recognition_summary(option), True),
                para(option.get("implementation_notes", ""), True),
            ]
    if data.get("research_updates"):
        story.append(heading("Sourced research updates"))
        story += [para(line, True) for line in research_lines(data)]
    save("Academic-Advising.pdf", story)
    if not ws.abroad_enabled:
        return
    story = [
        title("Study abroad brief"),
        para(
            f"Target term: {abroad.get('term') or 'not selected'}. Route: {abroad.get('route') or 'not selected'}."
        ),
        para(
            "Preference: "
            + (" > ".join(abroad.get("destination_preference", [])) or "not selected")
        ),
        para(
            "Research date: "
            + text(abroad.get("research_as_of") or "not supplied")
            + ". "
            + text(
                abroad.get(
                    "current_verification",
                    "Rules require current official verification.",
                )
            )
        ),
        heading("Purpose and access"),
        para(
            abroad.get("ge_plan", {}).get(
                "summary", "Degree use and course mix remain unassigned."
            )
        ),
    ]
    breadth = abroad.get("breadth_exploration", {})
    if breadth:
        story.append(
            para(
                f"Breadth selection: {breadth.get('selected') or 'not selected'}. Leaning: {breadth.get('leaning') or 'not supplied'}."
            )
        )
    for destination in abroad.get("destinations", []):
        story += [
            heading(
                text(destination.get("label", destination.get("code", "Destination")))
            ),
            para(destination.get("eligibility", "Eligibility unresolved")),
            para(destination.get("access", "Access unresolved")),
        ]
    story += [PageBreak(), heading("Courses and credit approval")]
    candidates = abroad.get("historical_candidates", [])
    if candidates:
        story.append(
            table(
                [["Historical candidate", "Status"]]
                + [
                    [c["course"], "Unapproved; check offering, access and degree use"]
                    for c in candidates
                ],
                [330, 194],
            )
        )
    approvals = abroad.get("approved_courses", [])
    if approvals:
        story.append(
            table(
                [["Recorded approval", "Scope / evidence"]]
                + [
                    [
                        c["course"],
                        c.get("degree_use", "See evidence")
                        + "; "
                        + c["approval_source"],
                    ]
                    for c in approvals
                ],
                [220, 304],
            )
        )
    else:
        story.append(para("No approved abroad courses are recorded."))
    if options:
        story.append(heading("Conditional existing-credit use"))
        story += [para(recognition_summary(option), True) for option in options]
    useful = useful_requirements(data, abroad)
    if useful:
        story.append(heading("Useful degree requirements; host use unresolved"))
        story.append(
            table(
                [["Requirement", "Status / notes"]]
                + [
                    [r["requirement"], r["status"] + "; " + r.get("notes", "")]
                    for r in useful
                ],
                [220, 304],
            )
        )
    load = abroad.get("load_planning", {})
    for key in ("summary", "unresolved"):
        if load.get(key):
            story.append(para(load[key], True))
    if abroad.get("research_updates"):
        story.append(heading("Sourced research updates"))
        story += [para(line, True) for line in research_lines(abroad)]
    story += [heading("Advising questions")]
    story += [para(q) for q in abroad.get("questions", [])] or [
        para("No questions supplied.")
    ]
    story += [
        heading("Evidence and decisions"),
        para(
            "Program eligibility, host enrollment permission, credit conversion and home-university requirement approval need separate evidence. Preserved sources and detailed research remain in shared records."
        ),
    ]
    for destination in abroad.get("destinations", []):
        if destination.get("url"):
            story.append(para(destination["url"], True))
    save("Abroad-Brief.pdf", story)


def markdown(ws):
    data, abroad = ws.data, ws.abroad
    profile = data.get("profile", {})
    gpa = profile.get("current_gpa", profile.get("current_ucla_gpa"))
    lines = [
        "# Current academic record",
        "",
        "Generated view: edit knowledge/academics/ and knowledge/goals/, then rebuild.",
        "",
        f"Saved record date: {data.get('updated', 'not supplied')}",
        f"Institution / major: {profile.get('institution') or 'not supplied'} / {profile.get('major') or 'not supplied'}",
        total_description(ws.summary, "credits", ws.unit_label),
        total_description(ws.summary, "current_coursework", ws.unit_label),
        f"GPA: {gpa if gpa is not None else 'not supplied'}",
        "",
        "## Active assignments",
        "",
    ]
    for row in sorted(
        data.get("assignments", []), key=lambda r: ws.term_key(r["term"])
    ):
        lines.append(
            f"- {row['term']}: {row['course']} ({row['units']}), {row['status']}"
        )
    lines += ["", "## Requirement status", ""]
    lines += [
        f"- {r['id']}: {r['requirement']}; {r['status']}"
        for r in data.get("requirements", [])
    ]
    lines += ["", "## Current coursework", ""]
    lines += [
        f"- {r['course']}: {r['units']} units; in-progress"
        for r in data.get("current_coursework", [])
    ]
    if data.get("planning_targets"):
        lines += ["", "## Completion targets; not enrollment", ""]
        lines += [
            f"- {r['target_term']}: {r['course']}; {r.get('commitment', 'Target')}"
            for r in data["planning_targets"]
        ]
    proposal = data.get("term_proposal")
    lines += ["", "## Next-term proposal", ""]
    if proposal:
        lines += [f"{proposal['term']} - proposed; not enrollment.", ""] + [
            f"- {c['course']}: {c['units']} units; {c.get('basis', 'See evidence')}"
            for c in proposal["courses"]
        ]
    else:
        lines.append("No proposal recorded.")
    for option in recognition_options(data):
        lines += [
            "",
            "## Conditional existing-credit use",
            "",
            recognition_summary(option),
            option.get("implementation_notes", ""),
            "Evidence: " + str(option.get("approval_source", "pending")),
        ]
    if data.get("research_updates"):
        lines += ["", "## Sourced research updates", "", *research_lines(data)]
    if ws.abroad_enabled:
        lines += [
            "",
            "## Abroad",
            "",
            f"Target: {abroad.get('term') or 'not selected'}",
            f"Preference: {' > '.join(abroad.get('destination_preference', [])) or 'not selected'}",
            f"Recorded course approvals: {len(abroad.get('approved_courses', []))}",
            *research_lines(abroad),
        ]
        for requirement in useful_requirements(data, abroad):
            lines.append(
                "Useful requirement; host use unapproved: " + requirement["requirement"]
            )
        for key in ("summary", "unresolved"):
            if abroad.get("load_planning", {}).get(key):
                lines.append(abroad["load_planning"][key])
    lines += [
        "",
        "## Shared goals",
        "",
        ws.goals.strip(),
        "",
        "## Evidence register",
        "",
    ]
    lines += [f"- [{relative}](../../{relative})" for relative in sorted(ws.evidence)]
    return "\n".join(lines) + "\n"


def render_all(ws, folder):
    formulas = workbook(ws, folder / "Academic-Planner.xlsx")
    pdf_views(ws, folder)
    (folder / "Current-Academic-Record.md").write_text(markdown(ws), encoding="utf-8")
    from .core import json_bytes

    (folder / "formula-values.json").write_bytes(json_bytes(formulas))
