---
name: audit-application-system
description: Audit application sources, personal records, evidence selection, drafting quality, and skill behavior. Use for session reviews, unsupported claims, missed evidence, repeated writing failures, or requested workflow improvements.
---

# Audit Application System

Follow `WORKSPACE.md`. Start with the named artifact or session delta. Audits are read-only unless corrections are requested. Ask before changing workspace instructions, tool code/schemas, stable IDs, or board state outside the task.

## Choose the scope

- Validate changed files and links for a routine check.
- Trace a named output or claim for a targeted audit.
- Read [session-close.md](references/session-close.md) for a requested session or end-to-end workflow review, including transitions between application context, drafting, narrative revision, and completion.
- Read [deep-audit.md](references/deep-audit.md) only for a system-wide audit.

## Verify

For source/reference integrity or Git-exposure issues, run `student-workspace audit WORKSPACE_PATH` from `tools/.venv`. Do not collect, restore, or import reviews just to audit content. Skill-only changes need skill validation and relevant link/behavior checks, not an unrelated whole-workspace audit.

Inspect the affected chain: hashes and transcription where relevant, source registrations, IDs/statuses, catalog entries, links/anchors, draft provenance, prompts, and limits. Consult [record conventions](../ingest-application-materials/references/records.md) only when needed. Structural checks prove neither factual truth nor persuasive quality. Use the known delta rather than modification-time scans or requiring Git access. Preserve imported originals and distinguish pre-existing defects.

## Investigate and correct

Trace only the necessary source, record, evidence, draft, and provenance links. Separate differences in time, role, contribution, or metric; generated drafts establish no facts. Check ownership, measured behavior, and scope, missed evidence and common ground, repeated reads, and unnecessary questions about ordinary self-report.

For workflow failures, trace where intent, evidence, accepted content, or unresolved work was lost between stages. Separate observed causes from hypotheses, changes already applied from remaining gaps, and structural validation from demonstrated behavioral improvement. For writing failures, separate evidence selection from expression. Track accepted wording, voice, confidence, and the central question across revisions. Distinguish absent guidance, conflicting guidance, and failure to follow adequate guidance; adding instructions does not fix every execution failure.

When authorized, fix the smallest evidenced cause and recheck affected files without weakening checks or overwriting user decisions and custom metadata. For skill improvements, edit the owner skill and relevant routing rather than adding overlapping systems or recipient-specific rules. Reuse current reads and earlier findings; inspect only changed claims and affected references unless a new concern warrants more.

For repeated failures or substantial workflow changes, use [behavioral-validation.md](references/behavioral-validation.md) when a trial adds useful evidence. Report concrete findings, corrections, checks, and limits. No separate report for a clean routine audit unless requested; report text-size reductions as such, not as measured billed-token savings.
