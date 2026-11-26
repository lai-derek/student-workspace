"""Application Studio backend: store, markup, rendering, export, import, screening checks, AI handoff."""

from __future__ import annotations

import io
import json
import sqlite3
from datetime import date
from pathlib import Path

import pytest
from pypdf import PdfReader

from student_workspace.cli import main as cli_main
from student_workspace.studio import ats, export, handoff, importer
from student_workspace.studio.db import DB_RELATIVE, connect
from student_workspace.studio.markup import plain, segments, smarten
from student_workspace.studio.render import Renderer, compile_source, export_source
from student_workspace.studio.store import TEMPLATES, Studio, StudioError
from student_workspace.workspace import initialize_workspace

FIXTURES = Path(__file__).parent / "fixtures" / "studio"
DAY = date(2026, 11, 22)
HEADER = {
    "name": "Alex Rivera",
    "contact": [
        {"text": "alex@example.edu", "url": "mailto:alex@example.edu"},
        {"text": "github.com/example-alex", "url": "https://github.com/example-alex"},
    ],
}


@pytest.fixture(scope="module")
def renderer() -> Renderer:
    return Renderer()


@pytest.fixture
def studio(tmp_path: Path):
    root = tmp_path / "Student Workspace"
    initialize_workspace(root)
    with Studio(root) as opened:
        yield opened


def build(studio: Studio, folder: str = "applications/acme") -> dict[str, str]:
    """A small resume: one education entry, one project with three bullets."""
    resume_id, version_id = studio.create_resume(
        folder, header=HEADER, skills=[{"label": "Languages", "value": "Python, C++"}], day=DAY
    )
    edu = studio.add_section(version_id, "Education", "education")
    school = studio.create_entry(
        "education",
        "Example University",
        location="Los Angeles, CA",
        subtitle="B.S. in EE",
        dates="Expected 2030",
    )
    studio.add_entry_to_section(edu, school)
    proj = studio.add_section(version_id, "Projects", "project")
    project = studio.create_entry(
        "project", "Offline Note Taker", url="https://github.com/example-alex/notes"
    )
    studio.add_entry_to_section(proj, project)
    b1 = studio.add_bullet(version_id, project, "Built an **offline** app that writes structured notes.")
    b2 = studio.add_bullet(version_id, project, "Compared nine models; 3.1% word error versus 5.6%.")
    b3 = studio.add_bullet(version_id, project, "Collected 40 labeled photos for a vision pilot.")
    return {"resume": resume_id, "version": version_id, "edu": edu, "proj": proj, "project": project,
            "school": school, "b1": b1, "b2": b2, "b3": b3}  # fmt: skip


def bullet_texts(studio: Studio, version_id: str) -> list[str]:
    version = studio.version(version_id)
    return [
        b["text"] for s in version["sections"] for e in s["entries"] for b in e["bullets"] if not b["hidden"]
    ]


# ---------- database ----------


def test_database_lives_in_the_workspace_and_migrates_once(studio: Studio) -> None:
    assert (studio.root / DB_RELATIVE).is_file()
    again = connect(studio.root)
    versions = [row[0] for row in again.execute("SELECT version FROM schema_migrations")]
    again.close()
    assert versions == [1]


def test_foreign_keys_are_enforced(studio: Studio) -> None:
    with pytest.raises(sqlite3.IntegrityError), studio.conn:
        studio.conn.execute("INSERT INTO bullets VALUES ('bul_x', 'ent_missing', 't', 'n', 'n')")


# ---------- store ----------


def test_version_name_and_reading_back(studio: Studio) -> None:
    ids = build(studio)
    version = studio.version(ids["version"])
    assert version["name"] == "resume-2026-11-22"
    assert [s["title"] for s in version["sections"]] == ["Education", "Projects"]
    assert bullet_texts(studio, ids["version"])[0].startswith("Built an **offline**")


def test_reorder_hide_and_edit_stay_in_this_version(studio: Studio) -> None:
    ids = build(studio)
    v = ids["version"]
    studio.move(v, "bullet", ids["b3"], 0)
    studio.set_hidden(v, "bullet", ids["b2"], True)
    studio.edit_bullet(v, ids["b1"], "Built an offline app.")
    assert bullet_texts(studio, v) == [
        "Collected 40 labeled photos for a vision pilot.",
        "Built an offline app.",
    ]
    assert [b["id"] for b in studio.render_data(v)["sections"][1]["entries"][0]["bullets"]] == [
        ids["b3"],
        ids["b1"],
    ]
    # The library keeps the original wording until it's saved.
    library = {b["id"]: b["text"] for e in studio.library() for b in e["bullets"]}
    assert library[ids["b1"]].startswith("Built an **offline**")
    studio.save_bullet_to_library(v, ids["b1"])
    library = {b["id"]: b["text"] for e in studio.library() for b in e["bullets"]}
    assert library[ids["b1"]] == "Built an offline app."


