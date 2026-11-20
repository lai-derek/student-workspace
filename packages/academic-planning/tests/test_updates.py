import copy
import hashlib
from pathlib import Path
import tempfile
import unittest

import openpyxl
from pypdf import PdfReader
import yaml
from student_workspace.workspace import initialize_workspace

from academic_planning.core import PlanningError, Workspace, import_source, json_bytes
from academic_planning.records import demo, initialize
from academic_planning.planning import recognition_options

PROTECTED = ["knowledge/academics", "knowledge/goals", ".student-workspace/source-manifest.json"]


def inventories(root, relatives):
    """SHA-256 of every file below each relative path (None when absent)."""
    result = {}
    for relative in relatives:
        path = Path(root) / relative
        if not path.exists():
            result[relative] = None
        elif path.is_file():
            result[relative] = {"": hashlib.sha256(path.read_bytes()).hexdigest()}
        else:
            result[relative] = {
                item.relative_to(path).as_posix(): hashlib.sha256(item.read_bytes()).hexdigest()
                for item in sorted(path.rglob("*"))
                if item.is_file()
            }
    return result


class StudentFixture(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.root = self.base / "student"
        demo(self.root)

    def read(self, name="academic.yaml"):
        return yaml.safe_load(
            (self.root / "knowledge/academics" / name).read_text(encoding="utf-8")
        )

    def write(self, data, name="academic.yaml"):
        (self.root / "knowledge/academics" / name).write_text(
            yaml.safe_dump(data, sort_keys=False), encoding="utf-8"
        )

    def recognized(self):
        data = self.read()
        ref = data["source_keys"]["audit"]
        data["recognition_options"] = [
            {
                "id": "option-a",
                "area": "Example area",
                "eligibility": "approved",
                "credit_ids": ["credit-math"],
                "requirement_ids": ["req-foundation", "req-lab"],
                "minimum_courses": 2,
                "minimum_units": 12,
                "approval_source": ref,
                "declaration_status": "unconfirmed",
                "dars_application": "unconfirmed",
                "implementation_notes": "Synthetic advisor instruction; not area selection.",
            }
        ]
        self.write(data)
        return data

    def research(self):
        data = self.recognized()
        ref = data["source_keys"]["audit"]
        data["research_updates"] = [
            {
                "id": "new",
                "as_of": "2031-10-02",
                "topic": "Eligibility",
                "summary": "Written ruling replaces only the named uncertainty.",
                "source_refs": [ref],
                "supersedes": [
                    {"scope": "Existing award eligibility only", "source_refs": [ref]}
                ],
            },
            {
                "id": "other",
                "as_of": "2031-10-02",
                "topic": "Course access",
                "summary": "Other claim from the same source remains unresolved.",
                "source_refs": [ref],
            },
        ]
        self.write(data)
        return data


class UpdateTests(StudentFixture):
    def test_recognition_derives_both_minima_without_awarding_or_selecting(self):
        data = self.recognized()
        before = copy.deepcopy(data)
        option = recognition_options(data)[0]
        self.assertEqual(
            (option["approved_existing_courses"], option["existing_awarded_units"]),
            (1, 9),
        )
        self.assertEqual(
            (option["new_courses_remaining"], option["new_units_remaining"]), (1, 3)
        )
        self.assertEqual(data, before)
        self.assertEqual(Workspace(self.root).context("record")["earned_units"], 13)
        self.assertFalse(
            self.read("abroad.yaml").get("breadth_exploration", {}).get("selected")
        )

    def test_pending_and_rejected_recognition_use_no_awards(self):
        for status in ("pending", "rejected"):
            data = self.recognized()
            data["recognition_options"][0].update(eligibility=status)
            del data["recognition_options"][0]["approval_source"]
            self.write(data)
            result = Workspace(self.root).context("record")["recognition_options"][0]
            self.assertEqual(
                (
                    result["existing_awarded_units"],
                    result["new_courses_remaining"],
                    result["new_units_remaining"],
                ),
                (0, 2, 12),
            )

    def test_recognition_rejects_bad_links_minima_and_missing_authority(self):
        base = self.recognized()
        mutations = [
            {"credit_ids": ["credit-math", "credit-math"]},
            {"credit_ids": ["missing"]},
            {"credit_ids": ["credit-duplicate"]},
            {"requirement_ids": ["missing"]},
            {"minimum_courses": True},
            {"minimum_units": float("inf")},
            {"approval_source": ""},
        ]
        for mutation in mutations:
            data = copy.deepcopy(base)
            data["recognition_options"][0].update(mutation)
            self.write(data)
            with self.assertRaises(PlanningError):
                Workspace(self.root).load()

    def test_declaration_and_audit_posting_each_need_checked_evidence(self):
        base = self.recognized()
        for state, source in [
            ("declaration_status", "declaration_source"),
            ("dars_application", "dars_source"),
        ]:
            data = copy.deepcopy(base)
            data["recognition_options"][0][state] = "confirmed"
            self.write(data)
            with self.assertRaisesRegex(PlanningError, "own evidence"):
                Workspace(self.root).load()
            data["recognition_options"][0][source] = "sources/missing.md"
            self.write(data)
            with self.assertRaisesRegex(PlanningError, "Missing evidence"):
                Workspace(self.root).load()
            data["recognition_options"][0][source] = data["source_keys"]["audit"]
            self.write(data)
            Workspace(self.root).load()

    def test_historical_source_inventory_checks_preserved_sources(self):
        data = self.read()
        relative = data["source_keys"]["audit"].split("#")[0]
        from academic_planning.core import digest

        path = self.root / "knowledge/academics/source-inventory.json"
        inventory = {
            "files": [
                {
                    "stored_path": relative,
                    "sha256": digest(self.root / relative),
                    "disposition": "preserved",
                }
            ]
        }
        path.write_bytes(json_bytes(inventory))
        Workspace(self.root).load()
        inventory["files"][0]["sha256"] = "0" * 64
        path.write_bytes(json_bytes(inventory))
        with self.assertRaisesRegex(PlanningError, "Historical inventory"):
            Workspace(self.root).load()

    def test_obsolete_ruling_rejected(self):
        data = self.read()
        data["breadth_credit_ruling"] = {"declared": True}
        self.write(data)
        with self.assertRaisesRegex(PlanningError, "Obsolete"):
            Workspace(self.root).load()

    def test_scoped_research_keeps_shared_source_claims_in_all_views(self):
        self.research()
        abroad = self.read("abroad.yaml")
        abroad["research_updates"] = self.read()["research_updates"]
        abroad["useful_requirement_ids"] = ["req-lab"]
        abroad["load_planning"] = {
            "summary": "Load conversion unresolved",
            "unresolved": "Host faculty classification unknown",
        }
        self.write(abroad, "abroad.yaml")
        Workspace(self.root).build()
        folder = Workspace(self.root).output
        for name in ("Academic-Advising.pdf", "Abroad-Brief.pdf"):
            text = " ".join(
                " ".join(
                    p.extract_text() for p in PdfReader(folder / name).pages
                ).split()
            )
            self.assertIn("Other claim from the same source", text)
            self.assertIn("Supersedes only", text)
            self.assertIn("1 course(s), at least 3 units", text)
        markdown = (folder / "Current-Academic-Record.md").read_text()
        self.assertIn("Existing award eligibility only", markdown)
        self.assertIn("Load conversion unresolved", markdown)
        book = openpyxl.load_workbook(folder / "Academic-Planner.xlsx", data_only=True)
        self.assertTrue(
            any(
                "1 course(s), at least 3 units" in str(c.value)
                for row in book["Credit Record"]
                for c in row
            )
        )
        self.assertEqual(
            Workspace(self.root).context("abroad")["useful_requirements"][0]["id"],
            "req-lab",
        )

    def test_research_requires_scope_date_links_and_unique_ids(self):
        base = self.research()
        for change in ("scope", "date", "prior", "duplicate"):
            data = copy.deepcopy(base)
            row = data["research_updates"][0]
            if change == "scope":
                row["supersedes"][0]["scope"] = ""
            if change == "date":
                row["as_of"] = "not-a-date"
            if change == "prior":
                row["supersedes"][0]["source_refs"] = ["sources/missing.md"]
            if change == "duplicate":
                data["research_updates"].append(copy.deepcopy(row))
            self.write(data)
            with self.assertRaises(PlanningError):
                Workspace(self.root).load()

    def test_fresh_workspace_records_and_import_need_no_opportunity_profile(self):
        root = self.base / "fresh"
        initialize_workspace(root)
        initialize(root)
        Workspace(root).build()
        self.assertFalse((root / "knowledge/academics/abroad.yaml").exists())
        self.assertEqual(Workspace(root).context("record")["profile"], {})
        self.assertEqual(len(Workspace(root).build()["built"]), 3)
        self.assertNotIn(
            "Abroad goal",
            (
                root / "artifacts/academic-planning/Current-Academic-Record.md"
            ).read_text(),
        )
        source = self.base / "audit.pdf"
        source.write_bytes(b"Synthetic unparsed PDF bytes")
        registered = import_source(root, source)
        self.assertEqual(
            (root / registered["stored_path"]).read_bytes(), source.read_bytes()
        )
        self.assertEqual(Workspace(root).context("record")["requirements"], 0)
        self.assertTrue((root / "knowledge/academics/INTAKE.md").exists())
        self.assertEqual(initialize(root)["created"], [])

    def test_optional_abroad_enable_disable_archives_only_owned_brief(self):
        root = self.base / "fresh"
        initialize_workspace(root)
        initialize(root)
        Workspace(root).build()
        initialize(root, with_abroad=True)
        self.assertTrue(Workspace(root).check()["outputs_stale"])
        Workspace(root).build()
        output = root / "artifacts/academic-planning"
        self.assertTrue((output / "Abroad-Brief.pdf").exists())
        (root / "knowledge/academics/abroad.yaml").unlink()
        self.assertTrue(Workspace(root).check()["outputs_stale"])
        Workspace(root).build()
        self.assertFalse((output / "Abroad-Brief.pdf").exists())
        self.assertTrue(list((output / "history").glob("*/Abroad-Brief.pdf")))

    def test_optional_abroad_removal_cannot_discard_edited_brief(self):
        (self.root / "knowledge/academics/abroad.yaml").unlink()
        (self.root / "artifacts/academic-planning/Abroad-Brief.pdf").write_bytes(
            b"user edited"
        )
        with self.assertRaisesRegex(PlanningError, "edited independently"):
            Workspace(self.root).build()

    def test_existing_unowned_optional_report_is_not_overwritten(self):
        root = self.base / "fresh"
        initialize_workspace(root)
        initialize(root)
        Workspace(root).build()
        brief = root / "artifacts/academic-planning/Abroad-Brief.pdf"
        brief.write_bytes(b"unowned report")
        initialize(root, with_abroad=True)
        with self.assertRaisesRegex(PlanningError, "Unmanaged output"):
            Workspace(root).build()
        self.assertEqual(brief.read_bytes(), b"unowned report")

    def test_unpopulated_intake_is_not_presented_as_zero_earned_facts(self):
        root = self.base / "empty"
        initialize_workspace(root)
        initialize(root)
        Workspace(root).build()
        self.assertFalse(Workspace(root).check()["intake_populated"])
        folder = root / "artifacts/academic-planning"
        text = " ".join(
            p.extract_text() for p in PdfReader(folder / "Academic-Advising.pdf").pages
        )
        self.assertIn("not established", text)
        self.assertNotIn("Earned: 0", text)
        self.assertIn(
            "unknown (not established)",
            (folder / "Current-Academic-Record.md").read_text(),
        )

    def test_future_record_initialization_is_rejected(self):
        root = self.base / "future"
        initialize_workspace(root)
        path = root / "knowledge/academics/academic.yaml"
        path.parent.mkdir(parents=True)
        path.write_text("schema_version: 99")
        with self.assertRaisesRegex(PlanningError, "Unsupported"):
            initialize(root)

    def test_context_read_only_routes_to_real_proposal_and_pending_states(self):
        self.recognized()
        term = self.root / "knowledge/academics/WINTER-2032.md"
        term.write_text("Synthetic term narrative")
        before = inventories(self.root, PROTECTED)
        view = Workspace(self.root).context("term")
        self.assertIn("knowledge/academics/WINTER-2032.md", view["read_next"])
        self.assertNotIn("recognition_options", view)
        self.assertEqual(inventories(self.root, PROTECTED), before)



if __name__ == "__main__":
    unittest.main()
