"""Shared records, provenance and protected artifact generation."""

from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import tempfile

import yaml
from student_workspace.sources import import_source as shared_import_source
from student_workspace.sources import read_source_manifest
from student_workspace.state import STATE_DIR, WorkspaceStateError

from . import __version__


class PlanningError(ValueError):
    """A user-actionable record, provenance or file conflict."""


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def now():
    return datetime.now(timezone.utc).isoformat()


def json_bytes(value):
    return (
        json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n"
    ).encode("utf-8")


def atomic_write(path, content):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".academic-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(content)
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


def within(root, relative, allowed=None):
    """Resolve a relative path, including symlinks, before any access."""
    root = Path(root).resolve()
    value = str(relative)
    if "\\" in value or re.match(r"^[A-Za-z]:", value):
        raise PlanningError(f"Use a workspace-relative forward-slash path: {value}")
    parts = Path(value).parts
    if (
        not parts
        or Path(value).is_absolute()
        or any(p in {"..", "."} for p in value.split("/"))
    ):
        raise PlanningError(f"Unsafe relative path: {value}")
    if allowed and parts[0] not in allowed:
        raise PlanningError(f"Path must start with one of {sorted(allowed)}: {value}")
    path = (root / value).resolve()
    if path == root or not path.is_relative_to(root):
        raise PlanningError(f"Path escapes workspace: {value}")
    return path


def object_file(path, yaml_file=False):
    value = (
        yaml.safe_load(Path(path).read_text(encoding="utf-8-sig"))
        if yaml_file
        else json.loads(Path(path).read_text(encoding="utf-8-sig"))
    )
    if not isinstance(value, dict):
        raise PlanningError(f"Expected a mapping in {Path(path).name}")
    return value


def units(value, label, positive=False):
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(value)
        or value < 0
        or (positive and value == 0)
    ):
        raise PlanningError(
            f"{label} needs finite {'positive' if positive else 'nonnegative'} units"
        )
    return value


def close(actual, expected, label):
    units(expected, label)
    if abs(actual - expected) > 1e-8:
        raise PlanningError(
            f"{label} does not reconcile: calculated {actual}, recorded {expected}"
        )


def source_refs(value):
    if isinstance(value, dict):
        for key, child in value.items():
            if key in {"source_refs", "research_sources"}:
                if not isinstance(child, list):
                    raise PlanningError(f"{key} must be a list")
                yield from child
            elif key == "source_keys":
                if not isinstance(child, dict):
                    raise PlanningError("source_keys must be a mapping")
                yield from child.values()
            elif key in {
                "decision_source",
                "approval_source",
                "preference_source",
                "declaration_source",
                "dars_source",
            }:
                if child:
                    yield child
            else:
                yield from source_refs(child)
    elif isinstance(value, list):
        for child in value:
            yield from source_refs(child)


def read_manifest(root):
    """The shared student-workspace source registry."""
    try:
        return read_source_manifest(Path(root))
    except WorkspaceStateError as exc:
        raise PlanningError(f"{exc}; run student-workspace init first") from exc


