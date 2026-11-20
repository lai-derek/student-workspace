---
name: plan-academics
description: Maintain sourced UCLA undergraduate academic records, credit recognition, course plans and optional study-abroad research. Use for academic intake, audits, advisor rulings and course tradeoffs; excludes coursework tutoring and application drafting.
---

# Plan academics

Follow the workspace instructions. Shared records own student facts and decisions; the academic-planning tool owns code and generated views. Academic planning does not require opportunity filters, an application profile or the discovery engine.

For a fresh student, follow `knowledge/academics/INTAKE.md`: preserve and register their latest DARS/audit, retrieve supplied goals and constraints, prepare a sourced extraction, show it to the student, and obtain review before adopting facts. There is no automatic DARS interpreter or official rule verifier. Empty records mean unfinished intake. Keep contradictions and unknowns visible. Use each student's institution, major and evidence; no personal term, destination or preference is a default. UCLA undergraduate study is the initial supported scope.

Use `academic-planning --workspace . context --focus overview`, `record`, `term` or `abroad` (from `tools/.venv`) for saved context; follow `read_next` selectively. Read goals before optimizing a plan. Tentative interests remain tentative. These summaries do not refresh offerings, seats or approvals.

For course mixes, section schedules, backups and repairs use [plan-course-schedules](../plan-course-schedules/SKILL.md). Compare complete alternatives over the affected horizon, including downstream offerings, displaced work, labs, workload and user timing goals. Use [verification and sequencing](references/verification.md) when needed. Capacity and prerequisite count alone do not rank urgency. Verify exact terms, requisites, restrictions, linked meetings and finals; label unpublished offerings as projections.

Scheduling SQLite owns offering observations, alternatives and save receipts. YAML owns degree requirements, credit and selected assignments. Use [ucla-class-planner](../ucla-class-planner/SKILL.md) for requested saved-plan changes only. A draft never authorizes browser writes. Independent reload/read-back observations must precede a verified receipt; tests never operate the real browser. Enrollment is outside the saved-plan workflow.

Keep earned awards, in-progress work, appointment eligibility and projected standing separate. Recorded-row subtotals are not established totals. Use sourced audit fields or dated record_coverage evidence for completeness in each domain independently; missing/partial evidence stays unknown, while explicitly evidenced zero remains numeric. Do not infer credit/enrollment completeness from requirement rows or nonempty lists. Recognition of an existing award does not award units again. Conditional recognition_options link existing credit IDs and requirement slots, track both course and unit minima, and keep approval, area selection, declaration and DARS posting distinct. Confirmed administrative states need separate evidence. See [record maintenance](references/verification.md#record-maintenance-and-recognition).

Preserve originals with import-source before updating facts. research_updates carry dated findings and source_refs; supersedes names only the replaced claim scope and prior evidence. A newer date does not establish broader authority. Keep unrelated findings even when they share a source.

Study abroad is optional. Initialize abroad records only when requested. Separate program eligibility, host classification and enrollment access, load, unit conversion and home-degree approval. A topic or breadth label does not establish equivalence. Investigate useful unmet requirement roles before adding redundant work. Host courses require their own approval evidence.

Update the owning records and relevant existing narrative/profile/catalog links without requiring new opportunity setup. Run check, build when consumed inputs change, inspect affected outputs, and check again. Run `student-workspace audit` after source registrations change. Reconcile independently edited outputs before replacing them. Commands and backup boundaries are in the tool's [workspace instructions](../../docs/workspace-section.md).
