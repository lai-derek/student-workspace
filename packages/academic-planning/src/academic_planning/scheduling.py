"""Portable schedule storage and evaluation. Python standard library only.

Run with --help; the JSON contract is documented in skills/plan-course-schedules.
No academic approval or browser operation is inferred by this component.
"""

from __future__ import annotations

import argparse
from collections import Counter
from contextlib import closing
from datetime import date, timedelta
import hashlib
import itertools
import json
import math
from pathlib import Path
import re
import sqlite3
import sys

VERSION = 1
DAYS = {"M", "Tu", "W", "Th", "F", "Sa", "Su"}


class ScheduleError(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise ScheduleError(message)


def encoded(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False)


def identity(value):
    return hashlib.sha256(encoded(value).encode()).hexdigest()[:24]


def fields(value, required, optional=()):
    require(isinstance(value, dict), "Expected a JSON object")
    require(
        set(required) <= value.keys(),
        f"Missing fields: {sorted(set(required) - value.keys())}",
    )
    require(
        not (value.keys() - set(required) - set(optional)),
        f"Unknown fields: {sorted(value.keys() - set(required) - set(optional))}",
    )


def text(value):
    require(
        isinstance(value, str) and bool(value.strip()), "Expected a nonempty string"
    )


def number(value):
    require(
        type(value) in (int, float) and math.isfinite(value) and value >= 0,
        "Expected a finite nonnegative number",
    )


def unique(rows, key="id"):
    require(isinstance(rows, list), "Expected a list")
    ids = []
    for row in rows:
        text(row[key])
        ids.append(row[key])
    require(len(ids) == len(set(ids)), f"Duplicate {key}")


def clock(value):
    require(
        isinstance(value, str) and re.fullmatch(r"([01]\d|2[0-3]):[0-5]\d", value),
        f"Expected HH:MM, received {value!r}",
    )
    h, m = map(int, value.split(":"))
    return h * 60 + m


def calendar_date(value):
    require(
        isinstance(value, str) and re.fullmatch(r"\d{4}-\d{2}-\d{2}", value),
        f"Expected YYYY-MM-DD, received {value!r}",
    )
    return date.fromisoformat(value)


def interval(row, exam=False):
    fields(
        row,
        ("date", "start", "end") if exam else ("days", "start", "end"),
        () if exam else ("start_date", "end_date"),
    )
    require(
        clock(row["start"]) < clock(row["end"]), "Meeting/exam end must follow start"
    )
    if exam:
        calendar_date(row["date"])
    else:
        require(
            isinstance(row["days"], list)
            and bool(row["days"])
            and set(row["days"]) <= DAYS
            and len(row["days"]) == len(set(row["days"])),
            "Invalid meeting days",
        )
        require(
            ("start_date" in row) == ("end_date" in row),
            "Supply both meeting date bounds",
        )
        if "start_date" in row:
            require(
                calendar_date(row["start_date"]) <= calendar_date(row["end_date"]),
                "Reversed meeting date bounds",
            )


def coincident_days(a, b):
    days = set(a["days"]) & set(b["days"])
    low = calendar_date(
        max(a.get("start_date", "0001-01-01"), b.get("start_date", "0001-01-01"))
    )
    high = calendar_date(
        min(a.get("end_date", "9999-12-31"), b.get("end_date", "9999-12-31"))
    )
    weekdays = ["M", "Tu", "W", "Th", "F", "Sa", "Su"]
    return high >= low and any(
        weekdays[(low + timedelta(days=i)).weekday()] in days
        for i in range(min(7, (high - low).days + 1))
    )


def overlap(a, b, exam=False):
    if exam:
        common = a["date"] == b["date"]
    else:
        common = coincident_days(a, b)
    return (
        common
        and clock(a["start"]) < clock(b["end"])
        and clock(b["start"]) < clock(a["end"])
    )


DDL = """
CREATE TABLE snapshots(id TEXT PRIMARY KEY, institution TEXT NOT NULL, term TEXT NOT NULL,
 observed_at TEXT NOT NULL, payload TEXT NOT NULL);
CREATE TABLE courses(snapshot TEXT REFERENCES snapshots(id), id TEXT, payload TEXT NOT NULL,
 PRIMARY KEY(snapshot,id));
CREATE TABLE aliases(snapshot TEXT, course TEXT, alias TEXT,
 PRIMARY KEY(snapshot,course,alias), FOREIGN KEY(snapshot,course) REFERENCES courses(snapshot,id));
CREATE TABLE sections(snapshot TEXT, id TEXT, course TEXT, payload TEXT NOT NULL,
 PRIMARY KEY(snapshot,id), FOREIGN KEY(snapshot,course) REFERENCES courses(snapshot,id));
CREATE TABLE events(snapshot TEXT, section TEXT, kind TEXT CHECK(kind IN ('meeting','exam')),
 ordinal INTEGER, payload TEXT NOT NULL, PRIMARY KEY(snapshot,section,kind,ordinal),
 FOREIGN KEY(snapshot,section) REFERENCES sections(snapshot,id));
CREATE TABLE bundles(snapshot TEXT, id TEXT, course TEXT, payload TEXT NOT NULL,
 PRIMARY KEY(snapshot,id), FOREIGN KEY(snapshot,course) REFERENCES courses(snapshot,id));
CREATE TABLE bundle_sections(snapshot TEXT, bundle TEXT, section TEXT,
 PRIMARY KEY(snapshot,bundle,section),
 FOREIGN KEY(snapshot,bundle) REFERENCES bundles(snapshot,id),
 FOREIGN KEY(snapshot,section) REFERENCES sections(snapshot,id));
CREATE TABLE requests(id TEXT PRIMARY KEY, snapshot TEXT REFERENCES snapshots(id), payload TEXT NOT NULL);
CREATE TABLE runs(id TEXT PRIMARY KEY, request TEXT REFERENCES requests(id), payload TEXT NOT NULL);
CREATE TABLE plans(id TEXT PRIMARY KEY, run TEXT REFERENCES runs(id), payload TEXT NOT NULL);
CREATE TABLE receipts(id INTEGER PRIMARY KEY, plan TEXT REFERENCES plans(id), payload TEXT NOT NULL);
"""


def connect(path, initialize=False):
    path = Path(path)
    if initialize:
        path.parent.mkdir(parents=True, exist_ok=True)
    require(initialize or path.is_file(), "Database missing: run init first")
    db = sqlite3.connect(path)
    db.execute("PRAGMA foreign_keys=ON")
    version = db.execute("PRAGMA user_version").fetchone()[0]
    if version == 0 and initialize:
        try:
            db.executescript(
                "BEGIN;\n" + DDL + f"\nPRAGMA user_version={VERSION};\nCOMMIT;"
            )
        except Exception:
            db.close()
            raise
    elif version != VERSION:
        db.close()
        raise ScheduleError(f"Unsupported database version {version}")
    return db


def validate_snapshot(data):
    fields(
        data,
        (
            "version",
            "id",
            "institution",
            "term",
            "observed_at",
            "sources",
            "courses",
            "sections",
            "bundles",
        ),
    )
    require(data["version"] == VERSION, "Unsupported input version")
    for key in ("id", "institution", "term", "observed_at"):
        text(data[key])
    require(
        re.fullmatch(r"(Fall|Winter|Spring) 20\d\d", data["term"]),
        "Only Fall/Winter/Spring terms supported",
    )
    calendar_date(data["observed_at"])
    require(
        isinstance(data["sources"], list) and data["sources"],
        "Offering evidence is required",
    )
    for src in data["sources"]:
        fields(src, ("url",), ("evidence_ref",))
        text(src["url"])
        require(
            src["url"].startswith(("https://", "http://")),
            "Evidence URL must be HTTP(S)",
        )
        if "evidence_ref" in src:
            text(src["evidence_ref"])
    for key in ("courses", "sections", "bundles"):
        unique(data[key])
    courses = {x["id"]: x for x in data["courses"]}
    sections = {x["id"]: x for x in data["sections"]}
    for course in courses.values():
        fields(course, ("id", "title", "units"), ("aliases", "equivalence_group"))
        text(course["title"])
        number(course["units"])
        aliases = course.get("aliases", [])
        require(
            isinstance(aliases, list) and len(aliases) == len(set(aliases)),
            "Invalid aliases",
        )
        for alias in aliases:
            text(alias)
        if "equivalence_group" in course:
            text(course["equivalence_group"])
    for section in sections.values():
        fields(
            section,
            (
                "id",
                "course_id",
                "component",
                "label",
                "availability",
                "meeting_status",
                "meetings",
                "exams",
            ),
            ("instructor", "location", "notes"),
        )
        require(section["course_id"] in courses, "Section refers to an unknown course")
        require(
            section["availability"] in ("open", "closed", "unknown"),
            "Invalid availability",
        )
        require(
            section["meeting_status"] in ("scheduled", "none", "unknown"),
            "Invalid meeting status",
        )
        text(section["component"])
        text(section["label"])
        for key in ("instructor", "location", "notes"):
            require(
                section.get(key) is None or isinstance(section[key], str),
                f"{key} must be text or null",
            )
        require(isinstance(section["meetings"], list), "meetings must be a list")
        require(
            (section["meeting_status"] == "scheduled") == bool(section["meetings"]),
            "scheduled requires meetings; none/unknown requires an empty list",
        )
        for row in section["meetings"]:
            interval(row)
        require(
            section["exams"] is None or isinstance(section["exams"], list),
            "exams must be null or a list",
        )
        for row in section["exams"] or []:
            interval(row, exam=True)
    for bundle in data["bundles"]:
        fields(bundle, ("id", "course_id", "section_ids"))
        require(bundle["course_id"] in courses, "Bundle refers to unknown course")
        ids = bundle["section_ids"]
        require(
            isinstance(ids, list) and ids and len(ids) == len(set(ids)),
            "Invalid bundle sections",
        )
        require(
            all(
                x in sections and sections[x]["course_id"] == bundle["course_id"]
                for x in ids
            ),
            "Broken bundle link or component from a different enrollment course",
        )
    return data


def import_snapshot(db, data):
    validate_snapshot(data)
    payload = encoded(data)
    old = db.execute(
        "SELECT payload FROM snapshots WHERE id=?", (data["id"],)
    ).fetchone()
    if old:
        require(
            old[0] == payload,
            "Snapshot ID already exists with different data; use a new snapshot ID",
        )
        return {"snapshot_id": data["id"], "imported": False}
    sid = data["id"]
    with db:
        db.execute(
            "INSERT INTO snapshots VALUES(?,?,?,?,?)",
            (sid, data["institution"], data["term"], data["observed_at"], payload),
        )
        for course in data["courses"]:
            db.execute(
                "INSERT INTO courses VALUES(?,?,?)",
                (sid, course["id"], encoded(course)),
            )
            db.executemany(
                "INSERT INTO aliases VALUES(?,?,?)",
                [(sid, course["id"], a) for a in course.get("aliases", [])],
            )
        for section in data["sections"]:
            db.execute(
                "INSERT INTO sections VALUES(?,?,?,?)",
                (sid, section["id"], section["course_id"], encoded(section)),
            )
            for kind, rows in [
                ("meeting", section["meetings"]),
                ("exam", section["exams"] or []),
            ]:
                db.executemany(
                    "INSERT INTO events VALUES(?,?,?,?,?)",
                    [
                        (sid, section["id"], kind, i, encoded(r))
                        for i, r in enumerate(rows)
                    ],
                )
        for bundle in data["bundles"]:
            db.execute(
                "INSERT INTO bundles VALUES(?,?,?,?)",
                (sid, bundle["id"], bundle["course_id"], encoded(bundle)),
            )
            db.executemany(
                "INSERT INTO bundle_sections VALUES(?,?,?)",
                [(sid, bundle["id"], x) for x in bundle["section_ids"]],
            )
    return {"snapshot_id": sid, "imported": True}


def load(db, table, key):
    require(table in ("snapshots", "plans", "runs"), "Unsupported record type")
    row = db.execute(f"SELECT payload FROM {table} WHERE id=?", (key,)).fetchone()
    require(row is not None, f"Unknown {table} ID: {key}")
    return json.loads(row[0])


def validate_request(req, snapshot):
    fields(
        req,
        ("version", "snapshot_id", "scenarios"),
        (
            "preferences",
            "locked_sections",
            "excluded_sections",
            "blocks",
            "min_units",
            "max_units",
            "eligibility",
            "baseline_sections",
            "travel",
            "count",
            "search_limit",
        ),
    )
    require(
        req["version"] == VERSION and req["snapshot_id"] == snapshot["id"],
        "Invalid version or snapshot",
    )
    require(
        isinstance(req["scenarios"], list) and req["scenarios"],
        "At least one scenario required",
    )
    unique(req["scenarios"])
    courses = {x["id"] for x in snapshot["courses"]}
    sections = {x["id"] for x in snapshot["sections"]}
    for scenario in req["scenarios"]:
        fields(scenario, ("id", "course_ids"), ("rationale",))
        ids = scenario["course_ids"]
        require(
            isinstance(ids, list)
            and ids
            and len(ids) == len(set(ids))
            and set(ids) <= courses,
            "Scenario needs distinct known course IDs",
        )
    for key in ("locked_sections", "excluded_sections", "baseline_sections"):
        ids = req.get(key, [])
        require(
            isinstance(ids, list)
            and len(ids) == len(set(ids))
            and set(ids) <= sections,
            f"{key} must contain distinct section IDs in this snapshot",
        )
    for key in ("count", "search_limit"):
        require(
            type(req.get(key, 1)) is int and req.get(key, 1) > 0,
            f"{key} must be a positive integer",
        )
    for key in ("min_units", "max_units"):
        if key in req:
            number(req[key])
    require(
        req.get("min_units", 0) <= req.get("max_units", float("inf")),
        "Reversed unit limits",
    )
    for key in ("blocks", "preferences", "travel"):
        require(isinstance(req.get(key, []), list), f"{key} must be a list")
    require(
        isinstance(req.get("eligibility", {}), dict), "eligibility must be an object"
    )
    for row in req.get("blocks", []):
        interval(row)
    for course, state in req.get("eligibility", {}).items():
        require(
            course in courses and state in ("eligible", "ineligible", "unknown"),
            "Invalid eligibility finding",
        )
    for pref in req.get("preferences", []):
        fields(pref, ("kind",), ("time", "day"))
        require(
            pref["kind"] in ("before", "after", "day", "changes"),
            "Unknown preference kind",
        )
        if pref["kind"] in ("before", "after"):
            require(
                set(pref) == {"kind", "time"}, "Time preference requires only kind/time"
            )
            clock(pref["time"])
        elif pref["kind"] == "day":
            require(
                set(pref) == {"kind", "day"} and pref["day"] in DAYS,
                "Invalid day preference",
            )
        else:
            require(
                set(pref) == {"kind"} and "baseline_sections" in req,
                "changes requires baseline_sections",
            )
    pairs = set()
    for row in req.get("travel", []):
        fields(row, ("from", "to", "minutes", "verified"))
        text(row["from"])
        text(row["to"])
        number(row["minutes"])
        require(type(row["verified"]) is bool, "travel.verified must be boolean")
        pair = (row["from"], row["to"])
        require(pair not in pairs, "Duplicate directed travel allowance")
        pairs.add(pair)


def evaluate(snapshot, req, bundles):
    courses = {x["id"]: x for x in snapshot["courses"]}
    section_map = {x["id"]: x for x in snapshot["sections"]}
    selected = sorted({s for b in bundles for s in b["section_ids"]})
    if not set(req.get("locked_sections", [])) <= set(selected):
        return None, "locked_sections"
    if set(req.get("excluded_sections", [])) & set(selected):
        return None, "excluded_sections"
    groups = [
        ("group", courses[b["course_id"]]["equivalence_group"])
        if "equivalence_group" in courses[b["course_id"]]
        else ("course", b["course_id"])
        for b in bundles
    ]
    if len(groups) != len(set(groups)):
        return None, "duplicate_equivalent_course"
    units = sum(courses[b["course_id"]]["units"] for b in bundles)
    if not req.get("min_units", 0) <= units <= req.get("max_units", float("inf")):
        return None, "units"
    unresolved, meetings, exams = [], [], []
    for bundle in bundles:
        cid = bundle["course_id"]
        eligibility = req.get("eligibility", {}).get(cid, "unknown")
        if eligibility == "ineligible":
            return None, "eligibility"
        if eligibility == "unknown":
            unresolved.append(f"Eligibility unresolved: {cid}")
    for sid in selected:
        section = section_map[sid]
        if section["availability"] == "closed":
            return None, "closed_section"
        if section["availability"] == "unknown":
            unresolved.append(f"Availability unknown: {sid}")
        if section["meeting_status"] == "unknown":
            unresolved.append(f"Meetings unknown: {sid}")
        if section["exams"] is None:
            unresolved.append(f"Exams unknown: {sid}")
        if section["meetings"] and not section.get("location"):
            unresolved.append(f"Location unknown: {sid}")
        meetings.extend(
            (sid, row, section.get("location")) for row in section["meetings"]
        )
        exams.extend((sid, row) for row in section["exams"] or [])
    if any(overlap(m[1], block) for m in meetings for block in req.get("blocks", [])):
        return None, "unavailable_time"
    if any(overlap(a[1], b[1]) for a, b in itertools.combinations(meetings, 2)):
        return None, "meeting_conflict"
    if any(overlap(a[1], b[1], True) for a, b in itertools.combinations(exams, 2)):
        return None, "exam_conflict"
    allowances = {(r["from"], r["to"]): r for r in req.get("travel", [])}
    for a, b in itertools.permutations(meetings, 2):
        if not coincident_days(a[1], b[1]):
            continue
        gap = clock(b[1]["start"]) - clock(a[1]["end"])
        if not 0 <= gap < 60 or not a[2] or not b[2] or a[2] == b[2]:
            continue
        allowance = allowances.get((a[2], b[2]))
        if allowance is None or not allowance["verified"]:
            unresolved.append(f"Travel unverified: {a[0]} -> {b[0]} ({gap} minutes)")
        if allowance and allowance["verified"] and allowance["minutes"] > gap:
            return None, "travel_conflict"
    violations = []
    for pref in req.get("preferences", []):
        if pref["kind"] == "changes":
            value = len(set(selected) ^ set(req["baseline_sections"]))
        elif pref["kind"] == "day":
            value = sum(pref["day"] in m[1]["days"] for m in meetings)
        else:
            value = sum(
                len(m[1]["days"])
                for m in meetings
                if (
                    clock(m[1]["start"]) < clock(pref["time"])
                    if pref["kind"] == "before"
                    else clock(m[1]["end"]) > clock(pref["time"])
                )
            )
        violations.append({"preference": pref, "count": value})
    return {
        "bundle_ids": sorted(b["id"] for b in bundles),
        "section_ids": selected,
        "courses": [
            courses[b["course_id"]]
            for b in sorted(bundles, key=lambda b: b["course_id"])
        ],
        "sections": [section_map[s] for s in selected],
        "units": units,
        "score": [v["count"] for v in violations],
        "violations": violations,
        "unresolved": sorted(set(unresolved)),
        "verification": "conditional"
        if unresolved
        else "checked-against-supplied-snapshot",
    }, None


def solve(db, req):
    snapshot = load(db, "snapshots", req["snapshot_id"])
    validate_request(req, snapshot)
    rid = identity(req)
    result = {
        "version": VERSION,
        "run_id": rid,
        "snapshot_id": snapshot["id"],
        "term": snapshot["term"],
        "observed_at": snapshot["observed_at"],
        "sources": snapshot["sources"],
        "scenarios": [],
    }
    by_course = {}
    for bundle in snapshot["bundles"]:
        by_course.setdefault(bundle["course_id"], []).append(bundle)
    for scenario in req["scenarios"]:
        options = [
            sorted(by_course.get(cid, []), key=lambda b: b["id"])
            for cid in scenario["course_ids"]
        ]
        total = math.prod(map(len, options))
        limit = req.get("search_limit", 100000)
        valid, rejected, seen = [], Counter(), set()
        for combo in itertools.islice(itertools.product(*options), limit):
            plan, reason = evaluate(snapshot, req, combo)
            if reason:
                rejected[reason] += 1
            elif tuple(plan["section_ids"]) not in seen:
                seen.add(tuple(plan["section_ids"]))
                plan["id"] = identity([rid, scenario["id"], plan["section_ids"]])
                plan["scenario_id"] = scenario["id"]
                plan["snapshot_id"] = snapshot["id"]
                plan["term"] = snapshot["term"]
                valid.append(plan)
        valid.sort(key=lambda p: (p["score"], p["section_ids"]))
        count = req.get("count", 3)
        result["scenarios"].append(
            {
                "id": scenario["id"],
                "rationale": scenario.get("rationale"),
                "combinations": total,
                "examined": min(total, limit),
                "exhaustive": total <= limit,
                "rejected": dict(rejected),
                "distinct_found": len(valid),
                "shortage": max(0, count - len(valid)),
                "plans": valid[:count],
            }
        )
    with db:
        db.execute(
            "INSERT OR IGNORE INTO requests VALUES(?,?,?)",
            (rid, snapshot["id"], encoded(req)),
        )
        db.execute(
            "INSERT OR IGNORE INTO runs VALUES(?,?,?)", (rid, rid, encoded(result))
        )
        for scenario in result["scenarios"]:
            for plan in scenario["plans"]:
                db.execute(
                    "INSERT OR IGNORE INTO plans VALUES(?,?,?)",
                    (plan["id"], rid, encoded(plan)),
                )
    return result


def receipt(db, observation):
    fields(
        observation,
        (
            "plan_id",
            "plan_name",
            "term",
            "observed_at",
            "reloaded",
            "section_ids",
            "units",
        ),
        ("evidence_ref",),
    )
    plan = load(db, "plans", observation["plan_id"])
    text(observation["plan_name"])
    calendar_date(observation["observed_at"])
    require(type(observation["reloaded"]) is bool, "reloaded must be boolean")
    require(
        isinstance(observation["section_ids"], list)
        and all(isinstance(s, str) for s in observation["section_ids"]),
        "section_ids must be strings",
    )
    number(observation["units"])
    differences = []
    for key in ("term", "units"):
        if observation[key] != plan[key]:
            differences.append(f"{key} mismatch")
    if sorted(observation["section_ids"]) != plan["section_ids"]:
        differences.append("section_ids mismatch")
    if not observation["reloaded"]:
        differences.append("Plan was not reloaded")
    value = {
        "expected_plan_id": plan["id"],
        "observation": observation,
        "verified": not differences,
        "differences": differences,
        "status": "saved-plan-verified"
        if not differences
        else "verification-incomplete",
        "notice": "Agent-reported browser observation; does not establish enrollment.",
    }
    with db:
        cursor = db.execute(
            "INSERT INTO receipts(plan,payload) VALUES(?,?)",
            (plan["id"], encoded(value)),
        )
    return dict(value, receipt_id=cursor.lastrowid)


def backup(db, destination):
    destination = Path(destination)
    require(not destination.exists(), "Backup destination exists; choose a new path")
    destination.parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(destination)) as target:
        db.backup(target)
    return {"backup": str(destination)}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, default=Path.cwd())
    parser.add_argument("--database", type=Path)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("init")
    for name in ("import", "solve", "receipt"):
        sub.add_parser(name).add_argument("input", type=Path)
    inspect = sub.add_parser("inspect")
    target = inspect.add_mutually_exclusive_group()
    target.add_argument("--snapshot")
    target.add_argument("--run")
    target.add_argument("--plan")
    inspect.add_argument(
        "--course", help="Filter a snapshot by exact enrollment course ID"
    )
    sub.add_parser("export").add_argument("plan_id")
    sub.add_parser("backup").add_argument("destination", type=Path)
    args = parser.parse_args(argv)
    try:
        if args.command == "inspect":
            require(not args.course or args.snapshot, "--course requires --snapshot")
        path = args.database or args.workspace / "knowledge/academics/schedules.sqlite"
        with closing(connect(path, args.command == "init")) as db:
            if args.command == "init":
                output = {"database": str(path), "schema_version": VERSION}
            elif args.command in ("import", "solve", "receipt"):
                data = json.loads(args.input.read_text(encoding="utf-8-sig"))
                output = {
                    "import": import_snapshot,
                    "solve": solve,
                    "receipt": receipt,
                }[args.command](db, data)
            elif args.command == "export":
                output = load(db, "plans", args.plan_id)
            elif args.command == "backup":
                require(
                    path.resolve() != args.destination.resolve(),
                    "Backup must use a different path",
                )
                output = backup(db, args.destination)
            elif args.snapshot:
                output = load(db, "snapshots", args.snapshot)
                if args.course:
                    require(
                        any(c["id"] == args.course for c in output["courses"]),
                        "Unknown course ID in snapshot",
                    )
                    output = dict(
                        output,
                        **{
                            key: [
                                row
                                for row in output[key]
                                if row["id" if key == "courses" else "course_id"]
                                == args.course
                            ]
                            for key in ("courses", "sections", "bundles")
                        },
                    )
            elif args.run:
                output = load(db, "runs", args.run)
            elif args.plan:
                output = {
                    "plan": load(db, "plans", args.plan),
                    "receipts": [
                        dict(json.loads(row[1]), receipt_id=row[0])
                        for row in db.execute(
                            "SELECT id,payload FROM receipts WHERE plan=? ORDER BY id",
                            (args.plan,),
                        )
                    ],
                }
            else:
                require(not args.course, "--course requires --snapshot")
                output = {
                    t: db.execute(f"SELECT count(*) FROM {t}").fetchone()[0]
                    for t in (
                        "snapshots",
                        "courses",
                        "sections",
                        "bundles",
                        "requests",
                        "plans",
                        "receipts",
                    )
                }
                output["snapshot_index"] = [
                    dict(zip(("id", "institution", "term", "observed_at"), row))
                    for row in db.execute(
                        "SELECT id,institution,term,observed_at FROM snapshots ORDER BY observed_at,id"
                    )
                ]
                output["run_ids"] = [
                    row[0] for row in db.execute("SELECT id FROM runs ORDER BY id")
                ]
        # ASCII-escaped JSON remains lossless on legacy Windows console encodings.
        print(json.dumps(output, sort_keys=True, ensure_ascii=True, allow_nan=False))
        return 0
    except (
        ScheduleError,
        ValueError,
        TypeError,
        KeyError,
        OSError,
        sqlite3.Error,
    ) as exc:
        print(json.dumps({"error": str(exc), "command": args.command}), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
