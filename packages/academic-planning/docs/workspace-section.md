## Academic planning

Academic records live in `knowledge/academics/` and goals in
`knowledge/goals/academic-career.md`; original evidence stays in `sources/`.
Generated views go to `artifacts/academic-planning/`. Run the tool from
`tools/.venv`:

```text
academic-planning --workspace . context --focus overview
academic-planning --workspace . check
academic-planning --workspace . build
academic-planning --workspace . import-source FILE
python -m academic_planning.scheduling --workspace . inspect
```

For a new student, follow `knowledge/academics/INTAKE.md`: preserve the audit
(DARS) and goals, prepare a sourced extraction, review it with the student, then
adopt the facts. Use the plan-academics skill for audits and decisions,
plan-course-schedules for section alternatives, ucla-class-planner for requested
saved plans, and audit-academic-planning only when the user asks for an audit.
A saved plan does not enroll courses. Current support is UCLA undergraduate study.

`academic.yaml` holds requirements, awards, credit recognition and selected
assignments; goals hold constraints and preferences; `schedules.sqlite` holds
offering observations and schedule alternatives. Research current rules and
sections before relying on them. Proposals, selected plans, enrollment,
completion and approved credit stay distinct. Academic updates do not change
opportunity filters, board decisions or application claims.

`check` exits 0 for current or never-built outputs, 2 for stale outputs and 1
for errors. Rebuild stale outputs after reconciling records. Independently
edited outputs stop replacement; reconcile those edits into the records first.
Previous outputs stay in `artifacts/academic-planning/history/`.
`academic-planning --workspace . init --with-abroad` adds optional study-abroad
records. For a consistent copy of the schedule database while it is in use, run
`python -m academic_planning.scheduling --workspace . backup NEW_PATH`;
`student-workspace backup` also copies it safely.
