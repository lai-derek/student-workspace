# Scheduling operations and JSON interface

Uses the Python standard library only; no Node, service or credentials are required. Run it with the workspace's tools environment (`tools/.venv/Scripts/python.exe -m academic_planning.scheduling` on Windows); `python scheduling.py` below stands for that command:

```text
python scheduling.py --workspace STUDENT_FOLDER init
python scheduling.py --workspace STUDENT_FOLDER import offerings.json
python scheduling.py --workspace STUDENT_FOLDER solve request.json
python scheduling.py --workspace STUDENT_FOLDER inspect
python scheduling.py --workspace STUDENT_FOLDER inspect --snapshot SNAPSHOT_ID
python scheduling.py --workspace STUDENT_FOLDER inspect --snapshot SNAPSHOT_ID --course COURSE_ID
python scheduling.py --workspace STUDENT_FOLDER inspect --run RUN_ID
python scheduling.py --workspace STUDENT_FOLDER inspect --plan PLAN_ID
python scheduling.py --workspace STUDENT_FOLDER export PLAN_ID
python scheduling.py --workspace STUDENT_FOLDER receipt observation.json
python scheduling.py --workspace STUDENT_FOLDER backup NEW_BACKUP_PATH
```

`--database PATH` overrides the workspace default `knowledge/academics/schedules.sqlite`. Global options precede the operation. Commands print JSON to stdout, errors to stderr and exit 1. Save stdout as an export when needed. Database inspection is read-only; initialization is explicit. No command changes MyUCLA, academic YAML, evidence files or degree decisions.

The database is authoritative for imported scheduling observations, requests, results and receipts. JSON files are interchange/export data. Existing YAML retains credit, degree and selected-assignment ownership. Sources remain files or URLs; import validates shape and relationships, not official truth. Give each changed offering snapshot a new ID. Reimporting exactly the same ID/data is harmless; replacing its contents is rejected.

## Offering snapshot

See [synthetic offerings](../assets/offerings.example.json) for a runnable input. No real student data is included. All objects reject unknown fields.

- Root: `version: 1`, nonempty `id`, `institution`, `term` (Fall/Winter/Spring YYYY), `observed_at` (YYYY-MM-DD), and lists `sources`, `courses`, `sections`, `bundles`.
- Each source: HTTP(S) `url`; optional `evidence_ref` to a preserved file. The root observation date applies to the snapshot; capture mixed-date evidence in separate snapshots when it changes the interpretation.
- Each course: unique `id`, `title`, nonnegative `units`; optional string list `aliases` and `equivalence_group`. IDs are enrollment identities. Aliases are display/research aids, not permission to use another enrollment listing. Assign the same equivalence group when two listings must not earn duplicate course credit in one schedule.
- Each section: unique `id` (use official class ID), `course_id`, `component`, `label`, `availability` (`open`, `closed`, `unknown`), `meeting_status` (`scheduled`, `none`, `unknown`), `meetings`, `exams`; optional `instructor`, `location`, `notes`. Availability is a researched observation; student-specific restrictions belong in eligibility findings.
- Meetings: `days` from `M,Tu,W,Th,F,Sa,Su`, `start` and `end` as 24-hour HH:MM, with end after start. Optional paired inclusive `start_date`/`end_date` for parts of term. Overnight meetings must be split. Empty meetings with status `none` means explicitly no timed meetings; `unknown` means unresolved.
- Exams: `null` means unknown; `[]` means verified none; otherwise a list of `{date,start,end}` using local dates/times. Do not substitute `[]` for unpublished finals. Meeting preferences and unavailable-time blocks concern regular meetings only.
- Each bundle: unique `id`, `course_id`, nonempty `section_ids` listing a complete allowed enrollment combination. Components must belong to that enrollment course. The importer cannot infer whether a required lab is missing: research the official linkage and enumerate complete combinations explicitly.

## Planning request

See [synthetic request](../assets/request.example.json). Required: `version: 1`, `snapshot_id`, `scenarios` containing `{id,course_ids,rationale?}`. A scenario is a fixed course mix, not a pool from which the solver selects courses. Backup substitutions are separate scenarios. Course IDs must match snapshot enrollment identities.

Optional fields:

