---
name: ingest-application-materials
description: Organize supplied resumes, essays, documents, and user clarifications into preserved sources and linked personal knowledge in the student workspace. Use for importing material, reconciling duplicates, or recording corrected facts.
---

# Ingest Application Materials

Work from the private workspace root containing `WORKSPACE.md` and `.student-workspace/workspace.json`. Keep personal files outside `tools/`. Read workspace instructions and [record conventions](references/records.md) before saving sources or labeled records.

## Find what already exists

Inspect the supplied material. Search `knowledge/CATALOG.md` for identifying terms, then follow any linked imported catalog. Read likely matching records before creating a new one. Search source text or read the full catalog when results are sparse or a likely credential is missing. Resolve relative links from the file containing them.

The preserved application-content snapshot is reference material. Add corrections and new knowledge under the current `knowledge/`; leave the preserved copy unchanged. Keep an existing ID when updating the same entity, and make the current catalog point to the revised record.

## Preserve and reconcile

- Copy new originals into `sources/originals/` without changing their bytes. Check existing source-manifest paths and hashes before making another copy.
- Save faithful transcriptions in `sources/markdown/`, preserving wording and order. Use stable segment headings for precise citations and mark unreadable passages.
- Save user-supplied facts or corrections in a dated source note before reusing them in knowledge or saved drafts. Preserve the supplied wording and its context.
- Register saved sources with `student-workspace source register` (or save and register in one step with `student-workspace source import`) as described in the record conventions. Verify the copy before removing an inbox item; leave it in place unless cleanup is authorized.

Merge records only when the evidence supports the same entity. Add aliases for alternate names; retain separate events and genuinely incompatible claims. Omission is not contradiction. Keep scopes such as gross raised and net donated distinct.

Ask only about uncertainty that materially affects identity, credentials, metrics, chronology, outcomes, ownership, eligibility, or reuse. Ordinary autobiographical details supplied in the conversation are self-reported evidence; they do not need clause-by-clause corroboration. Preserve qualifiers rather than forcing a more definite account.

## Save and check

Create only useful activity, story, capability, or theme records. Link concrete claims to source passages, retain uncertainty, and use stable IDs. Update the current profile and catalog where affected; check easily missed academic results, honors, coursework, and constraints without creating redundant records.

Verify source hashes, transcription fidelity, record IDs, catalog links, and evidence anchors for the changed files. Run `student-workspace audit` when source registrations change; it checks source integrity and exposure, not the accuracy of the prose. Run it from `tools/.venv` (`tools/.venv/Scripts/student-workspace.exe` on Windows).

Report material additions, merges, unresolved facts, and checks performed. Do not turn saved drafts into evidence or update tool decisions such as opportunity boards as part of ingestion.
