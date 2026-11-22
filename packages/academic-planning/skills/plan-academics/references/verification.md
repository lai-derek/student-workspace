# Verification and efficient research

## UCLA courses

Use the official catalog for course units and prerequisites; the named term's public Schedule of Classes for actual offerings, restrictions, meetings and published finals; departmental annual lists for tentative offering patterns. Cross-listed numbers do not guarantee both enrollment listings have capacity. Record class IDs and the checked date only when they matter to the plan.

Preserve the distinction between earned degree units and appointment-eligible units. Read current official rules on AP/IB, transfer and in-progress units rather than applying the earned total to every purpose. A projected class level for course requisites does not establish an enrollment-priority tier. Keep unexplained audit/portal differences explicit; do not assume rounding or silently change posted credits to reconcile them. Compare appointment quality only against the relevant official appointment range; do not infer it from a screenshot's total credits.

## Course-sequencing and enrollment comparison

Use this comparison for course selection, substitutions, workload changes, prerequisite sequencing, enrollment-pass allocation and degree timelines in any term or academic year. It applies to home-campus quarters, summer sessions, host semesters and returns from absences. Keep the user-facing explanation proportionate; a short question can reuse a previously established comparison.

For courses that compete for the same slot or enrollment units, establish:

- Their unmet degree role, prerequisites versus corequisites, and whether the student already satisfies them.
- Relevant downstream courses and their usable offerings, accounting for annual cycles, session dates, abroad or other absences, and credit/grade posting when it affects prerequisite clearance. Compare the candidate completion dates: which downstream start dates actually change? Follow affected branches through consequential bottlenecks, including capstone sequences or graduation when relevant; do not stop automatically after one term. Mark unpublished offerings and pending approvals as assumptions.
- User timing goals independent of prerequisites, such as finishing labs while lecture material is fresh, plus fixed meeting hours and scheduling constraints.

Compare complete alternatives rather than isolated substitutions: courses and requirement roles in each affected term, units and fixed laboratory/meeting hours, useful fallbacks if access fails, displaced work, and effects on the user's timing and completion goals. Continue far enough to identify whether the alternatives converge or leave a material scheduling difference; a full degree audit is necessary only when the claim depends on it. Do not add every deferred course to the next available term or retain an extra whose requirement role has disappeared.

For enrollment-pass decisions specifically, add protected courses and units, remaining later-pass targets and materially different uses of available pass capacity. Using the entire pass cap is not an objective by itself. Do not impose a first-pass structure on planning questions that do not involve enrollment passes.

Separate the consequence of missing a course from the evidence that it will fill. If demand evidence is unavailable, explain the tradeoff and make the ranking provisional. Do not assert a unique best combination from capacity or prerequisite count alone.

Check these reasoning boundaries before finalizing:

- A prerequisite can unlock several courses without advancing any of their actual start dates. Conversely, a limited annual offering can make one missed prerequisite consequential.
- A lab can deserve enrollment priority because of the user's completion goal or a compatible time slot even when it does not gate the major sequence. Do not invent a prerequisite between successive lab numbers.
- Two courses needed for the same later course need not have the same urgency today; compare their alternate offering opportunities and workloads.
- A backup recommendation must include its effects across the affected terms, not only the replacement term. Different backups may deserve different rankings after that comparison.
- When challenged, distinguish a new constraint from an overlooked existing one. Correct the specific reasoning or factual claim rather than changing the recommendation without an explanation supported by the conversation.

Keep personal deadlines, course facts and worked plans in shared academic records and their dated sources, not in these workflow instructions. Retrieve the records relevant to the requested horizon; do not default to a historical term's proposal or treat it as a selected plan.

## Fiat Lux and changing course directories

In the public UCLA Schedule of Classes, choose the requested term, Search By > Fiat Lux Classes > All Fiat Lux Classes, then expand the results. Open class details for topic descriptions, instructor, units, grading, restrictions and degree use. If a topic description is absent, state that fit is unassessed; department or instructor identity alone does not establish the seminar's subject.