def test_sections_and_entries_reorder_and_hide(studio: Studio) -> None:
    ids = build(studio)
    v = ids["version"]
    studio.move(v, "section", ids["proj"], 0)
    studio.set_hidden(v, "entry", ids["school"], True)
    data = studio.render_data(v)
    assert [s["title"] for s in data["sections"]] == ["Projects"]  # Education has no visible entries
    with pytest.raises(StudioError):
        studio.set_hidden(v, "entry", "ent_missing", True)


def test_variants_are_picked_per_version(studio: Studio) -> None:
    ids = build(studio)
    v = ids["version"]
    variant = studio.add_variant(ids["b2"], "Benchmarked nine models.")
    assert studio.add_variant(ids["b2"], "Benchmarked nine models.") == variant  # no duplicates
    studio.choose_variant(v, ids["b2"], variant)
    assert "Benchmarked nine models." in bullet_texts(studio, v)
    other = studio.new_version(v, day=DAY)
    studio.choose_variant(other, ids["b2"], None)
    assert "Benchmarked nine models." in bullet_texts(studio, v)
    assert "Benchmarked nine models." not in bullet_texts(studio, other)


def test_new_version_copies_everything_under_a_new_name(studio: Studio) -> None:
    ids = build(studio)
    v = ids["version"]
    studio.set_hidden(v, "bullet", ids["b3"], True)
    studio.set_template(v, "classic")
    other = studio.new_version(v, day=DAY)
    copy = studio.version(other)
    assert copy["name"] == "resume-2026-11-22-2" and copy["template"] == "classic"

    def without_section_ids(version_id: str) -> list[dict]:
        return [{k: s[k] for k in s if k != "id"} for s in studio.render_data(version_id)["sections"]]

    assert without_section_ids(other) == without_section_ids(v)  # new section ids, same content
    studio.delete_version(other)
    with pytest.raises(StudioError, match="at least one version"):
        studio.delete_version(v)


@pytest.mark.parametrize(
    ("call", "message"),
    [
        (lambda s, ids: s.edit_bullet(ids["version"], ids["b1"], "   "), "can't be empty"),
        (lambda s, ids: s.add_bullet(ids["version"], ids["project"], "x" * 2001), "longer than"),
        (lambda s, ids: s.update_entry(ids["project"], url="javascript:alert(1)"), "must start with"),
        (lambda s, ids: s.set_settings(ids["version"], {"font_size": 40}), "font_size"),
        (lambda s, ids: s.set_settings(ids["version"], {"colour": 1}), "unknown settings"),
        (lambda s, ids: s.set_template(ids["version"], "fancy"), "template must be"),
        (lambda s, ids: s.create_resume("../outside", header=HEADER), "below applications/"),
        (lambda s, ids: s.create_resume("applications/acme", header=HEADER), "already has a resume"),
        (lambda s, ids: s.edit_bullet(ids["version"], "bul_missing", "x"), "not found"),
    ],
)
def test_invalid_changes_are_refused(studio: Studio, call, message: str) -> None:
    ids = build(studio)
    with pytest.raises(StudioError, match=message):
        call(studio, ids)


def test_settings_merge_and_stay_in_bounds(studio: Studio) -> None:
    ids = build(studio)
    studio.set_settings(ids["version"], {"font_size": 10, "spacing": 0.8})
    assert studio.version(ids["version"])["settings"] == {"font_size": 10.0, "spacing": 0.8, "margin": 0.5}


# ---------- markup ----------


def test_markup_segments_and_typography() -> None:
    assert [s["bold"] for s in segments("a **b** c")] == [False, True, False]
    assert segments("[site](https://example.com)")[0]["url"] == "https://example.com"
    assert segments("[bad](javascript:alert(1))")[0]["url"] is None
    assert plain("2 * 3 * 4") == "2 * 3 * 4"
    assert plain(r"\*\*literal\*\*") == "**literal**"
    assert smarten('"Hi," it\'s 2024 -- 2026') == "“Hi,” it’s 2024 – 2026"


# ---------- rendering ----------


