# Personal records and sources

These conventions apply to the private workspace, not a tool's database or board schemas. Preserve existing IDs and source files. Keep imported snapshots unchanged; write new or revised records in the current workspace.

## Locations

| Material | Location | ID prefix |
| --- | --- | --- |
| Original documents | `sources/originals/` | None required |
| Faithful transcriptions and dated user notes | `sources/markdown/` | `src-` |
| Activities | `knowledge/activities/` | `act-` |
| Stories | `knowledge/stories/` | `story-` |
| Demonstrated capabilities | `knowledge/capabilities/` | `capability-` |
| Interpretive themes | `knowledge/themes/` | `theme-` |

Use lowercase kebab-case filenames matching stable IDs. Canonical records have YAML frontmatter with `id`, `type`, `title`, `summary`, and `review_status`; aliases are optional. Source notes also have `origin` and an extraction method when applicable. Record a source date only when known; a receipt date is not a submission or event date.

Review statuses are `verified` (checked against the cited evidence), `needs-confirmation`, and `conflicting`. Verified self-report remains self-report, not independent corroboration. A mixed-status record can supply individually sourced facts unaffected by its unresolved claim.

For concrete facts, use stable headings such as `### fact-robotics-role`, stating the claim, status, and evidence link. Stories should make the situation, personal actions, result, and boundaries clear; include reflection only when supplied. Capabilities need demonstrated behavior, while themes are labeled interpretations.

Keep one current catalog row per canonical record, with ID, type, linked title, aliases, summary, and status. A linked imported catalog may remain as a retrieval index. For a revised imported record, preserve its ID and link to the earlier version; make clear which version is current rather than treating them as two activities.

## Source registration

Read `tools/student-workspace/schemas/source-manifest.schema.json` before changing `.student-workspace/source-manifest.json`; prefer the `student-workspace source` commands. Preserve existing entries and custom metadata. Each imported source needs:

- SHA-256 of the saved bytes;
- original filename;
- `sources/`-relative stored path using forward slashes;
- actual import time as ISO-8601 with a timezone.

Register originals and saved transcriptions or source notes. Reuse an existing matching registration instead of adding duplicates. Source material stays unchanged after registration; preserve later corrections as new source notes. Verify each stored file and hash, and validate the manifest against the installed schema.

## Drafts and evidence notes

Save generated work under `applications/`. For a handoff request (created by a tool or `student-workspace apply request-url`), use its `drafts/` and `revisions/` folders and retain the request files. Otherwise use a descriptive application folder; date it by creation unless a different date is established.

Keep a neighboring `<name>.sources.md` using the [evidence-note template](../../synthesize-application-content/assets/provenance-sidecar.md). Record the request, consulted sources, factual claim mapping, unresolved claims, and meaningful creative choices. Fill only relevant entries. Drafts and evidence matrices are outputs, not new factual evidence.
