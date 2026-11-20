"""Registration with student-workspace: setup hook, skills and the workspace-wide check."""

from pathlib import Path
import tempfile
import unittest

from student_workspace.check import check_workspace
from student_workspace.tools import load_manifest, register_tool
from student_workspace.workspace import initialize_workspace

from academic_planning.core import Workspace

REPO = Path(__file__).parent.parent


class ToolTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name) / "workspace"
        initialize_workspace(self.root)

    def test_manifest_lists_existing_skills_and_instructions(self):
        manifest = load_manifest(REPO)
        self.assertEqual(manifest["name"], "academic-planning")
        self.assertTrue((REPO / manifest["instructions"]).is_file())
        for skill in manifest["skills"]:
            self.assertTrue((REPO / "skills" / skill / "SKILL.md").is_file(), skill)

    def test_registration_initializes_records_and_check_is_current_then_stale(self):
        result = register_tool(self.root, REPO)
        self.assertEqual(result["setup"]["exit_code"], 0)
        self.assertTrue((self.root / "knowledge/academics/academic.yaml").is_file())
        for skill in ("plan-academics", "audit-academic-planning"):
            self.assertTrue((self.root / ".agents/skills" / skill / "SKILL.md").is_file())
        self.assertIn("## Academic planning", (self.root / "WORKSPACE.md").read_text(encoding="utf-8"))
        self.assertEqual(check_workspace(self.root)["exit_code"], 0)
        Workspace(self.root).build()
        self.assertEqual(check_workspace(self.root)["exit_code"], 0)
        goals = self.root / "knowledge/goals/academic-career.md"
        goals.write_text(goals.read_text(encoding="utf-8") + "\nA changed goal.\n", encoding="utf-8")
        report = check_workspace(self.root)
        self.assertEqual((report["status"], report["exit_code"]), ("stale", 2))
        detail = next(item["detail"] for item in report["results"] if item["name"] == "academic-planning")
        self.assertEqual(len(detail), 1)
        self.assertIn("outputs are out of date", detail[0])


if __name__ == "__main__":
    unittest.main(verbosity=2)