@pytest.mark.parametrize("template", TEMPLATES)
def test_every_template_renders_positions_and_exports_identically(
    studio: Studio, renderer: Renderer, template: str
) -> None:
    ids = build(studio)
    data = studio.render_data(ids["version"])
    out = renderer.render(data, template)
    assert out.pages == 1 and 0 < out.fill < 1 and out.warnings == []
    assert {ids["b1"], ids["b2"], ids["b3"], ids["school"], ids["project"]} <= set(out.boxes)
    tops = [out.boxes[ids[b]]["top"] for b in ("b1", "b2", "b3")]
    assert tops == sorted(tops)
    assert compile_source(export_source(data, template)) == out.pdf


def test_user_text_never_runs_as_typst_but_raw_override_does(studio: Studio, renderer: Renderer) -> None:
    ids = build(studio)
    v = ids["version"]
    studio.edit_bullet(v, ids["b1"], 'Typst stays literal: #panic("x") $x^2$ <label> @ref // not a comment')
    studio.set_raw(v, ids["b2"], "Raw *Typst* with #text(fill: red)[color]")
    out = renderer.render(studio.render_data(v), "jake")
    text = " ".join(PdfReader(io.BytesIO(out.pdf)).pages[0].extract_text().split())
    assert "#panic(“x”) $x^2$ <label> @ref // not a comment" in text
    assert "Raw Typst with color" in text


def test_fill_grows_and_overflow_is_two_pages(studio: Studio, renderer: Renderer) -> None:
    ids = build(studio)
    v = ids["version"]
    before = renderer.render(studio.render_data(v), "jake").fill
    studio.add_bullet(v, ids["project"], "One more line of content for the fill meter.")
    assert renderer.render(studio.render_data(v), "jake").fill > before
    for i in range(40):
        studio.add_bullet(v, ids["project"], f"Filler bullet number {i} to push the resume past one page.")
    assert renderer.render(studio.render_data(v), "jake").pages == 2


def test_settings_change_the_layout(studio: Studio, renderer: Renderer) -> None:
    ids = build(studio)
    v = ids["version"]
    base = renderer.render(studio.render_data(v), "jake").fill
    studio.set_settings(v, {"font_size": 11.5, "spacing": 1.4})
    assert renderer.render(studio.render_data(v), "jake").fill > base


# ---------- export ----------


def test_export_writes_matching_source_and_pdf(studio: Studio) -> None:
    ids = build(studio)
    v = ids["version"]
    result = export.export_version(studio, v)
    source = studio.root / result["source_path"]
    pdf = studio.root / result["pdf_path"]
    assert source.name == "resume-2026-11-22.typ" and pdf.name == "resume-2026-11-22.pdf"
    assert source.parent == studio.root / "applications" / "acme"
    assert export.export_state(studio, v)["state"] == "current"
    assert export.verify_export(studio, v)


def test_editing_after_export_marks_the_export_outdated(studio: Studio) -> None:
    ids = build(studio)
    v = ids["version"]
    export.export_version(studio, v)
    studio.edit_bullet(v, ids["b1"], "A later wording.")
    assert export.export_state(studio, v)["state"] == "outdated"
    assert export.verify_export(studio, v)  # the files on disk still match each other
    export.export_version(studio, v)
    assert export.export_state(studio, v)["state"] == "current"


def test_outside_edits_are_detected_and_not_overwritten(studio: Studio) -> None:
    ids = build(studio)
    v = ids["version"]
    result = export.export_version(studio, v)
    source = studio.root / result["source_path"]
    source.write_text(
        source.read_text(encoding="utf-8").replace("Example University", "Edited By Hand"), encoding="utf-8"
    )
    assert export.export_state(studio, v)["state"] == "changed-outside"
    assert not export.verify_export(studio, v)
    with pytest.raises(StudioError, match="changed outside"):
        export.export_version(studio, v)
    export.export_version(studio, v, replace_outside_edits=True)
    assert export.verify_export(studio, v)


def test_export_refuses_to_overwrite_a_file_it_did_not_write(studio: Studio) -> None:
    ids = build(studio)
    folder = studio.root / "applications" / "acme"
    folder.mkdir(parents=True)
    (folder / "resume-2026-11-22.pdf").write_bytes(b"%PDF handmade")
    with pytest.raises(StudioError, match="wasn't written by the studio"):
        export.export_version(studio, ids["version"])


# ---------- import ----------