For richer descriptions, the official [Fiat Lux enrollment page](https://www.uei.ucla.edu/academic-programs/fiat-lux/courses-enrollment-deadlines/) links to a topic directory with term and category filters. Verify that the resulting course links/descriptions match the selected term. A changed dropdown with old term codes or unchanged old results is stale content, not evidence of current availability. In browser automation, use an actual select/change interaction and inspect the refreshed results; avoid repeatedly toggling a broken filter.

Themed pages and archives may list appealing past seminars; confirm each candidate in the requested term's schedule before recommending it as offered. When a term's list is sparse, check the official [faculty proposal deadline](https://www.uei.ucla.edu/academic-programs/fiat-lux/submission-deadlines-proposal-process/). Report the dated snapshot and whether additions are still plausible. Absence from an early list is not proof the seminar will not run. Do not invent titles or present historical courses as current alternatives.

For an optional seminar, distinguish discussion/exposure and faculty contact from technical training or a research/startup pipeline. Verify GE or other requirement recognition rather than inferring it from the topic. Evaluate its time cost alongside the user's current workload and enrollment-pass constraints; one P/NP unit does not automatically justify consuming scarce first-pass capacity.

## Optional exchange research

Use the destination's UCEAP academics/eligibility pages for UC program rules, then host incoming-exchange rules and target-year fact sheets for access. Start from links in `knowledge/academics/ABROAD.md` and its dated research sources. A residential college is not necessarily an academic faculty; host minimum credits may be below UCEAP's required load. Department placement and course classification need their own evidence.

Check only claims that could change the current answer. Previously verified same-session findings can be reused with their dates; old semester lists do not prove availability in the requested host term. Report unresolved approvals plainly rather than reopening the entire research trail.

## Fetch failures and output control

After a failed page/PDF fetch, try one independent access route if it is likely to resolve a material question. If that also fails, record the exact remaining gap and proceed with unaffected findings. Do not repeatedly download the same document. Prefer batched independent page reads, concise extracts and stored file paths over printing whole documents or base64 content. Avoid large combined tool responses that truncate evidence.

## Record maintenance and recognition

Preserve new evidence unchanged in `sources/` and register it through the existing manifest contract. Update the owning record, relevant narrative and concise profile/catalog links. Source dates describe scope; they do not automatically rank authority.

| Record | Meaning and update rule |
| --- | --- |
| `academic.yaml` requirements | Stable requirement/slot IDs. `units` is a planning value. `selected_course` identifies a required or chosen course. `satisfied-historical` preserves a dated prior audit; `needs-update` means current application is unknown. Current satisfied/remaining/in-progress states need sourced updates. |
| credits / credit_controls | One award per original course/exam, including explicit zero-credit duplicates. Keep original evidence dates; reconfirm with `last_confirmed` and new source references. Controls reconcile the historical snapshot, not current eligibility. Recognition does not award credit again. |
| audit_snapshot / current_coursework | Reconcile earned and in-progress units separately. Current coursework remains in progress until completion evidence arrives. Degree-unit shortfalls stop at zero. |
| assignments | Sole owner of active course-term placement: requirement ID, course, named term, positive confirmed units, planned/enrolled/completed status and `decision_source`. A selection is not enrollment. Proposals and alternatives do not become assignments without a decision. |
| planning_targets / term_proposal | Targets are desired completion dates. The next-term proposal stays proposed and needs a check for its own term's offerings/eligibility. Record requisite, linked-section, meeting and final checks before promoting selections. Appointment facts and pass caps stay separate from proposals and earned credit. |
| recognition_options | Sole structured owner of conditional existing-credit use. Link award IDs and requirement IDs; record area, dated authority/approval, course/unit minima, separate declaration/DARS states and implementation instructions. Remaining counts/units are derived. Keep any area choice in sourced shared records; when abroad records are enabled, breadth_exploration.selected may own that choice. |
| abroad.yaml | Owns destination preference, GE reservation, dated rules, historical candidates and approved host-course uses. An approved course needs `course`, `approval_source` and the approved `degree_use` when established. Host permission, UCLA use and enrollment are separate. Legacy unit proxies remain unconfirmed. |
| research_updates / useful_requirement_ids / load_planning | Brief dated findings, scoped supersession and links to existing requirement slots. Detailed course research remains in preserved sources. Missing classifications or conversions do not become a faculty share or sufficient-load conclusion. |
| shared goals / narrative records | Goals own preferences and tradeoffs. Narratives explain research and scenarios. If a narrative fact should appear in a generated view, reconcile it into the consumed YAML or goals record. Linked narrative edits alone do not require generation. |

A written advisor ruling may settle specific existing credits' eligibility without establishing area selection, declaration or posting on a refreshed audit. The dated audit still governs what it actually posted. Confirmed declaration and DARS application each need their own evidence (`declaration_source`, `dars_source`). Retain useful administrative instructions in the recognition option; do not keep a second editable ruling summary. Recompute both course and unit needs for the particular option without marking requirements satisfied or adding awards.

A `supersedes` entry names the older source and the exact claim scope replaced. Preserve that source unchanged; unrelated findings remain usable. Inspect the original passage when resolving a dispute, rather than inferring what an earlier response said. Keep personal cases and course facts out of reusable rules.

For a load gap, investigate other unmet requirement roles and exclusions before adding redundant courses or advancing a prerequisite solely for its label. Check exact subject codes and course identity. A course cannot fill separate slots without explicit permission. Confirm host units and UC conversion separately; course count alone does not establish a sufficient load.

Generated files are views. Batch record changes, use `academic-planning check` and `build`, reconcile independent output edits and inspect affected sheets/PDF/Markdown after generation. Rendering consumes academic YAML, optional abroad YAML, shared goals, registered referenced evidence, configuration and package code. A rebuild establishes no new academic fact. Preserve imported source trees and the full-workspace backup contract.
