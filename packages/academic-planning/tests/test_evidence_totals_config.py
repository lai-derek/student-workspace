"""Evidence coverage and config consistency regressions; synthetic records only."""

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

from academic_planning import core
from academic_planning.core import (
    PlanningError,
    Workspace,
    digest,
    import_source,
    json_bytes,
)
from academic_planning.records import demo, initialize
from academic_planning.render import render_all


class EvidenceTotalsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "student"
        initialize_workspace(self.root)
        initialize(self.root)
        original = Path(self.temp.name) / "evidence.md"
        original.write_text(
            "# Synthetic evidence\n\nOne degree requirement; no transcript or current-enrollment completeness claim.\n"
        )
        self.ref = import_source(self.root, original)["stored_path"]

    def read(self):
        return yaml.safe_load(
            (self.root / "knowledge/academics/academic.yaml").read_text()
        )

    def save(self, data):
        (self.root / "knowledge/academics/academic.yaml").write_text(
            yaml.safe_dump(data, sort_keys=False), encoding="utf-8"
        )

    def complete(self):
        return {"status": "complete", "as_of": "2031-10-01", "source_refs": [self.ref]}

    def credit(self):
        return {
            "id": "award-a",
            "institution": "Example College",
            "course": "EXAMPLE 1",
            "term": "Spring 2031",
            "kind": "transfer",
            "awarded_units": 4,
            "evidence_date": "2031-09-01",
            "source_refs": [self.ref],
        }

    def rendered(self):
        ws = Workspace(self.root)
        ws.build()
        check = ws.check()
        context = ws.context("record")
        self.assertFalse(check["outputs_stale"])
        self.assertEqual(check["earned_units"], context["earned_units"])
        self.assertEqual(check["in_progress_units"], context["in_progress_units"])
        folder = ws.output
        pdf = " ".join(
            " ".join(
                p.extract_text()
                for p in PdfReader(folder / "Academic-Advising.pdf").pages
            ).split()
        )
        md = (folder / "Current-Academic-Record.md").read_text()
        book = openpyxl.load_workbook(folder / "Academic-Planner.xlsx", data_only=True)
        values = {r[0].value: r[2].value for r in book["Credit Record"].iter_rows()}
        return check, pdf, md, values

    def assert_unknown(self, domain, check, pdf, md, values):
        field = "earned_units" if domain == "credits" else "in_progress_units"
        label = "Earned credit" if domain == "credits" else "In-progress credit"
        cell = "Earned units" if domain == "credits" else "In progress (not earned)"
        self.assertIsNone(check[field])
        self.assertIn(label + ": unknown (not established)", pdf)
        self.assertIn(label + ": unknown (not established)", md)
        self.assertEqual(values[cell], "Unknown")

    def test_empty_intake_has_unknown_domain_totals_and_labeled_zero_subtotals(self):
        output = self.rendered()
        self.assert_unknown("credits", *output)
        self.assert_unknown("current_coursework", *output)
        self.assertEqual(output[0]["recorded_earned_units"], 0)
        self.assertEqual(output[3]["Recorded award subtotal"], 0)
        self.assertEqual(output[3]["Recorded coursework subtotal"], 0)
        for key in (
            "remaining_earned_units_to_minimum",
            "remaining_units_if_in_progress_completed",
        ):
            self.assertIsNone(output[0][key])

    def test_requirement_only_does_not_establish_either_total(self):
        data = self.read()
        data["requirements"] = [
            {
                "id": "req-a",
                "requirement": "Example degree requirement",
                "status": "remaining",
                "units": 4,
                "source_refs": [self.ref],
            }
        ]
        self.save(data)
        output = self.rendered()
        self.assertTrue(output[0]["intake_populated"])
        self.assert_unknown("credits", *output)
        self.assert_unknown("current_coursework", *output)

    def test_coursework_only_is_a_partial_subtotal_not_an_enrollment_total(self):
        data = self.read()
        data["current_coursework"] = [
            {
                "course": "EXAMPLE CURRENT",
                "units": 4,
                "status": "in-progress",
                "source_refs": [self.ref],
            }
        ]
        data.pop("record_coverage")
        self.save(data)
        output = self.rendered()
        self.assert_unknown("credits", *output)
        self.assert_unknown("current_coursework", *output)
        self.assertEqual(output[0]["recorded_in_progress_units"], 4)
        self.assertEqual(
            output[0]["unit_coverage"]["current_coursework"]["status"], "partial"
        )
        self.assertEqual(output[3]["Recorded coursework subtotal"], 4)

    def test_partial_credit_keeps_subtotal_separate_from_unknown_earned_total(self):
        data = self.read()
        data["credits"] = [self.credit()]
        data["record_coverage"]["credits"] = {"status": "partial"}
        self.save(data)
        output = self.rendered()
        self.assert_unknown("credits", *output)
        self.assert_unknown("current_coursework", *output)
        self.assertEqual(output[0]["recorded_earned_units"], 4)
        self.assertEqual(output[3]["Recorded award subtotal"], 4)

    def test_complete_one_domain_does_not_complete_other_domain_or_remaining_units(
        self,
    ):
        data = self.read()
        data["credits"] = [self.credit()]
        data["record_coverage"]["credits"] = self.complete()
        data["audit_snapshot"] = {
            "as_of": "2031-10-01",
            "minimum_degree_units": 120,
            "source_refs": [self.ref],
        }
        self.save(data)
        output = self.rendered()
        self.assertEqual(output[0]["earned_units"], 4)
        self.assert_unknown("current_coursework", *output)
        self.assertEqual(output[3]["Remaining on earned basis"], 116)
        self.assertEqual(output[3]["Remaining if current work completes"], "Unknown")

    def test_minimum_with_incomplete_domains_does_not_compute_remaining_from_subtotals(
        self,
    ):
        data = self.read()
        data["credits"] = [self.credit()]
        data["audit_snapshot"] = {
            "as_of": "2031-10-01",
            "minimum_degree_units": 120,
            "source_refs": [self.ref],
        }
        self.save(data)
        output = self.rendered()
        self.assertIsNone(output[0]["remaining_earned_units_to_minimum"])
        self.assertEqual(output[3]["Degree minimum"], 120)
        self.assertEqual(output[3]["Remaining on earned basis"], "Unknown")
        self.assertEqual(output[3]["Remaining if current work completes"], "Unknown")

    def test_explicit_verified_zero_totals_remain_numeric(self):
        data = self.read()
        data["record_coverage"] = {
            "credits": self.complete(),
            "current_coursework": self.complete(),
        }
        self.save(data)
        check, pdf, md, cells = self.rendered()
        self.assertTrue(check["intake_populated"])
        self.assertEqual((check["earned_units"], check["in_progress_units"]), (0, 0))
        self.assertIn("Earned credit: 0 quarter units", pdf)
        self.assertIn("In-progress credit: 0 quarter units", md)
        self.assertEqual(
            (cells["Earned units"], cells["In progress (not earned)"]), (0, 0)
        )

    def test_sourced_audit_zero_and_existing_full_audit_keep_numeric_totals(self):
        data = self.read()
        data.pop("record_coverage")
        data["audit_snapshot"] = {
            "as_of": "2031-10-01",
            "source_refs": [self.ref],
            "earned_units": 0,
            "in_progress_units": 0,
            "minimum_degree_units": 120,
        }
        self.save(data)
        check, _, _, cells = self.rendered()
        self.assertTrue(check["intake_populated"])
        self.assertEqual((check["earned_units"], check["in_progress_units"]), (0, 0))
        self.assertEqual(cells["Remaining on earned basis"], 120)
        complete = Path(self.temp.name) / "complete"
        demo(complete)
        self.assertEqual(
            (
                Workspace(complete).check()["earned_units"],
                Workspace(complete).check()["in_progress_units"],
            ),
            (13, 4),
        )

    def test_partial_ledger_may_coexist_with_separately_evidenced_audit_total(self):
        data = self.read()
        data["credits"] = [self.credit()]
        data["record_coverage"]["credits"] = {"status": "partial"}
        data["audit_snapshot"] = {
            "as_of": "2031-10-01",
            "source_refs": [self.ref],
            "earned_units": 13,
            "minimum_degree_units": 120,
        }
        self.save(data)
        output = self.rendered()
        self.assertEqual(
            (output[0]["earned_units"], output[0]["recorded_earned_units"]), (13, 4)
        )
        self.assertEqual(output[3]["Earned units"], 13)
        self.assertEqual(output[3]["Recorded award subtotal"], 4)
        self.assertEqual(output[3]["Remaining on earned basis"], 107)

    def test_complete_coverage_needs_its_own_dated_registered_evidence(self):
        baseline = self.read()
        for entry in [
            {"status": "complete"},
            {"status": "complete", "as_of": "invalid", "source_refs": [self.ref]},
            {
                "status": "complete",
                "as_of": "2031-10-01",
                "source_refs": ["sources/missing.md"],
            },
        ]:
            data = copy.deepcopy(baseline)
            data["record_coverage"]["credits"] = entry
            self.save(data)
            with self.assertRaises(PlanningError):
                Workspace(self.root).load()

    def test_unsourced_audit_and_unsupported_remaining_assertions_rejected(self):
        for snapshot in [
            {"as_of": "2031-10-01", "earned_units": 0},
            {
                "as_of": "2031-10-01",
                "minimum_degree_units": 120,
                "source_refs": [self.ref],
                "remaining_earned_units_to_minimum": 120,
            },
        ]:
            data = self.read()
            data["audit_snapshot"] = snapshot
            self.save(data)
            with self.assertRaises(PlanningError):
                Workspace(self.root).load()


class ConfigurationSnapshotTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "student"
        demo(self.root)
        self.ws = Workspace(self.root)
        self.config = self.root / "knowledge/academics/planning-config.json"

    def configure(self, **changes):
        data = json.loads(self.config.read_text())
        data.update(changes)
        self.config.write_bytes(json_bytes(data))

    def output_hashes(self):
        return {p.name: digest(p) for p in self.ws.output.iterdir() if p.is_file()}

    def test_reused_instance_builds_and_certifies_current_unit_label(self):
        self.configure(unit_label="semester units")
        self.ws.build()
        result = Workspace(self.root).check()
        self.assertFalse(result["outputs_stale"])
        self.assertEqual(result["unit_label"], "semester units")
        md = (self.ws.output / "Current-Academic-Record.md").read_text()
        self.assertIn("Earned credit: 13 semester units", md)
        self.assertNotIn("13 quarter units", md)
        self.assertEqual(self.ws.context("record")["unit_label"], "semester units")

    def test_change_after_load_and_missing_config_creation_or_deletion_refreshes(self):
        self.ws.load()
        self.configure(unit_label="changed units")
        self.ws.build()
        self.assertEqual(self.ws.unit_label, "changed units")
        self.config.unlink()
        self.ws.build()
        self.assertEqual(self.ws.unit_label, "quarter units")
        self.config.write_bytes(
            json_bytes({"schema_version": 1, "unit_label": "new units"})
        )
        self.ws.build()
        self.assertEqual(self.ws.check()["unit_label"], "new units")

    def test_changed_period_order_is_consumed_and_rendered(self):
        record = self.root / "knowledge/academics/academic.yaml"
        data = yaml.safe_load(record.read_text())
        second = dict(
            data["assignments"][0],
            requirement_id="req-lab",
            course="EXAMPLE LAB",
            term="Winter 2031",
            units=2,
            status="planned",
        )
        data["assignments"].append(second)
        record.write_text(yaml.safe_dump(data), encoding="utf-8")
        self.configure(period_order=["Fall", "Winter", "Spring", "Summer"])
        self.ws.build()
        book = openpyxl.load_workbook(
            self.ws.output / "Academic-Planner.xlsx", data_only=True
        )
        self.assertEqual(
            [book["Quarter Plan"]["A6"].value, book["Quarter Plan"]["A7"].value],
            ["Fall 2031", "Winter 2031"],
        )
        self.assertFalse(Workspace(self.root).check()["outputs_stale"])

    def test_newly_unsupported_version_stops_load_check_and_build(self):
        before = self.output_hashes()
        self.configure(schema_version=99)
        for operation in (self.ws.load, self.ws.check, self.ws.build):
            with self.assertRaisesRegex(
                PlanningError, "Unsupported planning configuration"
            ):
                operation()
        self.assertEqual(before, self.output_hashes())

    def test_new_period_set_revalidates_existing_record_terms(self):
        before = self.output_hashes()
        self.configure(period_order=["Semester"])
        with self.assertRaisesRegex(PlanningError, "Unsupported term"):
            self.ws.build()
        self.assertEqual(before, self.output_hashes())

    def test_mutation_during_record_load_is_not_certified(self):
        real_read = core.object_file
        before = self.output_hashes()

        def mutate(path, yaml_file=False):
            result = real_read(path, yaml_file)
            if Path(path).name == "academic.yaml":
                self.configure(unit_label="mutated while loading")
            return result

        with patch("academic_planning.core.object_file", side_effect=mutate):
            with self.assertRaisesRegex(PlanningError, "Configuration changed"):
                self.ws.build()
        self.assertEqual(before, self.output_hashes())

    def test_mutation_during_render_preserves_previous_outputs(self):
        before = self.output_hashes()

        def mutate(workspace, stage):
            render_all(workspace, stage)
            self.configure(unit_label="mutated while rendering")

        with patch("academic_planning.render.render_all", side_effect=mutate):
            with self.assertRaisesRegex(PlanningError, "Configuration changed"):
                self.ws.build()
        self.assertEqual(before, self.output_hashes())
        self.assertTrue(Workspace(self.root).check()["outputs_stale"])


if __name__ == "__main__":
    unittest.main()
