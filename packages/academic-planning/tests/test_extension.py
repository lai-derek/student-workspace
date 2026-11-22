import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import openpyxl
from pypdf import PdfReader
import yaml
from student_workspace.workspace import initialize_workspace

from academic_planning.core import (
    PlanningError,
    Workspace,
    digest,
    import_source,
    json_bytes,
    within,
)
from academic_planning.records import demo, initialize


class ExtensionTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.base = Path(self.temporary.name)
        self.root = self.base / "workspace"
        demo(self.root)

    def read(self, name="academic.yaml"):
        return yaml.safe_load((self.root / "knowledge/academics" / name).read_text())

    def write(self, data, name="academic.yaml"):
        (self.root / "knowledge/academics" / name).write_text(
            yaml.safe_dump(data, sort_keys=False), encoding="utf-8"
        )

    def test_demo_has_three_distinct_views_and_cached_totals(self):
        ws = Workspace(self.root)
        self.assertFalse(ws.check()["outputs_stale"])
        book = openpyxl.load_workbook(
            ws.output / "Academic-Planner.xlsx", data_only=True
        )
        self.assertEqual(
            book.sheetnames, ["Requirements", "Quarter Plan", "Credit Record"]
        )
        ledger = book["Credit Record"]
        values = {r[0].value: r[2].value for r in ledger.iter_rows()}
        self.assertEqual(values["Earned units"], 13)
        self.assertEqual(values["In progress (not earned)"], 4)
        self.assertEqual(values["Remaining on earned basis"], 107)
        self.assertEqual(values["Remaining if current work completes"], 103)
        formulas = openpyxl.load_workbook(
            ws.output / "Academic-Planner.xlsx", data_only=False
        )
        self.assertEqual(formulas["Requirements"].freeze_panes, "A6")
        self.assertEqual(len(formulas["Requirements"].tables), 1)
        self.assertIsNone(formulas["Requirements"]["E6"].value)
        self.assertTrue(
            any(
                c.data_type == "f" and "SUMIFS" in c.value
                for row in formulas["Quarter Plan"]
                for c in row
            )
        )
        self.assertFalse(
            any(c.data_type == "e" for sh in book for row in sh for c in row)
        )

    def test_pdfs_reopen_with_text_and_expected_pages(self):
        folder = Workspace(self.root).output
        advising = PdfReader(folder / "Academic-Advising.pdf")
        abroad = PdfReader(folder / "Abroad-Brief.pdf")
        self.assertEqual(len(advising.pages), 1)
        self.assertEqual(len(abroad.pages), 2)
        self.assertIn("Proposed", advising.pages[0].extract_text())
        self.assertNotIn("##", advising.pages[0].extract_text())
        self.assertIn("No approved abroad courses", abroad.pages[1].extract_text())

    def test_earned_credit_is_not_increased_by_in_progress_or_proposal(self):
        result = Workspace(self.root).context("record")
        self.assertEqual(result["earned_units"], 13)
        self.assertEqual(result["in_progress_units"], 4)

    def test_current_audit_and_historical_totals_are_independent(self):
        data = self.read()
        row = copy.deepcopy(data["credits"][0])
        row.update(
            id="later-award",
            course="LATER",
            evidence_date="2032-02-01",
            awarded_units=3,
        )
        data["credits"].append(row)
        data["audit_snapshot"].update(
            earned_units=16,
            remaining_earned_units_to_minimum=104,
            remaining_units_if_in_progress_completed=100,
        )
        self.write(data)
        self.assertTrue(Workspace(self.root).check()["outputs_stale"])
        Workspace(self.root).build()
        book = openpyxl.load_workbook(
            Workspace(self.root).output / "Academic-Planner.xlsx", data_only=True
        )
        self.assertEqual(
            {r[0].value: r[2].value for r in book["Credit Record"].iter_rows()}[
                "Earned units"
            ],
            16,
        )

    def test_duplicate_award_rejected(self):
        data = self.read()
        duplicate = dict(data["credits"][0], id="different-id")
        data["credits"].append(duplicate)
        self.write(data)
        with self.assertRaisesRegex(PlanningError, "Duplicate credit"):
            Workspace(self.root).load()

    def test_invalid_numeric_units_rejected(self):
        for value in (-1, float("nan"), True):
            data = self.read()
            data["credits"][0]["awarded_units"] = value
            self.write(data)
            with self.assertRaises(PlanningError):
                Workspace(self.root).load()

    def test_edited_evidence_rejected(self):
        data = self.read()
        source = self.root / data["source_keys"]["audit"].split("#")[0]
        source.write_text("changed original")
        with self.assertRaisesRegex(PlanningError, "changed source"):
            Workspace(self.root).load()

    def test_nested_approval_evidence_is_checked(self):
        abroad = self.read("abroad.yaml")
        abroad["approved_courses"] = [
            {"course": "APPROVED", "approval_source": "sources/missing.md"}
        ]
        self.write(abroad, "abroad.yaml")
        with self.assertRaisesRegex(PlanningError, "Missing evidence"):
            Workspace(self.root).load()

    def test_wrong_term_offering_and_proposal_status_rejected(self):
        data = self.read()
        data["term_proposal"]["availability_check"]["term"] = "Spring 2032"
        self.write(data)
        with self.assertRaisesRegex(PlanningError, "own term"):
            Workspace(self.root).load()
        data["term_proposal"]["availability_check"]["term"] = "Winter 2032"
        data["assignments"][0]["status"] = "proposed"
        self.write(data)
        with self.assertRaisesRegex(PlanningError, "Assignments need"):
            Workspace(self.root).load()

    def test_duplicate_assignments_rejected(self):
        data = self.read()
        data["assignments"].append(copy.deepcopy(data["assignments"][0]))
        self.write(data)
        with self.assertRaisesRegex(PlanningError, "multiply assigned"):
            Workspace(self.root).load()

    def test_candidate_time_conflicts_rejected(self):
        data = self.read()
        data["term_proposal"]["candidate_sections"] = [
            {"days": ["M"], "start": "10:00", "end": "11:00"},
            {"days": ["M"], "start": "10:30", "end": "11:30"},
        ]
        self.write(data)
        with self.assertRaisesRegex(PlanningError, "overlap"):
            Workspace(self.root).load()

    def test_output_edits_stop_generation(self):
        ws = Workspace(self.root)
        target = ws.output / "Current-Academic-Record.md"
        target.write_text("Independent output change")
        before = {p.name: digest(p) for p in ws.output.iterdir() if p.is_file()}
        with self.assertRaisesRegex(PlanningError, "Output edited"):
            ws.build()
        self.assertEqual(
            before, {p.name: digest(p) for p in ws.output.iterdir() if p.is_file()}
        )

    def test_unmanaged_artifacts_are_not_overwritten(self):
        ws = Workspace(self.root)
        ws.state_path.unlink()
        with self.assertRaisesRegex(PlanningError, "lack.*manifest"):
            ws.build()

    def test_rebuild_preserves_history_and_detects_midbuild_change(self):
        ws = Workspace(self.root)
        old = digest(ws.output / "Academic-Planner.xlsx")
        ws.build()
        backups = list((ws.output / "history").glob("*/Academic-Planner.xlsx"))
        self.assertTrue(any(digest(p) == old for p in backups))
        from academic_planning.render import render_all

        def edit_during_build(workspace, folder):
            render_all(workspace, folder)
            (self.root / "knowledge/goals/academic-career.md").write_text(
                "Changed during generation"
            )

        state = digest(ws.state_path)
        with patch(
            "academic_planning.render.render_all", side_effect=edit_during_build
        ):
            with self.assertRaisesRegex(PlanningError, "Inputs changed"):
                ws.build()
        self.assertEqual(state, digest(ws.state_path))

    def test_source_strings_are_not_excel_formulas(self):
        data = self.read()
        data["requirements"][0]["notes"] = (
            '=HYPERLINK("https://example.invalid","source text")'
        )
        self.write(data)
        Workspace(self.root).build()
        book = openpyxl.load_workbook(
            Workspace(self.root).output / "Academic-Planner.xlsx", data_only=False
        )
        self.assertEqual(book["Requirements"]["G6"].data_type, "s")

    def test_negative_remaining_units_stop_at_zero(self):
        data = self.read()
        data["audit_snapshot"].update(
            minimum_degree_units=5,
            remaining_earned_units_to_minimum=0,
            remaining_units_if_in_progress_completed=0,
        )
        self.write(data)
        Workspace(self.root).build()
        book = openpyxl.load_workbook(
            Workspace(self.root).output / "Academic-Planner.xlsx", data_only=True
        )
        self.assertEqual(
            {r[0].value: r[2].value for r in book["Credit Record"].iter_rows()}[
                "Remaining on earned basis"
            ],
            0,
        )

    def test_import_preserves_manifest_metadata_and_reuses_bytes(self):
        path = self.root / ".student-workspace/source-manifest.json"
        manifest = json.loads(path.read_text())
        manifest["custom"]["keep"] = {"nested": "metadata"}
        manifest["external_references"] = [
            {"path": "external.txt", "label": "Keep external index"}
        ]
        path.write_bytes(json_bytes(manifest))
        evidence = self.base / "new evidence.txt"
        evidence.write_bytes(b"Original\x00bytes\r\n")
        first = import_source(self.root, evidence)
        self.assertEqual(
            (self.root / first["stored_path"]).read_bytes(), evidence.read_bytes()
        )
        self.assertTrue(import_source(self.root, evidence)["reused"])
        updated = json.loads(path.read_text())
        self.assertEqual(updated["custom"], manifest["custom"])
        self.assertEqual(
            updated["external_references"], manifest["external_references"]
        )

    def test_init_keeps_existing_records_and_rejects_future_version(self):
        before = digest(self.root / "knowledge/academics/academic.yaml")
        self.assertEqual(initialize(self.root)["created"], [])
        self.assertEqual(
            before, digest(self.root / "knowledge/academics/academic.yaml")
        )
        data = self.read()
        data["schema_version"] = 99
        self.write(data)
        with self.assertRaisesRegex(PlanningError, "Unsupported"):
            initialize(self.root)

    def test_paths_cannot_escape(self):
        for path in (
            "../outside",
            "sources/../escape",
            "C:/absolute",
            "sources\\escape",
        ):
            with self.assertRaises(PlanningError):
                within(self.root, path)

    def test_future_config_blocks_initialization_before_creating_records(self):
        (self.root / "knowledge/academics/planning-config.json").write_bytes(
            json_bytes({"schema_version": 2})
        )
        goals = self.root / "knowledge/goals/academic-career.md"
        goals.unlink()
        with self.assertRaisesRegex(PlanningError, "configuration version"):
            initialize(self.root)
        self.assertFalse(goals.exists())

    def test_later_gpa_and_approval_replace_unknown_output(self):
        data = self.read()
        data["profile"]["current_gpa"] = 3.8
        self.write(data)
        abroad = self.read("abroad.yaml")
        abroad["approved_courses"] = [
            {
                "course": "EXAMPLE APPROVED",
                "degree_use": "Example elective",
                "approval_source": data["source_keys"]["audit"],
            }
        ]
        self.write(abroad, "abroad.yaml")
        ws = Workspace(self.root)
        ws.build()
        advising = "\n".join(
            p.extract_text()
            for p in PdfReader(ws.output / "Academic-Advising.pdf").pages
        )
        brief = "\n".join(
            p.extract_text() for p in PdfReader(ws.output / "Abroad-Brief.pdf").pages
        )
        self.assertIn("GPA: 3.8", advising)
        self.assertNotIn("No approved abroad courses", brief)
        self.assertIn("EXAMPLE APPROVED", brief)
        self.assertIn(
            "GPA: 3.8", (ws.output / "Current-Academic-Record.md").read_text()
        )

    def test_partial_publish_failure_restores_previous_output_set(self):
        ws = Workspace(self.root)
        before = {
            name: digest(ws.output / name)
            for name in ws.names + ["build-manifest.json"]
        }
        from academic_planning import core

        real_replace = core.os.replace
        failed = False

        def fail_once(source, target):
            nonlocal failed
            if Path(target).name == "Academic-Advising.pdf" and not failed:
                failed = True
                raise OSError("Synthetic publication failure")
            return real_replace(source, target)

        with patch("academic_planning.core.os.replace", side_effect=fail_once):
            with self.assertRaisesRegex(OSError, "Synthetic publication"):
                ws.build()
        self.assertEqual(before, {name: digest(ws.output / name) for name in before})

    def test_empty_records_build_without_fabricated_profile(self):
        empty = self.base / "empty"
        initialize_workspace(empty)
        initialize(empty)
        result = Workspace(empty).check()
        self.assertFalse(result["outputs_built"])
        Workspace(empty).build()
        self.assertIsNone(Workspace(empty).check()["earned_units"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
