"""Synthetic scheduling tests; no personal records or live services."""

import copy
from contextlib import closing
import json
import os
import itertools
import random
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import unittest

from academic_planning import scheduling as s


def sample():
    def section(sid, cid, start, end, days=None):
        return {
            "id": sid,
            "course_id": cid,
            "component": "lecture",
            "label": sid,
            "availability": "open",
            "meeting_status": "scheduled",
            "location": "Campus A",
            "meetings": [{"days": days or ["M", "W"], "start": start, "end": end}],
            "exams": [],
        }

    return {
        "version": 1,
        "id": "synthetic-1",
        "institution": "UCLA",
        "term": "Winter 2031",
        "observed_at": "2030-11-01",
        "sources": [{"url": "https://example.edu/catalog"}],
        "courses": [
            {"id": "ART", "title": "Art methods", "units": 4, "aliases": ["ARTS"]},
            {"id": "STAT", "title": "Statistics", "units": 5},
        ],
        "sections": [
            section("A8", "ART", "08:00", "09:00"),
            section("A12", "ART", "12:00", "13:00"),
            section("S9", "STAT", "09:00", "10:00"),
        ],
        "bundles": [
            {"id": "b-" + sid, "course_id": cid, "section_ids": [sid]}
            for sid, cid in [("A8", "ART"), ("A12", "ART"), ("S9", "STAT")]
        ],
    }


def request():
    return {
        "version": 1,
        "snapshot_id": "synthetic-1",
        "scenarios": [{"id": "primary", "course_ids": ["ART", "STAT"]}],
        "eligibility": {"ART": "eligible", "STAT": "eligible"},
        "preferences": [{"kind": "before", "time": "10:00"}],
        "count": 3,
    }


class SchedulingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.db = s.connect(self.root / "schedules.sqlite", True)
        self.data = sample()

    def tearDown(self):
        self.db.close()
        self.temp.cleanup()

    def run_case(self, req=None):
        s.import_snapshot(self.db, self.data)
        return s.solve(self.db, req or request())["scenarios"][0]

    def test_rank_units_adjacent_and_shortage(self):
        result = self.run_case()
        self.assertEqual(result["distinct_found"], 2)
        self.assertEqual(result["shortage"], 1)
        self.assertEqual(result["plans"][0]["section_ids"], ["A12", "S9"])
        self.assertEqual(result["plans"][0]["units"], 9)
        self.assertEqual(result["plans"][1]["score"], [4])

    def test_opposite_preferences(self):
        req = request()
        req["preferences"] = [{"kind": "after", "time": "11:00"}]
        self.assertEqual(self.run_case(req)["plans"][0]["section_ids"], ["A8", "S9"])

    def test_meeting_and_block_conflicts(self):
        self.data["sections"][1]["meetings"][0].update(start="09:30", end="10:30")
        req = request()
        req["blocks"] = [{"days": ["M"], "start": "08:00", "end": "08:30"}]
        result = self.run_case(req)
        self.assertEqual(result["distinct_found"], 0)
        self.assertEqual(
            set(result["rejected"]), {"meeting_conflict", "unavailable_time"}
        )

    def test_finals_same_day_allowed_unless_overlap(self):
        self.data["sections"][0]["exams"] = [
            {"date": "2031-03-18", "start": "08:00", "end": "11:00"}
        ]
        self.data["sections"][1]["exams"] = [
            {"date": "2031-03-18", "start": "10:00", "end": "12:00"}
        ]
        self.data["sections"][2]["exams"] = [
            {"date": "2031-03-18", "start": "11:00", "end": "14:00"}
        ]
        self.assertEqual(self.run_case()["plans"][0]["section_ids"], ["A8", "S9"])

    def test_unknown_information_is_conditional(self):
        self.data["sections"][1].update(
            meeting_status="unknown", meetings=[], exams=None, availability="unknown"
        )
        req = request()
        req.pop("eligibility")
        result = self.run_case(req)["plans"][0]
        self.assertEqual(result["verification"], "conditional")
        self.assertGreaterEqual(len(result["unresolved"]), 4)

    def test_linked_components_units_once(self):
        lab = copy.deepcopy(self.data["sections"][0])
        lab.update(id="LAB", component="laboratory", label="Lab 1")
        lab["meetings"][0]["days"] = ["F"]
        self.data["sections"].append(lab)
        self.data["bundles"][1]["section_ids"].append("LAB")
        req = request()
        req["locked_sections"] = ["LAB"]
        plan = self.run_case(req)["plans"][0]
        self.assertEqual(plan["section_ids"], ["A12", "LAB", "S9"])
        self.assertEqual(plan["units"], 9)

    def test_locks_exclusions_and_units(self):
        req = request()
        req.update(
            locked_sections=["A8"], excluded_sections=["A12"], min_units=9, max_units=9
        )
        self.assertEqual(self.run_case(req)["plans"][0]["section_ids"], ["A8", "S9"])

    def test_crosslist_no_access_assumption(self):
        self.data["courses"].append(
            {
                "id": "DESIGN",
                "title": "Crosslisting",
                "units": 4,
                "equivalence_group": "shared",
            }
        )
        self.data["courses"][0]["equivalence_group"] = "shared"
        section = copy.deepcopy(self.data["sections"][1])
        section.update(id="D12", course_id="DESIGN", availability="closed")
        self.data["sections"].append(section)
        self.data["bundles"].append(
            {"id": "design", "course_id": "DESIGN", "section_ids": ["D12"]}
        )
        req = request()
        req["scenarios"] = [{"id": "backup", "course_ids": ["DESIGN", "STAT"]}]
        self.assertEqual(self.run_case(req)["distinct_found"], 0)

    def test_equivalent_courses_not_double_counted(self):
        for course in self.data["courses"]:
            course["equivalence_group"] = "same-credit"
        self.assertEqual(
            self.run_case()["rejected"], {"duplicate_equivalent_course": 2}
        )

    def test_minimal_change_and_ties(self):
        req = request()
        req.update(baseline_sections=["A8", "S9"], preferences=[{"kind": "changes"}])
        result = self.run_case(req)
        self.assertEqual(result["plans"][0]["score"], [0])
        req["preferences"] = []
        first = s.solve(self.db, req)
        self.assertEqual(first, s.solve(self.db, req))
        self.assertEqual(len(first["scenarios"][0]["plans"]), 2)

    def test_truncation_and_unavailable_backups(self):
        req = request()
        req["search_limit"] = 1
        result = self.run_case(req)
        self.assertFalse(result["exhaustive"])
        self.assertEqual(result["examined"], 1)

    def test_travel_verified_and_estimated(self):
        self.data["sections"][2]["location"] = "Campus B"
        req = request()
        req["travel"] = [
            {"from": "Campus A", "to": "Campus B", "minutes": 20, "verified": True}
        ]
        result = self.run_case(req)
        self.assertEqual(result["distinct_found"], 1)
        req["travel"][0]["verified"] = False
        plans = s.solve(self.db, req)["scenarios"][0]["plans"]
        self.assertTrue(
            any("Travel unverified" in " ".join(p["unresolved"]) for p in plans)
        )

    def test_snapshot_import_immutable_and_idempotent(self):
        self.assertTrue(s.import_snapshot(self.db, self.data)["imported"])
        self.assertFalse(s.import_snapshot(self.db, self.data)["imported"])
        changed = copy.deepcopy(self.data)
        changed["sections"][0]["availability"] = "closed"
        with self.assertRaises(s.ScheduleError):
            s.import_snapshot(self.db, changed)
        changed["id"] = "synthetic-2"
        s.import_snapshot(self.db, changed)
        self.assertEqual(s.load(self.db, "snapshots", self.data["id"]), self.data)

    def test_invalid_import_has_no_partial_rows(self):
        self.data["bundles"][0]["section_ids"] = ["NO-SUCH-SECTION"]
        with self.assertRaises(s.ScheduleError):
            s.import_snapshot(self.db, self.data)
        self.assertEqual(
            self.db.execute("SELECT count(*) FROM snapshots").fetchone()[0], 0
        )

    def test_database_transaction_rolls_back(self):
        self.db.execute(
            "CREATE TRIGGER fail_bundle BEFORE INSERT ON bundles BEGIN SELECT RAISE(ABORT,'synthetic failure'); END"
        )
        with self.assertRaises(sqlite3.IntegrityError):
            s.import_snapshot(self.db, self.data)
        self.assertEqual(
            self.db.execute("SELECT count(*) FROM courses").fetchone()[0], 0
        )
        self.assertEqual(
            self.db.execute("SELECT count(*) FROM snapshots").fetchone()[0], 0
        )

    def test_receipt_detects_each_mismatch(self):
        plan = self.run_case()["plans"][0]
        observation = {
            "plan_id": plan["id"],
            "plan_name": "Synthetic plan",
            "term": plan["term"],
            "observed_at": "2030-11-02",
            "reloaded": True,
            "section_ids": plan["section_ids"],
            "units": plan["units"],
        }
        self.assertTrue(s.receipt(self.db, observation)["verified"])
        observation.update(
            section_ids=["A8"], units=4, term="Spring 2031", reloaded=False
        )
        result = s.receipt(self.db, observation)
        self.assertFalse(result["verified"])
        self.assertEqual(len(result["differences"]), 4)

    def test_backup_reopen_and_foreign_keys(self):
        self.run_case()
        destination = self.root / "backup.sqlite"
        s.backup(self.db, destination)
        restored = s.connect(destination)
        try:
            self.assertEqual(s.load(restored, "snapshots", self.data["id"]), self.data)
            with self.assertRaises(sqlite3.IntegrityError):
                restored.execute(
                    "INSERT INTO receipts(plan,payload) VALUES(?,?)", ("missing", "{}")
                )
        finally:
            restored.close()

    def test_unknown_input_fields_and_invalid_intervals(self):
        s.import_snapshot(self.db, self.data)
        req = request()
        req["avoid_mornings"] = True
        with self.assertRaises(s.ScheduleError):
            s.solve(self.db, req)
        for start, end in [("25:00", "26:00"), ("10:00", "09:00")]:
            with self.assertRaises(s.ScheduleError):
                s.interval({"days": ["M"], "start": start, "end": end})

    def test_dated_sections_do_not_overlap_across_parts_of_term(self):
        self.data["sections"][0]["meetings"][0].update(
            start_date="2031-01-01", end_date="2031-01-31"
        )
        self.data["sections"][2]["meetings"][0].update(
            start="08:00", end="09:00", start_date="2031-02-01", end_date="2031-03-01"
        )
        self.assertEqual(self.run_case()["distinct_found"], 2)

    def test_portable_cli_outside_workspace(self):
        script = self.root / "portable" / "scheduling.py"
        script.parent.mkdir()
        shutil.copyfile(Path(s.__file__), script)
        snapshot = self.root / "snapshot.json"
        snapshot.write_text(json.dumps(self.data))
        req = self.root / "request.json"
        req.write_text(json.dumps(request()))

        def cli(*args):
            result = subprocess.run(
                [
                    sys.executable,
                    str(script),
                    "--workspace",
                    str(self.root / "student"),
                    *args,
                ],
                cwd=self.root,
                text=True,
                capture_output=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            return json.loads(result.stdout)

        cli("init")
        cli("import", str(snapshot))
        result = cli("solve", str(req))
        self.assertEqual(
            cli("export", result["scenarios"][0]["plans"][0]["id"])["units"], 9
        )

    def test_backup_scenario_with_no_sections_reports_shortage(self):
        self.data["courses"].append(
            {"id": "HIST", "title": "History seminar", "units": 4}
        )
        req = request()
        req["scenarios"].append(
            {
                "id": "backup",
                "course_ids": ["HIST", "STAT"],
                "rationale": "ART unavailable",
            }
        )
        s.import_snapshot(self.db, self.data)
        result = s.solve(self.db, req)
        self.assertEqual(result["scenarios"][0]["distinct_found"], 2)
        backup = result["scenarios"][1]
        self.assertTrue(backup["exhaustive"])
        self.assertEqual((backup["combinations"], backup["shortage"]), (0, 3))

    def test_ineligible_courses_never_certified(self):
        req = request()
        req["eligibility"]["STAT"] = "ineligible"
        self.assertEqual(self.run_case(req)["rejected"], {"eligibility": 2})

    def test_date_bounds_without_common_meeting_day(self):
        a = {
            "days": ["M"],
            "start": "08:00",
            "end": "09:00",
            "start_date": "2031-01-06",
            "end_date": "2031-01-07",
        }
        b = dict(a, start_date="2031-01-07", end_date="2031-01-08")
        self.assertFalse(s.overlap(a, b))

    def test_second_student_science_courses_and_friday_preference(self):
        for course, cid in zip(self.data["courses"], ["CHEM", "BIO"]):
            old = course["id"]
            course.update(id=cid, title=f"Synthetic {cid}")
            for section in self.data["sections"]:
                if section["course_id"] == old:
                    section["course_id"] = cid
            for bundle in self.data["bundles"]:
                if bundle["course_id"] == old:
                    bundle["course_id"] = cid
        self.data["sections"][1]["meetings"][0]["days"] = ["F"]
        req = request()
        req.update(
            scenarios=[{"id": "science", "course_ids": ["CHEM", "BIO"]}],
            eligibility={"CHEM": "eligible", "BIO": "eligible"},
            preferences=[{"kind": "day", "day": "F"}],
        )
        self.assertEqual(self.run_case(req)["plans"][0]["section_ids"], ["A8", "S9"])

    def test_travel_ignores_noncoincident_dated_meetings(self):
        self.data["sections"][0]["meetings"] = [
            {
                "days": ["M"],
                "start": "08:00",
                "end": "09:00",
                "start_date": "2031-01-06",
                "end_date": "2031-01-07",
            }
        ]
        self.data["sections"][2]["meetings"] = [
            {
                "days": ["M"],
                "start": "09:00",
                "end": "10:00",
                "start_date": "2031-01-07",
                "end_date": "2031-01-08",
            }
        ]
        self.data["sections"][2]["location"] = "Campus B"
        req = request()
        req["travel"] = [
            {"from": "Campus A", "to": "Campus B", "minutes": 20, "verified": True}
        ]
        self.assertEqual(self.run_case(req)["distinct_found"], 2)

    def test_equivalence_group_label_does_not_collide_with_course_id(self):
        self.data["courses"][0]["equivalence_group"] = "STAT"
        self.assertEqual(self.run_case()["distinct_found"], 2)

    def test_date_strings_require_documented_calendar_format(self):
        for value in ("20301101", "2030-W44-5"):
            with self.subTest(value=value):
                data = copy.deepcopy(self.data)
                data["observed_at"] = value
                with self.assertRaises(s.ScheduleError):
                    s.validate_snapshot(data)

    def test_exact_preference_boundaries(self):
        req = request()
        req["preferences"] = [
            {"kind": "before", "time": "08:00"},
            {"kind": "after", "time": "13:00"},
        ]
        self.assertEqual(
            [p["score"] for p in self.run_case(req)["plans"]], [[0, 0], [0, 0]]
        )

    def test_all_cli_operations_and_errors(self):
        script = Path(s.__file__).resolve()
        database = self.root / "student with spaces.sqlite"

        def cli(*args, error=False, env=None):
            result = subprocess.run(
                [sys.executable, str(script), "--database", str(database), *args],
                cwd=self.root,
                text=True,
                encoding="utf-8",
                capture_output=True,
                env=env,
            )
            self.assertEqual(result.returncode, 1 if error else 0, result.stderr)
            if error:
                self.assertNotIn("Traceback", result.stderr)
            return json.loads(result.stderr if error else result.stdout)

        def payload(name, data):
            path = self.root / name
            path.write_text(json.dumps(data), encoding="utf-8")
            return str(path)

        cli("inspect", error=True)
        cli("init")
        cli("init")
        self.assertTrue(cli("import", payload("offerings.json", self.data))["imported"])
        self.assertFalse(cli("import", str(self.root / "offerings.json"))["imported"])
        run = cli("solve", payload("request.json", request()))
        plan = run["scenarios"][0]["plans"][0]
        self.assertEqual(cli("inspect", "--run", run["run_id"]), run)
        self.assertEqual(
            cli("inspect", "--snapshot", "synthetic-1", "--course", "ART")["courses"][
                0
            ]["id"],
            "ART",
        )
        self.assertEqual(cli("export", plan["id"]), plan)
        obs = {
            "plan_id": plan["id"],
            "plan_name": "Synthetic",
            "term": plan["term"],
            "observed_at": "2030-11-02",
            "reloaded": True,
            "section_ids": plan["section_ids"],
            "units": plan["units"],
        }
        self.assertTrue(cli("receipt", payload("observation.json", obs))["verified"])
        self.assertTrue(cli("inspect", "--plan", plan["id"])["receipts"][0]["verified"])
        cli("backup", str(self.root / "copy.sqlite"))
        cli("backup", str(self.root / "copy.sqlite"), error=True)
        cli("backup", str(database), error=True)
        cli("export", "nonexistent", error=True)
        cli("inspect", "--course", "ART", error=True)
        cli(
            "inspect",
            "--snapshot",
            "synthetic-1",
            "--course",
            "nonexistent",
            error=True,
        )
        cli("import", payload("bad.json", {"unknown": True}), error=True)
        with closing(sqlite3.connect(database)) as db:
            self.assertEqual(db.execute("PRAGMA integrity_check").fetchone()[0], "ok")
            self.assertEqual(db.execute("PRAGMA foreign_key_check").fetchall(), [])

    def test_unicode_cli_under_non_unicode_console(self):
        s.import_snapshot(self.db, self.data)
        s.solve(self.db, request())
        # Re-import a snapshot containing a name not representable by a legacy Windows console.
        data = copy.deepcopy(self.data)
        data["id"] = "unicode"
        data["courses"][0]["title"] = "Mathematics \u03c0"
        s.import_snapshot(self.db, data)
        env = dict(os.environ, PYTHONIOENCODING="ascii")
        result = subprocess.run(
            [
                sys.executable,
                str(Path(s.__file__)),
                "--database",
                str(self.root / "schedules.sqlite"),
                "inspect",
                "--snapshot",
                "unicode",
            ],
            capture_output=True,
            env=env,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            json.loads(result.stdout)["courses"][0]["title"],
            data["courses"][0]["title"],
        )

    def test_random_schedules_against_independent_exhaustive_oracle(self):
        rng = random.Random(1287)
        for trial in range(60):
            data = sample()
            data["id"] = f"oracle-{trial}"
            data["courses"] = [
                {"id": f"C{i}", "title": f"Course {i}", "units": i + 2}
                for i in range(3)
            ]
            data["sections"] = []
            data["bundles"] = []
            times = {}
            for i in range(3):
                for j in range(3):
                    sid = f"{i}-{j}"
                    start = rng.randrange(8, 18) * 60
                    day = rng.choice(["M", "Tu", "F"])
                    duration = rng.choice([30, 60, 90])
                    times[sid] = (day, start, start + duration)
                    fmt = lambda minutes: f"{minutes // 60:02}:{minutes % 60:02}"
                    data["sections"].append(
                        {
                            "id": sid,
                            "course_id": f"C{i}",
                            "component": "lecture",
                            "label": sid,
                            "availability": "open",
                            "meeting_status": "scheduled",
                            "location": "A",
                            "meetings": [
                                {
                                    "days": [day],
                                    "start": fmt(start),
                                    "end": fmt(start + duration),
                                }
                            ],
                            "exams": [],
                        }
                    )
                    data["bundles"].append(
                        {"id": sid, "course_id": f"C{i}", "section_ids": [sid]}
                    )
            req = {
                "version": 1,
                "snapshot_id": data["id"],
                "scenarios": [{"id": "mix", "course_ids": ["C0", "C1", "C2"]}],
                "eligibility": {f"C{i}": "eligible" for i in range(3)},
                "count": 100,
                "preferences": [
                    {"kind": "before", "time": "10:00"},
                    {"kind": "day", "day": "F"},
                ],
            }
            expected = []
            for ids in itertools.product(
                *[[f"{i}-{j}" for j in range(3)] for i in range(3)]
            ):
                rows = [times[sid] for sid in ids]
                if any(
                    a[0] == b[0] and max(a[1], b[1]) < min(a[2], b[2])
                    for a, b in itertools.combinations(rows, 2)
                ):
                    continue
                score = [sum(r[1] < 600 for r in rows), sum(r[0] == "F" for r in rows)]
                expected.append((score, list(ids)))
            expected.sort()
            s.import_snapshot(self.db, data)
            actual = s.solve(self.db, req)["scenarios"][0]
            self.assertTrue(actual["exhaustive"])
            self.assertEqual(
                [(p["score"], p["section_ids"]) for p in actual["plans"]], expected
            )


if __name__ == "__main__":
    unittest.main(verbosity=2)
