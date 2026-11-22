---
name: plan-course-schedules
description: Research UCLA undergraduate course choices and generate ranked term schedules and backups using the academic scheduling module. Use for section planning, schedule repairs, and downstream course tradeoffs.
---

# Plan course schedules

Use student evidence and goals as inputs, not fixed personal defaults. The module supplies reliable storage and calculations; the agent supplies academic interpretation and recommendations. Initially cover UCLA undergraduate Fall/Winter/Spring. Identify other cases as outside verified coverage.

## Establish the request

Retrieve available coursework, requirements, decisions, preferences and future-term commitments before asking questions. In an integrated workspace, use its academic context command and follow relevant records selectively. Without one, accept supplied records or conversation; do not require the opportunity engine.

Distinguish course selection from section selection. Confirm only consequential unknowns: target term, needed courses, eligibility gaps, hard constraints versus ordered preferences, and what each backup assumes unavailable. Preserve tentative goals and existing authorization. No universal preference for mornings, gaps, Fridays, instructor ratings, full-time units or abroad GEs.

## Research and compute

Read the [scheduling interface](references/interface.md) when using the commands or preparing inputs. The implementation is [scheduling.py](../../src/academic_planning/scheduling.py), run as `python -m academic_planning.scheduling` from `tools/.venv`; all database/workspace paths are explicit or relative to the working directory.

- Verify the named term in UCLA's official Schedule of Classes, and check catalog/department rules and student records for requisites, restrictions and eligibility. Record allowed lecture/discussion/lab bundles explicitly, including closed and unknown sections. Verify finals and locations; never turn missing information into an empty/known value.
- Reuse researched snapshots when suitable, but saved observations do not establish current seats or rules. Refresh materially changed or stale facts and store a new snapshot. Preserve evidence files before registration; use the workspace's source-registration conventions where available. The scheduling importer does not register or authenticate sources.
- Recommend course mixes from unmet requirements, student goals, workload and actual downstream offerings. Qualitative instructor reviews supplement official facts; distinguish matching-course reports from other-course reports. Do not infer workload from units alone.
- Supply course mixes, eligibility findings and backup rationale to the solver. Use locked sections or a baseline when preserving part of an existing schedule. Inspect rejection reasons, unresolved checks, ties, shortages and search truncation. An exhaustive result covers only the supplied candidates, not every UCLA option.
- Return concise section tables from exported plan data: instructor, meetings, location, class IDs, units, finals and compromises. Compare requested distinct alternatives and useful backups; do not pad a shortage. If every result is poor, broaden researched options or explain the binding constraints rather than quietly relaxing them.

## Interpret and hand off

Trace substitutions through affected later terms, prerequisites, absence terms and next usable offerings. Label projections and displaced courses. Do not add a deferred course to a saved future-term plan without a decision.

Keep proposals, user choices, planner saves, enrollment, completion and credit approval distinct. Database results are based on supplied evidence, not an official eligibility ruling. Provide exact exported plan data to `ucla-class-planner` only when the user requests saved-plan changes; drafting alone does not authorize them. Return record updates to the owning academic workflow instead of maintaining a second student profile.
