# Editing shared records

The tool reads these files relative to the private workspace:

| File | Purpose |
| --- | --- |
| `knowledge/academics/academic.yaml` | Requirements, awarded credit, selected assignments and next-term proposals |
| `knowledge/academics/abroad.yaml` (optional) | Destination preferences, access research, candidates and approvals |
| `knowledge/goals/academic-career.md` | Shared preferences and explanations |
| `knowledge/academics/planning-config.json` | Unit label and chronological period ordering |
| `.student-workspace/source-manifest.json` | Shared Student Workspace source registry |

Use `demo` in a separate empty directory to inspect a complete synthetic example. `init` creates empty personal records, not the demo. All academic YAML and configuration currently use `schema_version: 1`. Unknown versions are rejected; records are never converted automatically. Follow INTAKE.md and obtain student review of extracted DARS facts before adopting them.

## Academic YAML

`requirements` rows need a unique `id`, a readable `requirement`, a `status` and nonempty `source_refs`. Units may be unknown (`null`) or nonnegative. Statuses are `needs-update`, `satisfied-historical`, `satisfied`, `remaining` and `in-progress`. `selected_course`, `prerequisites` and `notes` help explain the plan. A requirement's unit value is not an earned-credit entry.

`credits` rows need unique `id` and `(institution, course, term)` identity, `kind`, nonnegative `awarded_units`, `evidence_date` and `source_refs`. Kinds are `transfer`, `ap`, `ib`, `institution`, and the legacy `ucla` alias. `recognition` describes requirement satisfaction separately. Keep zero-unit duplicate awards explicit rather than counting the same credit twice.

Optional `credit_controls` describe a dated audit baseline with `as_of`, `total_units`, evidence and per-kind totals such as `transfer_units` and `ap_units`. The validator compares awards with that evidence date. These controls are historical and should not be relabeled as current totals.

`assignments` is the active course-to-term plan. Each row needs `requirement_id`, `course`, positive `units`, a configured `term`, a `status` of `planned`, `enrolled` or `completed`, and `decision_source`. One requirement/course cannot appear twice in the active plan. Assignment status and the owning requirement's recognition can differ while a new audit is pending; keep that difference explicit.

`current_coursework` holds sourced in-progress course rows. Neither a nonempty course/credit list nor a populated requirement list establishes complete academic totals. Recorded-row subtotals are separate from established totals; missing totals are `null` in check/context and Unknown in generated views.

Optional `audit_snapshot` supplies independently established `earned_units`, `in_progress_units` and/or `minimum_degree_units`, with `as_of` (ISO date) and nonempty `source_refs`. Only supplied, sourced fields are established; a degree minimum alone establishes neither earned nor enrollment totals. Existing fully sourced snapshots continue to reconcile against row sums. A field absent or `null` remains unknown. Historical `credit_controls` do not establish current totals.

`record_coverage` separately describes the completeness of `credits` and `current_coursework` rows. Each entry has `status: unknown | partial | complete`. A complete entry requires an ISO `as_of` date and nonempty checked `source_refs` supporting that completeness. This permits an evidenced empty ledger or no current enrollment to establish a legitimate numeric zero. A source containing one requirement or one award is not evidence that all awards/enrollment were extracted. Do not mark completeness merely to remove an Unknown label. Fresh records explicitly start unknown; legacy nonempty lists without evidence of completeness are partial subtotals.

For example, after evidence and student review establish a complete award ledger but current enrollment remains unresolved:

```yaml
record_coverage:
  credits:
    status: complete
    as_of: '2031-10-01'
    source_refs: ['sources/your-registered-evidence.md']
  current_coursework:
    status: unknown
```

An explicitly partial/unknown extraction can coexist with a separately sourced audit total. Its subtotal cannot exceed that total. Complete rows must reconcile exactly; when no coverage entry is present, existing audit-to-ledger reconciliation remains required. `unit_coverage` in check/context records the row status and the total's basis (`audit_snapshot`, `complete-record-coverage`, or null). `recorded_earned_units` / `recorded_in_progress_units` always describe arithmetic subtotals; `earned_units` / `in_progress_units` describe established totals or null.

Remaining-unit calculations require the evidenced degree minimum and established earned total; the conditional calculation also needs established in-progress units. Otherwise they remain unknown. Known results stop at zero. A remaining-unit assertion without the required totals is rejected. These unit checks do not prove that all degree requirements are satisfied.

`term_proposal` holds an unselected scenario. It must have `status: proposed`, an exact term, course rows with positive units, and `availability_check` containing the same term, checked `available_courses` and `source_refs`. Candidate meetings, when supplied, are checked for overlap. This validates supplied evidence; it does not fetch schedules. `planning_targets` hold desired completion dates with evidence and do not create active assignments.

`profile` can hold institution, major and GPA (`current_gpa`; the old `current_ucla_gpa` key is accepted). Missing GPA stays unknown. Appointment fields may be retained in `enrollment_appointments`; they do not change awarded credit.

## Abroad YAML and evidence

Use `term`, `route`, `destination_preference`, dated `research_sources`, `destinations`, `historical_candidates`, `approved_courses` and `questions` as relevant. A recorded approval needs `approval_source`; `degree_use` describes its scope. The legacy historical-candidate field `ucla_credit` must remain `unapproved`. Its name is retained for compatibility, not interpreted as an institution-independent approval rule.

Evidence keys (`source_refs`, `research_sources`, `source_keys`, `decision_source`, `approval_source`, `preference_source`, `declaration_source`, `dars_source`) are checked recursively. References must resolve inside `sources/` or `knowledge/`; registered source bytes must match their manifest hashes. Markdown heading anchors are checked for simple unique headings. Preserve source corrections as new evidence rather than changing the registered original.

Configure a different calendar with `period_order`, for example `["Winter", "Spring", "Summer", "Fall"]`; terms use `Period YYYY`. `unit_label` controls presentation and does not convert semester/quarter/host credit. Configuration is reloaded and validated with each record load; edits during loading/rendering stop publication rather than certifying stale settings. Conversion requires separate evidence and explicit award values.

## Conditional recognition and research

recognition_options in academic.yaml reference positive existing credit_ids and existing requirement_ids, each unique within the option. Required fields: id, area, eligibility (approved/pending/rejected), minimum_courses (positive integer matching requirement slot count), minimum_units (positive finite units), declaration_status and dars_application (unconfirmed/confirmed). Approved eligibility needs approval_source; confirmed declaration and DARS application need declaration_source and dars_source respectively. implementation_notes retain administrative instructions. Derived remaining course and unit minima are independent and stop at zero. Pending/rejected options use no awards. Options remain conditional and never add earned credit, select an area or approve host coursework. Obsolete breadth_credit_ruling stops validation for reconciliation.

research_updates may be in academic.yaml or optional abroad.yaml: unique id, as_of (ISO date), topic, summary and nonempty source_refs. Optional supersedes entries need an explicit scope and prior source_refs. These statements replace only named claims; older originals and unrelated findings stay visible. The generator checks provenance and structure, not authority or factual truth. abroad.yaml useful_requirement_ids must reference unique existing requirement slots; load_planning summary/unresolved remain statements needing evidence and interpretation, not an automatic conversion calculation.