| Field | Meaning |
|---|---|
| `eligibility` | Map course ID → `eligible`, `ineligible`, `unknown`; omitted = unknown. Agent researches prerequisites, corequisites and restrictions; code trusts these findings. |
| `locked_sections`, `excluded_sections` | Lists of official section IDs; applied to every scenario. A lock on a course omitted by a backup makes that scenario infeasible. Use separate requests when scenario constraints differ. |
| `blocks` | Meeting-shaped unavailable-time intervals. |
| `min_units`, `max_units` | Nonnegative inclusive limits. No universal full-time assumption. |
| `preferences` | Ordered list of `{kind:before,time:HH:MM}`, `{kind:after,time:HH:MM}`, `{kind:day,day:F}`, or `{kind:changes}`. Use JSON string values. No preferences by default. |
| `baseline_sections` | Section IDs in this snapshot; required for the changes preference. Refresh/reconcile baseline identities before replanning across snapshots. |
| `travel` | Directed allowances `{from,to,minutes,verified}` between exact location strings. Verified insufficient travel rejects a plan; missing/estimated allowances flag unresolved travel when the gap is under 60 minutes. Estimates do not certify feasibility. |
| `count` | Positive integer, default 3 returned alternatives per scenario. |
| `search_limit` | Positive integer, default 100000 examined bundle combinations per scenario. |

Ranking is lexicographic in preference order, never an unexplained weighted sum. A before/after violation counts weekly meeting occurrences, using start/end respectively and strict comparison; a day violation counts meetings on that day. Changes counts the symmetric difference of selected and baseline section IDs (a replaced section counts as one removal plus one addition). Stable section IDs break presentation ties; equal-score plans remain eligible. Units come from courses, not component rows.

Known closed sections, ineligibility, equivalent-course duplication, overlaps, blocks and hard limits reject combinations. Unknown availability, eligibility, meetings, locations, exams or short-gap travel remain explicit in `unresolved`. Known exam overlap rejects even on the same day; adjacent exams do not overlap. No capacity reservation or enrollment promise is made.

## Results and exports

`solve` stores the request and deterministic results, returning a run ID, snapshot provenance and per-scenario counts, rejection reasons, `exhaustive`, `shortage` and ranked `plans`. Search limits apply before ranking: when truncated, the best examined result is not necessarily globally best. Shortage under truncation means only “not found within this search.” An empty candidate bundle list produces zero alternatives, not fabricated schedules.

Each plan includes its ID, scenario, snapshot, term, full selected course/section records, units, score, preference violations, unresolved checks and verification classification. `checked-against-supplied-snapshot` means only that supplied checks passed; `conditional` identifies remaining unknowns. Neither means official academic approval or live availability. Export stored plan IDs for exact planner entry; do not retype or independently maintain a second schedule dataset.

## Planner observation

`receipt` accepts:

```json
{
  "plan_id": "ID_FROM_EXPORT",
  "plan_name": "Observed UI name",
  "term": "Winter 2031",
  "observed_at": "2030-11-02",
  "reloaded": true,
  "section_ids": ["IDS_READ_FROM_UI"],
  "units": 9,
  "evidence_ref": "optional screenshot or observation file"
}
```

The observation must come from an independently reloaded UI, not a copy of expected input. Code compares term, all component IDs (including duplicate counts) and units, and requires `reloaded: true`. It records verified or incomplete status and differences without modifying the expected plan. A missing component leaves the receipt incomplete. This trusts the agent's observation and does not authenticate the browser or establish enrollment. To inspect stored receipts use `inspect --plan PLAN_ID`.

## Installation and backup

The Student Workspace setup installs the scheduling code with academic-planning and generates discovery entries for these skills. Existing personal YAML and source files are not distribution inputs. A fresh student needs only their own workspace folder and `init`; copy nothing from another student's database.

Use `backup` to create a consistent, new SQLite backup file even while a connection is open. Restore by closing connections and copying a validated backup to a new database path, then inspect it. Stop writers before a raw full-workspace archive, or include a SQLite backup taken with this command; do not copy a live database file piecemeal. Sources and degree YAML still require the existing full-workspace backup. Schema versions other than 1 are rejected; future upgrades need an explicit conversion, never a silent reset.