class Workspace:
    def __init__(self, root):
        self.root = Path(root).resolve()
        self.output = within(self.root, "artifacts/academic-planning")
        self.config_path = within(self.root, "knowledge/academics/planning-config.json")
        self._load_config()
        self.names = [
            "Academic-Planner.xlsx",
            "Academic-Advising.pdf",
            "Abroad-Brief.pdf",
            "Current-Academic-Record.md",
        ]
        self.state_path = within(
            self.root, "artifacts/academic-planning/build-manifest.json"
        )

    def _load_config(self):
        self.config_path = within(self.root, "knowledge/academics/planning-config.json")
        raw = self.config_path.read_bytes() if self.config_path.exists() else None
        config = json.loads(raw.decode("utf-8-sig")) if raw is not None else {}
        if not isinstance(config, dict):
            raise PlanningError("Planning configuration must be a mapping")
        version = config.get("schema_version", 1)
        if type(version) is not int or version != 1:
            raise PlanningError(
                "Unsupported planning configuration version; no automatic conversion is implemented"
            )
        label = config.get("unit_label", "quarter units")
        if not isinstance(label, str) or not label.strip():
            raise PlanningError("unit_label must be a nonempty string")
        periods = config.get("period_order", ["Winter", "Spring", "Summer", "Fall"])
        if (
            not isinstance(periods, list)
            or not periods
            or any(not isinstance(p, str) or not p.isalpha() for p in periods)
            or len(set(periods)) != len(periods)
        ):
            raise PlanningError(
                "period_order must contain unique alphabetic period names"
            )
        self.config, self.unit_label, self.periods = config, label, periods
        self._config_hash = hashlib.sha256(raw).hexdigest() if raw is not None else None

    def _check_config_snapshot(self):
        current = within(self.root, "knowledge/academics/planning-config.json")
        hashed = digest(current) if current.exists() else None
        if hashed != self._config_hash:
            raise PlanningError(
                "Configuration changed while loading or rendering; retry from consistent inputs"
            )

    def term_key(self, term):
        match = re.fullmatch(r"([A-Za-z]+) (\d{4})", str(term))
        if not match or match[1] not in self.periods:
            raise PlanningError(
                f"Unsupported term {term!r}; use a configured period and four-digit year"
            )
        return int(match[2]), self.periods.index(match[1])

    def load(self):
        self._load_config()
        data = object_file(within(self.root, "knowledge/academics/academic.yaml"), True)
        abroad_path = within(self.root, "knowledge/academics/abroad.yaml")
        self.abroad_enabled = abroad_path.is_file()
        abroad = object_file(abroad_path, True) if self.abroad_enabled else {}
        if data.get("schema_version") != 1 or (
            self.abroad_enabled and abroad.get("schema_version") != 1
        ):
            raise PlanningError(
                "Unsupported academic data version; no automatic conversion is implemented"
            )
        self.names = [
            "Academic-Planner.xlsx",
            "Academic-Advising.pdf",
            "Current-Academic-Record.md",
        ]
        if self.abroad_enabled:
            self.names.insert(2, "Abroad-Brief.pdf")
        manifest = read_manifest(self.root)
        registered = {r["stored_path"]: r for r in manifest["imports"]}
        self.evidence = {}
        for ref in source_refs([data, abroad]):
            if not isinstance(ref, str):
                raise PlanningError("Evidence references must be strings")
            relative, _, anchor = ref.partition("#")
            path = within(self.root, relative, {"sources", "knowledge"})
            if not path.is_file():
                raise PlanningError(f"Missing evidence: {relative}")
            hashed = digest(path)
            if relative.startswith("sources/") and (
                relative not in registered or registered[relative]["sha256"] != hashed
            ):
                raise PlanningError(f"Unregistered or changed source: {relative}")
            if anchor and path.suffix.lower() == ".md":
                headings = re.findall(
                    r"^#+ (.+)$", path.read_text(encoding="utf-8-sig"), re.M
                )
                anchors = {
                    re.sub(r"[^\w -]", "", h.lower()).replace(" ", "-")
                    for h in headings
                }
                if anchor not in anchors:
                    raise PlanningError(f"Missing evidence anchor: {ref}")
            self.evidence[relative] = hashed
        inventory_path = within(
            self.root, "knowledge/academics/source-inventory.json"
        )
        if inventory_path.exists():
            inventory = object_file(inventory_path)
            if not isinstance(inventory.get("files"), list):
                raise PlanningError("Historical source inventory needs a files list")
            for row in inventory["files"]:
                if row.get("disposition") == "excluded":
                    continue
                relative = row["stored_path"]
                path = within(self.root, relative, {"sources"})
                if (
                    relative not in registered
                    or not path.is_file()
                    or digest(path) != row["sha256"]
                    or registered[relative]["sha256"] != row["sha256"]
                ):
                    raise PlanningError(
                        "Historical inventory source failed hash/registration check"
                    )
                self.evidence[relative] = row["sha256"]
        requirements = data.get("requirements", [])
        credits = data.get("credits", [])
        ids = set()
        for row in requirements:
            if row["id"] in ids or not row.get("source_refs"):
                raise PlanningError("Requirements need unique IDs and evidence")
            ids.add(row["id"])
            if row["status"] not in {
                "needs-update",
                "satisfied-historical",
                "satisfied",
                "remaining",
                "in-progress",
            }:
                raise PlanningError("Unknown requirement status")
            if row.get("units") is not None:
                units(row["units"], "Requirement")
            if row.get("planned_term") is not None:
                raise PlanningError("Term ownership belongs to assignments")
        credit_ids, credit_keys = set(), set()
        for row in credits:
            key = (row["institution"], row["course"], row["term"])
            if (
                key in credit_keys
                or row["id"] in credit_ids
                or not row.get("source_refs")
            ):
                raise PlanningError("Duplicate credit award or missing credit evidence")
            credit_ids.add(row["id"])
            credit_keys.add(key)
            if row["kind"] not in {"transfer", "ap", "ib", "ucla", "institution"}:
                raise PlanningError("Unknown credit kind")
            units(row["awarded_units"], "Awarded credit")
        earned = sum(r["awarded_units"] for r in credits)
        controls = data.get("credit_controls")
        if controls:
            historical = [r for r in credits if r["evidence_date"] == controls["as_of"]]
            for kind in ("transfer", "ap", "ib", "ucla", "institution"):
                if f"{kind}_units" in controls:
                    close(
                        sum(
                            r["awarded_units"] for r in historical if r["kind"] == kind
                        ),
                        controls[f"{kind}_units"],
                        f"Historical {kind} units",
                    )
            close(
                sum(r["awarded_units"] for r in historical),
                controls["total_units"],
                "Historical total",
            )
        assigned_reqs, assigned_courses = set(), set()
        for row in data.get("assignments", []):
            self.term_key(row["term"])
            if (
                row["requirement_id"] not in ids
                or row["requirement_id"] in assigned_reqs
                or row["course"] in assigned_courses
            ):
                raise PlanningError("Unknown or multiply assigned course/requirement")
            if row["status"] not in {"planned", "enrolled", "completed"} or not row.get(
                "decision_source"
            ):
                raise PlanningError(
                    "Assignments need a selected/enrolled/completed status and decision evidence; proposals remain separate"
                )
            units(row["units"], "Assignment", True)
            assigned_reqs.add(row["requirement_id"])
            assigned_courses.add(row["course"])
        in_progress = 0
        for row in data.get("current_coursework", []):
            if row.get("status") != "in-progress" or not row.get("source_refs"):
                raise PlanningError(
                    "Current coursework needs in-progress status and evidence"
                )
            in_progress += units(row["units"], "In-progress coursework", True)
        from .totals import summarize_units

        unit_summary = summarize_units(data, earned, in_progress)
        for row in data.get("planning_targets", []):
            self.term_key(row["target_term"])
            if not row.get("source_refs"):
                raise PlanningError("Completion target lacks evidence")
        proposal = data.get("term_proposal")
        if proposal:
            self.term_key(proposal["term"])
            availability = proposal.get("availability_check", {})
            if (
                proposal.get("status") != "proposed"
                or availability.get("term") != proposal["term"]
                or not availability.get("source_refs")
            ):
                raise PlanningError(
                    "Proposal needs its own term's offering and eligibility evidence"
                )
            seen = set()
            for row in proposal["courses"]:
                units(row["units"], "Proposal", True)
                if row["course"] in seen or row["course"] not in availability.get(
                    "available_courses", []
                ):
                    raise PlanningError(
                        "Duplicate proposal course or unchecked term availability"
                    )
                seen.add(row["course"])
            meetings = proposal.get("candidate_sections", [])
            for i, meeting in enumerate(meetings):
                if meeting["start"] >= meeting["end"]:
                    raise PlanningError("Invalid candidate meeting time")
                for other in meetings[i + 1 :]:
                    if (
                        set(meeting["days"]) & set(other["days"])
                        and meeting["start"] < other["end"]
                        and other["start"] < meeting["end"]
                    ):
                        raise PlanningError("Candidate meetings overlap")
        for row in abroad.get("approved_courses", []):
            if not row.get("approval_source"):
                raise PlanningError("Abroad approval lacks evidence")
        for row in abroad.get("historical_candidates", []):
            if row.get("ucla_credit", "unapproved") != "unapproved":
                raise PlanningError(
                    "Historical abroad candidates cannot establish approved credit"
                )
        from .planning import validate_planning_records

        validate_planning_records(data, abroad)
        self.goals_path = within(self.root, "knowledge/goals/academic-career.md")
        self.goals = self.goals_path.read_text(encoding="utf-8-sig")
        self.data, self.abroad = data, abroad
        self.summary = {
            "intake_populated": bool(
                requirements
                or credits
                or data.get("current_coursework")
                or data.get("audit_snapshot")
                or unit_summary["earned_units"] is not None
                or unit_summary["in_progress_units"] is not None
            ),
            **unit_summary,
            "requirements": len(requirements),
            "assignments": len(data.get("assignments", [])),
            "unit_label": self.unit_label,
        }
        self._check_config_snapshot()
        return data, abroad

    def inputs(self):
        self._check_config_snapshot()
        # Re-read evidence, not just the recorded digest, to detect mid-build edits.
        paths = [
            "knowledge/academics/academic.yaml",
            "knowledge/goals/academic-career.md",
            *self.evidence,
        ]
        if within(self.root, "knowledge/academics/source-inventory.json").exists():
            paths.append("knowledge/academics/source-inventory.json")
        if self.abroad_enabled:
            paths.append("knowledge/academics/abroad.yaml")
        if self.config_path.exists():
            paths.append("knowledge/academics/planning-config.json")
        result = {p: digest(within(self.root, p)) for p in paths}
        for p in sorted(Path(__file__).parent.glob("*.py")):
            result[f"generator/{p.name}"] = digest(p)
        return result

    def output_state(self):
        if not self.state_path.exists():
            if any((self.output / name).exists() for name in self.names):
                raise PlanningError(
                    "Existing artifacts lack this generator's manifest; preserve/reconcile them before building"
                )
            return None
        state = object_file(self.state_path)
        allowed = {
            "Academic-Planner.xlsx",
            "Academic-Advising.pdf",
            "Current-Academic-Record.md",
            "Abroad-Brief.pdf",
        }
        if (
            state.get("schema_version") != 1
            or not isinstance(state.get("outputs"), dict)
            or not (allowed - {"Abroad-Brief.pdf"}) <= set(state["outputs"]) <= allowed
        ):
            raise PlanningError(
                "Unsupported/incomplete build manifest; preserve outputs before rebuilding"
            )
        for name in set(self.names) - set(state["outputs"]):
            if (self.output / name).exists():
                raise PlanningError(
                    f"Unmanaged output would be replaced: {name}; preserve/reconcile first"
                )
        for name in state["outputs"]:
            path = within(self.root, f"artifacts/academic-planning/{name}")
            if path.exists() and digest(path) != state["outputs"][name]:
                raise PlanningError(
                    f"Output edited independently: {name}. Preserve and reconcile its changes first"
                )
        return state

    def check(self):
        self.load()
        state = self.output_state()
        stale = bool(
            state
            and (
                state["inputs"] != self.inputs()
                or set(state["outputs"]) != set(self.names)
                or any(not (self.output / n).exists() for n in self.names)
            )
        )
        return {
            "valid": True,
            **self.summary,
            "outputs_built": bool(state),
            "outputs_stale": stale,
        }

    def context(self, focus):
        self.load()
        result = {
            "saved_as_of": self.data.get("updated"),
            "fresh_research": False,
            **self.summary,
        }
        if focus in {"record", "overview"}:
            result.update(
                profile=self.data.get("profile", {}),
                audit_snapshot=self.data.get("audit_snapshot"),
                enrollment_appointments=self.data.get("enrollment_appointments"),
            )
        if focus in {"term", "winter", "overview"}:
            result.update(
                assignments=self.data.get("assignments", []),
                term_proposal=self.data.get("term_proposal"),
                planning_targets=self.data.get("planning_targets", []),
                enrollment_appointments=self.data.get("enrollment_appointments"),
            )
        if focus in {"abroad", "overview"}:
            result["abroad_enabled"] = self.abroad_enabled
            if self.abroad_enabled:
                result["abroad"] = self.abroad
        if focus in {"record", "abroad", "overview"}:
            from .planning import recognition_options, useful_requirements

            result["recognition_options"] = recognition_options(self.data)
            result["research_updates"] = self.data.get("research_updates", [])
            if self.abroad_enabled:
                result["useful_requirements"] = useful_requirements(
                    self.data, self.abroad
                )
        result["goals"] = self.goals
        result["notice"] = (
            "Saved evidence; proposals, decisions, enrollment, completion and approval remain distinct."
        )
        result["read_next"] = [
            "knowledge/academics/README.md",
            "knowledge/goals/academic-career.md",
        ]
        result["read_next"].append("knowledge/academics/academic.yaml")
        if self.abroad_enabled and focus in {"overview", "abroad"}:
            result["read_next"].append("knowledge/academics/abroad.yaml")
        proposal = self.data.get("term_proposal")
        if proposal and focus in {"overview", "term", "winter"}:
            relative = (
                "knowledge/academics/"
                + proposal["term"].upper().replace(" ", "-")
                + ".md"
            )
            if within(self.root, relative).is_file():
                result["read_next"].append(relative)
        return result

    def build(self):
        from .render import render_all

        self.load()
        before = self.inputs()
        # Bracket the consumed model with hashes, not a hash of a later edit.
        self.load()
        if self.inputs() != before:
            raise PlanningError(
                "Inputs changed while loading; retry from consistent records"
            )
        self.output.mkdir(parents=True, exist_ok=True)
        with exclusive(self.output / ".build.lock"):
            prior = self.output_state()
            stage = Path(tempfile.mkdtemp(prefix="build-", dir=self._work()))
            render_all(self, stage)
            self.output_state()
            if self.inputs() != before:
                raise PlanningError(
                    "Inputs changed during generation; staging retained; rebuild"
                )
            old_names = [
                name
                for name in list(
                    dict.fromkeys(
                        [
                            *self.names,
                            *(prior or {}).get("outputs", {}),
                            "build-manifest.json",
                        ]
                    )
                )
                if (self.output / name).exists()
            ]
            revision = self.output / "history" / stage.name
            if old_names:
                revision.mkdir(parents=True)
                for name in old_names:
                    shutil.copy2(self.output / name, revision / name)
            published = []
            try:
                for name in self.names:
                    os.replace(stage / name, self.output / name)
                    published.append(name)
                for name in set((prior or {}).get("outputs", {})) - set(self.names):
                    (self.output / name).unlink(missing_ok=True)
                    published.append(name)
                atomic_write(
                    self.state_path,
                    json_bytes(
                        {
                            "schema_version": 1,
                            "extension_version": __version__,
                            "built_at": now(),
                            "inputs": before,
                            "outputs": {n: digest(self.output / n) for n in self.names},
                        }
                    ),
                )
            except BaseException:
                for name in published + ["build-manifest.json"]:
                    if name in old_names:
                        atomic_write(self.output / name, (revision / name).read_bytes())
                    else:
                        (self.output / name).unlink(missing_ok=True)
                raise
        return {"built": self.names, "output_directory": str(self.output)}

    def _work(self):
        work = within(self.root, f"{STATE_DIR}/academic-planning/work")
        work.mkdir(parents=True, exist_ok=True)
        return work


@contextmanager
def exclusive(path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL)
    except FileExistsError as exc:
        raise PlanningError(
            f"Operation locked: {path.name}; inspect the running operation before removing a stale lock"
        ) from exc
    try:
        with os.fdopen(fd, "w") as stream:
            stream.write(str(os.getpid()))
        yield
    finally:
        path.unlink(missing_ok=True)


def import_source(root, filename):
    """Preserve a file unchanged in sources/academic-planning/ and register it."""
    try:
        return shared_import_source(
            Path(root), Path(filename), folder="academic-planning", custom={"tool": "academic-planning"}
        )
    except WorkspaceStateError as exc:
        raise PlanningError(str(exc)) from exc
