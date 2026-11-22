"""Starter academic records and the synthetic demonstration workspace."""

from __future__ import annotations

from pathlib import Path

import yaml
from student_workspace.workspace import initialize_workspace

from .core import (
    PlanningError,
    Workspace,
    atomic_write,
    import_source,
    json_bytes,
    now,
    object_file,
    read_manifest,
    within,
)


def initialize(root, with_abroad=False):
    root = Path(root).resolve()
    # Future versions must be migrated explicitly before adding anything.
    for name in ("academic.yaml", "abroad.yaml"):
        path = within(root, "knowledge/academics/" + name)
        if path.exists() and object_file(path, True).get("schema_version") != 1:
            raise PlanningError(
                "Unsupported existing academic version; initialization left records unchanged"
            )
    config_path = within(root, "knowledge/academics/planning-config.json")
    if config_path.exists() and object_file(config_path).get("schema_version") != 1:
        raise PlanningError(
            "Unsupported existing configuration version; initialization left records unchanged"
        )
    read_manifest(root)
    academic = {
        "schema_version": 1,
        "updated": now()[:10],
        "profile": {},
        "source_keys": {},
        "requirements": [],
        "credits": [],
        "assignments": [],
        "planning_targets": [],
        "current_coursework": [],
        "record_coverage": {
            "credits": {"status": "unknown"},
            "current_coursework": {"status": "unknown"},
        },
        "open_questions": [],
    }
    abroad = {
        "schema_version": 1,
        "updated": now()[:10],
        "term": None,
        "route": None,
        "destination_preference": [],
        "research_sources": [],
        "historical_candidates": [],
        "approved_courses": [],
        "questions": [],
    }
    records = {
        "knowledge/academics/academic.yaml": yaml.safe_dump(
            academic, sort_keys=False
        ).encode(),
        "knowledge/academics/planning-config.json": json_bytes(
            {
                "schema_version": 1,
                "unit_label": "quarter units",
                "period_order": ["Winter", "Spring", "Summer", "Fall"],
            }
        ),
        "knowledge/goals/academic-career.md": b"# Academic and career goals\n\nNo preferences supplied. Record user decisions and their sources here.\n",
        "knowledge/academics/README.md": b"# Academic records\n\nBegin with INTAKE.md and review extracted facts with the student before adopting them. Edit academic.yaml for requirements, awarded credit and assignments. abroad.yaml is optional; initialize with --with-abroad only when requested. Keep goals in ../goals/academic-career.md. Generated files live in ../../artifacts/academic-planning/.\n",
    }
    if with_abroad:
        records["knowledge/academics/abroad.yaml"] = yaml.safe_dump(
            abroad, sort_keys=False
        ).encode()
    records["knowledge/academics/INTAKE.md"] = (
        Path(__file__).parent / "assets/intake.md"
    ).read_bytes()
    created = []
    # Exclusive creation never overwrites a file created concurrently.
    for relative, content in records.items():
        path = within(root, relative)
        if not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            try:
                with path.open("xb") as stream:
                    stream.write(content)
                created.append(relative)
            except FileExistsError:
                pass
    return {"created": created, "personal_records_overwritten": False}


