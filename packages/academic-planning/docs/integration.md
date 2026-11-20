# Workspace integration and ownership

Academic Planning is a Student Workspace tool. `student-workspace-tool.json`
declares what it owns: `knowledge/academics/`, `artifacts/academic-planning/`
and `.student-workspace/academic-planning/`, plus the SQLite database
`knowledge/academics/schedules.sqlite`. Setup runs `academic-planning init`,
which creates blank records, goals and intake guidance and never overwrites
existing records. `academic-planning check` is the tool's part of
`student-workspace check` (0 current, 2 stale outputs, 1 error).

Original evidence is registered in the shared Student Workspace source registry
(`.student-workspace/source-manifest.json`); `import-source` preserves bytes and
reuses already registered content. Source references resolve inside `sources/`
or `knowledge/`.

Student YAML owns degree requirements, existing awards, recognition and selected
assignments. Shared goals own preferences. Optional `abroad.yaml` owns abroad
research and approvals. Scheduling SQLite owns offering snapshots, requests,
alternatives and planner receipts; JSON is interchange data. No component infers
enrollment from a draft or saved plan. A receipt compares agent-reported
independent observations; it does not authenticate the browser.

Builds validate sources and records, stage outputs, recheck input and output
hashes and keep previous versions in `artifacts/academic-planning/history/`.
An edited or unowned output is never silently replaced. Locks coordinate this
tool's own operations, not arbitrary external writers.
`student-workspace backup` copies the schedule database consistently.