def test_import_jake_style_resume(studio: Studio) -> None:
    parsed = importer.parse_resume((FIXTURES / "jake-resume.tex").read_text(encoding="utf-8"))
    assert parsed["name"] == "Alex Rivera"
    assert parsed["contact"][1] == {"text": "alex@example.edu", "url": "mailto:alex@example.edu"}
    assert [s["title"] for s in parsed["sections"]] == ["Education", "Projects", "Leadership"]
    school, highschool = parsed["sections"][0]["entries"]
    assert school["location"] == "Los Angeles, CA" and school["dates"] == "Expected Jun. 2030"
    assert school["subtitle"] == "B.S. in Electrical Engineering"
    assert school["note"] == "Selected coursework | Linear Algebra, Python"
    assert highschool["details"] == "Valedictorian | 12 AP exams" and highschool["dates"] == "Jun. 2026"
    project = parsed["sections"][1]["entries"][0]
    assert (
        project["title"] == "Offline Note Taker" and project["url"] == "https://github.com/example-alex/notes"
    )
    assert project["tech"] == "Python, ONNX Runtime" and project["dates"] == "2026 -- Present"
    assert project["bullets"][0].endswith("writes **structured notes**.")
    assert (
        project["bullets"][1]
        == "Compared nine local models; the default reached 3.1% word error versus 5.6% for the baseline."
    )
    club = parsed["sections"][2]["entries"][0]
    assert club["dates"] == "2024 -- 2026" and club["location"] == "Springfield, CA"
    assert " 100+ students" in club["bullets"][0]
    assert (
        club["bullets"][1]
        == "Raised $500+ annually & sourced snacks from local businesses; it's a tradition."
    )
    assert parsed["skills"] == [
        {"label": "Languages", "value": "Python, C++, SQL"},
        {"label": "Tools & Frameworks", "value": "PyTorch, Git"},
    ]


def test_import_original_jake_layout(studio: Studio) -> None:
    parsed = importer.parse_resume((FIXTURES / "original-jake.tex").read_text(encoding="utf-8"))
    assert parsed["name"] == "Sam Lee"
    assert [c["text"] for c in parsed["contact"]] == [
        "123-456-7890",
        "sam@example.com",
        "github.com/example-sam",
    ]
    job = parsed["sections"][0]["entries"][0]
    assert job["title"] == "Undergraduate Research Assistant" and job["dates"] == "June 2025 -- Present"
    assert job["location"] == "College Station, TX" and job["subtitle"] == "Example University"
    assert parsed["sections"][1]["entries"][0]["tech"] == "Python, Flask, React"
    assert parsed["skills"][0] == {"label": "Languages", "value": "Java, Python, C/C++, SQL"}


def test_imported_resume_renders_and_reuses_the_library(studio: Studio, renderer: Renderer) -> None:
    tex = (FIXTURES / "jake-resume.tex").read_text(encoding="utf-8")
    first = importer.import_resume(studio, "applications/acme", tex, day=DAY)
    second = importer.import_resume(studio, "applications/globex", tex, day=DAY)
    assert first["entries_created"] == 4 and second["entries_created"] == 0 and second["entries_reused"] == 4
    assert len([b for e in studio.library() for b in e["bullets"]]) == 4  # bullets shared, not duplicated
    data = studio.render_data(first["version_id"])
    out = renderer.render(data, "jake")
    report = ats.parse_check(out.pdf, data, margin_in=0.5)
    assert report["result"] == "ok", report["findings"]


def test_evidence_matrix_rows_become_notes(studio: Studio) -> None:
    matrix = studio.root / "matrix.md"
    matrix.write_text(
        "| Claim | Evidence | Scope |\n| --- | --- | --- |\n"
        "| Nine models compared | [Benchmark](https://example.com/b) | One talk only |\n"
        "| Club fundraising | Club record | Gross funds |\n",
        encoding="utf-8",
    )
    ids = importer.import_evidence_matrix(studio, matrix)
    notes = studio.evidence()
    assert len(ids) == 2 and notes[1]["title"] == "Nine models compared"
    assert "Benchmark (https://example.com/b)" in notes[1]["body"]
    assert importer.import_evidence_matrix(studio, matrix) == ids  # re-import updates, doesn't duplicate


def test_evidence_links_show_on_bullets(studio: Studio) -> None:
    ids = build(studio)
    note = studio.add_evidence("Benchmark record", "One talk; 3.1% vs 5.6%.")
    studio.link_evidence(note, "bullet", ids["b2"])
    bullet = studio.version(ids["version"])["sections"][1]["entries"][0]["bullets"][1]
    assert [n["title"] for n in bullet["evidence"]] == ["Benchmark record"]
    studio.link_evidence(note, "bullet", ids["b2"], linked=False)
    assert studio.version(ids["version"])["sections"][1]["entries"][0]["bullets"][1]["evidence"] == []