def demo(root):
    root = Path(root).resolve()
    if root.exists() and any(root.iterdir()):
        raise PlanningError("Demo requires a new or completely empty directory")
    root.mkdir(parents=True, exist_ok=True)
    initialize_workspace(root)
    initialize(root)
    original = root / "sources/synthetic-audit.md"
    atomic_write(
        original,
        b"# Synthetic academic evidence\n\nFictional test data only.\n\n## baseline\nTransfer award: 9 units. AP award: 4 units. Current course: 4 units.\nThe selected term course has a checked offering. No host credit approvals exist.\n",
    )
    ref = import_source(root, original)["stored_path"] + "#baseline"
    academic = {
        "schema_version": 1,
        "updated": "2031-10-01",
        "profile": {
            "name": "Example student",
            "institution": "Example University",
            "major": "Example Engineering",
            "current_gpa": None,
        },
        "source_keys": {"audit": ref},
        "credit_controls": {
            "as_of": "2031-09-01",
            "transfer_units": 9,
            "ap_units": 4,
            "total_units": 13,
            "source_refs": [ref],
        },
        "requirements": [
            {
                "id": "req-foundation",
                "requirement": "Mathematical foundation",
                "units": 4,
                "status": "satisfied",
                "selected_course": "EXAMPLE MATH",
                "prerequisites": None,
                "notes": "Recognized requirement; earned units are recorded separately.",
                "source_refs": [ref],
            },
            {
                "id": "req-design",
                "requirement": "Engineering design",
                "units": 4,
                "status": "in-progress",
                "selected_course": "EXAMPLE DESIGN",
                "prerequisites": "Foundation",
                "notes": "Current enrollment remains in progress.",
                "source_refs": [ref],
            },
            {
                "id": "req-lab",
                "requirement": "Engineering laboratory",
                "units": 2,
                "status": "remaining",
                "selected_course": None,
                "prerequisites": "Design",
                "notes": "Proposed for the next term.",
                "source_refs": [ref],
            },
        ],
        "credits": [
            {
                "id": "credit-math",
                "institution": "Example College",
                "course": "EXAMPLE MATH",
                "term": "Spring 2031",
                "kind": "transfer",
                "awarded_units": 9,
                "recognition": "Mathematical foundation",
                "evidence_date": "2031-09-01",
                "source_refs": [ref],
            },
            {
                "id": "credit-ap",
                "institution": "Example exam board",
                "course": "EXAMPLE AP",
                "term": "Spring 2031",
                "kind": "ap",
                "awarded_units": 4,
                "recognition": "Units only; no laboratory credit",
                "evidence_date": "2031-09-01",
                "source_refs": [ref],
            },
            {
                "id": "credit-duplicate",
                "institution": "Example exam board",
                "course": "EXAMPLE DUPLICATE",
                "term": "Spring 2031",
                "kind": "ap",
                "awarded_units": 0,
                "recognition": "Duplicate award retained with zero units",
                "evidence_date": "2031-09-01",
                "source_refs": [ref],
            },
        ],
        "assignments": [
            {
                "requirement_id": "req-design",
                "course": "EXAMPLE DESIGN",
                "term": "Fall 2031",
                "units": 4,
                "status": "enrolled",
                "decision_source": ref,
            }
        ],
        "current_coursework": [
            {
                "course": "EXAMPLE DESIGN",
                "units": 4,
                "status": "in-progress",
                "source_refs": [ref],
            }
        ],
        "audit_snapshot": {
            "as_of": "2031-10-01",
            "earned_units": 13,
            "in_progress_units": 4,
            "minimum_degree_units": 120,
            "remaining_earned_units_to_minimum": 107,
            "remaining_units_if_in_progress_completed": 103,
            "source_refs": [ref],
        },
        "planning_targets": [
            {
                "course": "EXAMPLE LAB",
                "target_term": "Winter 2032",
                "commitment": "Desired completion; not enrollment",
                "source_refs": [ref],
            }
        ],
        "term_proposal": {
            "term": "Winter 2032",
            "status": "proposed",
            "courses": [
                {
                    "course": "EXAMPLE LAB",
                    "units": 2,
                    "basis": "Synthetic offering check; user has not selected a plan",
                }
            ],
            "availability_check": {
                "term": "Winter 2032",
                "available_courses": ["EXAMPLE LAB"],
                "source_refs": [ref],
            },
        },
        "open_questions": [
            "Confirm the actual schedule and student preferences before assigning future courses."
        ],
    }
    abroad = {
        "schema_version": 1,
        "updated": "2031-10-01",
        "term": "Fall 2032",
        "route": "Example exchange",
        "destination_preference": ["Example Host A", "Example Host B"],
        "preference_source": ref,
        "research_as_of": "2031-10-01",
        "current_verification": "Synthetic rules; not real program guidance",
        "research_sources": [ref],
        "destinations": [
            {
                "code": "EXA",
                "label": "Example Host A",
                "eligibility": "Example eligibility remains subject to official verification.",
                "access": "Faculty share, prerequisites and individual seat access are separate checks.",
            },
            {
                "code": "EXB",
                "label": "Example Host B",
                "eligibility": "Example program eligibility unresolved.",
                "access": "A host course is not automatically approved for home-university requirements.",
            },
        ],
        "ge_plan": {
            "summary": "Reserve an unmet general requirement only after degree-use approval."
        },
        "historical_candidates": [
            {
                "course": "EXAMPLE HOST COURSE",
                "ucla_credit": "unapproved",
                "source_refs": [ref],
            }
        ],
        "approved_courses": [],
        "questions": [
            "Which host courses are available in the intended semester?",
            "Which courses have written approval for remaining requirements?",
        ],
    }
    atomic_write(
        root / "knowledge/academics/academic.yaml",
        yaml.safe_dump(academic, sort_keys=False).encode(),
    )
    atomic_write(
        root / "knowledge/academics/abroad.yaml",
        yaml.safe_dump(abroad, sort_keys=False).encode(),
    )
    atomic_write(
        root / "knowledge/goals/academic-career.md",
        b"# Academic and career goals\n\n## Workload preference\n\nSynthetic preference: balance laboratory work with project time. No accelerated graduation date is selected.\n",
    )
    result = Workspace(root).build()
    return {"synthetic": True, "workspace": str(root), **result}
