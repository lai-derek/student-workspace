## Opportunity discovery

Collection runs daily when scheduled, or on request with
`opdisc --workspace WORKSPACE run`; its database, exports and logs live in
`.student-workspace/opportunity-discovery/`. Open `Open Dashboard.cmd` in a
separate window on Windows, or run `opdisc dashboard WORKSPACE`. Stop an open
dashboard before changing board state.

### Screening profile

Use documented answers first; ask only about missing or contradictory major,
expected graduation, year in program, class standing, available geographic
regions, remote work, interests, and opportunity focus: early
exploratory/freshman-sophomore programs, standard undergraduate internships,
or entry-level full-time jobs. Default city preferences to their surrounding
metro areas. Research official regional/municipal sources for city, county and
regional aliases; save source URLs in the private region settings. Cities within
the same region should resolve to the same metro, rather than literal city
filters. Summarize the scope and ask only about material ambiguity or explicit
city/commute limits. Preserve actual majors and normalize suitable degree
aliases and broad academic families into major_match_terms. Ask whether regions
are preferences or limits and whether short programs elsewhere are acceptable
with covered travel. Then import structured private screening settings with
`opdisc profile WORKSPACE FILE`, following
`tools/opportunity-discovery/schemas/opportunity-screening-profile.schema.json`.
Keep unknown credentials unknown. Do not require the user to write JSON.
Reuse documented citizenship and institution regions. Distinguish current degree
enrollment from an explicitly documented completed-degree inventory; missing
inventory is null, not an empty list. Ask about school-term placement
availability only when relevant. Do not equate citizenship with
security-clearance eligibility.

### Opportunity review

When asked, follow `tools/opportunity-discovery/docs/PRIVATE_WORKSPACE_OPERATIONS.md`
and `docs/INTEGRATION_CONTRACT.md` there for review import. Read the profile and
current exports; check run_summary.json and source_health.json for collection
failures. The packet is a sample. Use `opdisc screen WORKSPACE` on the whole
collection and `opdisc screening WORKSPACE --compact` for bounded, balanced
recommended review batches. Follow review_selection: include promising
clarification leads alongside clear matches, group shared profile questions,
and reuse saved findings. Do not spend equal research on every plausible lead.
Use --include-deferred for the broader feed. Unchanged unresolved official
checks retain their questions until new evidence, changed facts, approaching
deadlines or staleness warrant another check. An optional semantic screening
pass may interpret captured text; import it with `opdisc apply-screening`.
Screening is separate from official checks. Use ai_evidence_packet to compare
quoted requirements with documented facts, preserving preferred
qualifications, graduation alternatives and undergraduate exceptions. For
accuracy audits, use --audit-sample to inspect selected, deferred and excluded
records; the stratified sample is not a population error-rate estimate. Check
official pages and personal fit, preserve uncertainty, and confirm a successful
`opdisc apply-review` before reporting that the board is updated. State how
much was screened, plausible, officially checked, and still awaiting
investigation, and what remains unresolved. Carry unchanged findings forward;
prioritize changed requirements, deadlines, and stale checks.
`opdisc request WORKSPACE OPPORTUNITY_ID TYPE TEXT` creates an application
handoff for a board record.