# ---------- screening checks ----------


def test_parse_check_flags_problems(studio: Studio, renderer: Renderer) -> None:
    ids = build(studio)
    v = ids["version"]
    studio.add_section(v, "My Journey", "other")
    studio.add_bullet(v, ids["project"], "A" * 220)
    data = studio.render_data(v)
    report = ats.parse_check(renderer.render(data, "jake").pdf, data, margin_in=0.5)
    codes = {f["code"]: f["level"] for f in report["findings"]}
    assert codes["margins"] == "error" and report["result"] == "error"


def test_keyword_coverage_marks_missing_terms_and_evidence(studio: Studio) -> None:
    posting = (
        "We build Python services on Kubernetes. Interns write Python and SQL, use Kubernetes daily, "
        "and work on data pipelines. Experience with data pipelines is a plus."
    )
    resume = "Built Python tools with SQL storage."
    evidence = [{"id": "ev_1", "title": "Cluster work", "body": "Deployed jobs on Kubernetes"}]
    result = ats.keyword_coverage(posting, resume, evidence)
    terms = {row["term"].lower(): row for row in result["terms"]}
    assert terms["python"]["covered"] and terms["sql"]["covered"]
    assert not terms["kubernetes"]["covered"] and terms["kubernetes"]["evidence"][0]["id"] == "ev_1"
    assert "data pipelines" in terms and not terms["data pipelines"]["covered"]
    assert ats.keyword_coverage("", resume) == {"terms": [], "covered": 0, "missing": 0}


# ---------- AI handoff ----------


def answer(studio: Studio, request_path: str, variants: list[dict[str, str]]) -> None:
    folder = studio.root / request_path
    (folder / "drafts" / "variants.json").write_text(
        json.dumps({"schema_version": "1.0", "variants": variants}), encoding="utf-8"
    )
    (folder / "response.json").write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "request_id": folder.name,
                "status": "drafted",
                "artifacts": [{"path": "drafts/variants.json", "kind": "draft"}],
                "source_refs": [],
                "notes": "",
                "custom": {},
            }
        ),
        encoding="utf-8",
    )


def test_ask_ai_round_trip(studio: Studio) -> None:
    ids = build(studio)
    v = ids["version"]
    request = handoff.ask_ai(studio, v, ids["proj"], "Make the benchmark bullet more specific")
    target = json.loads((studio.root / request["request_path"] / "target.json").read_text(encoding="utf-8"))
    assert target["kind"] == "studio-section"
    assert [b["bullet_id"] for b in target["entries"][0]["bullets"]] == [ids["b1"], ids["b2"], ids["b3"]]
    with pytest.raises(StudioError, match="isn't answered yet"):
        handoff.import_variants(studio, request["request_path"])
    assert handoff.requests_for(studio, v)[0]["status"] == "awaiting-response"

    answer(
        studio,
        request["request_path"],
        [
            {"bullet_id": ids["b2"], "text": "Benchmarked nine models on one talk: 3.1% vs 5.6% word error."},
            {"bullet_id": "bul_not_in_this_section", "text": "ignored"},
        ],
    )
    result = handoff.import_variants(studio, request["request_path"])
    assert result["added"] == 1 and len(result["skipped"]) == 1
    bullet = studio.version(v)["sections"][1]["entries"][0]["bullets"][1]
    assert (
        bullet["variants"][0]["source"] == "ai"
        and bullet["variants"][0]["request_id"] == request["request_id"]
    )
    assert handoff.requests_for(studio, v)[0]["imported_variants"] == 1


# ---------- command line ----------


def test_cli_import_show_export_verify_check(studio: Studio, capsys: pytest.CaptureFixture[str]) -> None:
    root = str(studio.root)
    tex = str(FIXTURES / "jake-resume.tex")
    assert cli_main(["--json", "resume", "import-tex", root, "applications/acme", tex]) == 0
    version_id = json.loads(capsys.readouterr().out)["version_id"]
    assert cli_main(["resume", "show", root, version_id]) == 0
    assert "Offline Note Taker" in capsys.readouterr().out
    assert cli_main(["resume", "export", root, version_id]) == 0
    assert cli_main(["resume", "verify", root, version_id]) == 0
    assert "matches its source" in capsys.readouterr().out
    assert cli_main(["resume", "check", root, version_id]) == 0
    assert cli_main(["resume", "show", root, "ver_missing"]) == 1
