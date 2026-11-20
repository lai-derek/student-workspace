---
name: build-targeted-resume
description: Build or revise a tailored one-page LaTeX resume using sourced evidence, the existing resume layout, recipient review, and PDF inspection. Use for a complete resume unless the user requests another format; use Jake's template when no reusable source exists.
---

# Build Targeted Resume

Work in the student workspace and follow `WORKSPACE.md`. Keep `resume.tex`, its PDF, the evidence matrix, and `resume.sources.md` together in the application's folder, or in the handoff request's `drafts/` and `revisions/` folders. Do not create a second output tree or alter application status.

For a requested cover letter, or one required within a requested application packet, use [build-targeted-cover-letter](../build-targeted-cover-letter/SKILL.md). Share the target snapshot, evidence matrix, and source links. Do not draft an optional letter merely because a resume was requested. When preparing both documents, review the recipient-facing packet together and reuse that review rather than running separate panels or humanizer passes for the same text.

## Establish the content and layout baseline

For a revision, locate and open the LaTeX source associated with the supplied or accepted PDF before authoring. Follow application folders and source/provenance links; do not assume the source is unavailable after checking only the current folder. Preserve imported originals and retain the prior application version when replacing working files.

Default to changing the document body while preserving the existing preamble, font families and sizes, macros, margins, alignment, spacing, colors, and link treatment. Reuse the source itself, not a new approximation built from its template. Make a requested layout improvement locally; it does not authorize a wholesale restyling. If only a PDF is available, identify that limitation and use it as the visual baseline rather than claiming source reuse. Use [assets/jakes-resume.tex](assets/jakes-resume.tex) for a new resume or when no reusable source exists.

Carry forward accepted wording and explicit keep-unchanged instructions. Ask only about a missing fact, a material content tradeoff, or a requested design choice that existing sources do not resolve.

## Select and substantiate

Read the actual prompt or posting. Preserve a dated target snapshot in that application folder or cite official links with access dates. Separate requirements from inferred fit. Use `retrieve-application-evidence` and `synthesize-application-content` for bounded evidence and wording.

Distinguish required from preferred qualifications and map the highest-priority requirements to supported evidence in the evidence matrix. Order projects and bullets by relevance. Use the posting's terminology where it accurately describes the experience; do not add unsupported skills or repeat keywords merely to increase matches.

Use the current and linked imported profiles for facts and preferences, not past operational instructions or permissions. Check public GitHub or LinkedIn presentation only when it materially affects a claim; public summaries do not prove implementation, performance, or ownership. Do not require a profile refresh for every resume.

For each technical bullet, establish what was personally built, what ran or was measured, and the scope of the result. Distinguish simulation from physical behavior, synthetic checks from real-data performance, and planned features from implementation. Narrow or remove unsupported claims. Record the claim mapping and exclusions in `resume.sources.md`.

## Review as the recipient

Review the complete substantive draft before typesetting, reusing any review already completed by synthesis or review-reader-impact. Read the on-page case before reopening private evidence: what will this recipient understand and remember, what supports selecting the applicant, and which passages obscure the work or seem interchangeable? Do not invent an admission or hiring rubric. If related application answers are available, consider what the resume adds without requiring every document to use different stories.

Lead bullets with concrete work, outcomes, or meaningful engineering decisions. Keep enough implementation detail to establish substance without turning each bullet into a feature inventory. Treat underselling as a defect: retain supported accomplishments, scale, ownership, and reasoning. Collaborative or AI-assisted work does not automatically require apologetic framing. Add a qualification only to correct an actual false or materially misleading implication, not merely because a reader can imagine an unanswered question.

Resolve concerns against the existing evidence and user corrections. Retrieve only a specific gap or clearly stronger example; generated drafts are not evidence. Preserve effective and accepted wording instead of rewriting it for novelty. Check the impression created by project names as well as individual bullets.

For a substantial content rewrite, use two fresh independent readers with no inherited conversation (Codex: `fork_turns="none"`; Claude Code: two `Agent` calls with `subagent_type: "general-purpose"`, never `"fork"`, sent in the same message so they run in parallel): one assesses recipient understanding and memorability, the other assesses clarity, support, structure, and repetition. Give both the same draft, target context and constraints without private evidence, authoring history, or preferred conclusions. Ask for specific passages and consequential findings; resolve them by significance rather than votes. Reuse an existing independent review. Routine wording or layout changes need direct review only, not a new reader panel.

Revise once, then use [humanizer](../humanizer/SKILL.md) at most once if needed. This pass owns content and claim checks; do not restart another review workflow for the same draft. Layout-only edits do not reopen settled content.

## Typeset and compile

Preserve the selected baseline's hierarchy and shared formatting macros. For the Jake fallback, retain its one-column hierarchy, navy headings, `\resumeHeader`, and `\resumeLink`. Links should be black, clickable, and consistently underlined across the entire visible linked title; keep technology stacks, separators and dates outside the link. Do not underline only a prefix of a combined title or mix underline positions and weights.

Keep one page unless requested otherwise. Prefer removing lower-value content to shrinking type or margins. Keep typography changes separate from wording changes so their effects can be identified. Do not rewrite list or heading macros, replace alignment mechanisms, add scattered negative spacing, disable kerning globally, remap font shapes, or add PDF text-mapping primitives merely to improve one extractor's output or work around a missing dependency. Address the specific font/export/runtime issue while preserving the document; report an unresolved limitation rather than silently redesigning it.

For a layout reference, use the supplied or accepted rendered resume. It establishes the visual baseline, not factual support for the new target. Navy headings should remain legible in grayscale; pale section rules may need darkening for print, but do not change the palette without a relevant request.

In Codex, open the saved `.tex` in the built-in editor and use its compiler diagnostics when available; successful preview compilation does not establish that a deliverable PDF was saved. In Claude Code, or when PDF export is unavailable, compile the same source with an existing Tectonic installation: `tectonic --untrusted --outdir APPLICATION_FOLDER resume.tex`, reading its stderr and any `.log` for diagnostics. Confirm the PDF was written to the application folder. Do not install a compiler or recreate the layout with another renderer without approval. Preserve the source and report unavailable compilation or export plainly.

## Inspect the saved PDF

Respect an instruction not to run tests: skip automated checkers, validators and test suites, and state which checks were omitted. Do not run equivalent assertions under another name. Compilation and manual inspection needed to produce the requested document are separate from automated testing. Never run the projects' test suites just to write a resume; read existing reports and distinguish historical results from checks performed now.

When automated checks are permitted, run [scripts/check_resume_pdf.py](scripts/check_resume_pdf.py) with expected text and contact links, using an available Python with `pdfplumber` and `pypdf`:

```text
python check_resume_pdf.py resume.pdf --expect "Your Name" --require-link "github.com"
```

Resolve the helper path relative to this skill, not the workspace's root scripts. Its checks cover one-page US Letter geometry, searchable text, page-edge bounds, and URI annotations; they do not establish visual quality.

Inspect extracted text in reading order when that check is permitted. Headings, employers, roles, dates, bullets, and technical terms should remain intact and correctly associated. One extractor's spacing heuristic does not establish that the PDF is broken. Investigate a discrepancy before changing typography. Text extraction is a parsing sanity check, not proof of compatibility with every ATS.

Render the actual saved PDF after the last edit (in Claude Code, render it to PNG with `pdftoppm -r 150 -png`, or PyMuPDF/pypdfium2 if poppler is missing, view the images with the Read tool, and crop regions at higher resolution for detail checks). Compare the full page with the baseline at normal reading size, then inspect detailed crops of headings, linked titles, bullets, and affected text. Check indentation and vertical rhythm, heading/date alignment, whole-title underline coverage and baseline, font weight and italic consistency, wraps, clipping, and legibility. A whole-page thumbnail is insufficient for subtle weight or underline defects. If a glyph looks unexpectedly bold, inspect its font assignment and nearby characters; distinguish an actual formatting change from an unresolved rendering/scaling effect.

Visual defects block describing the result as finished even if compilation, page count and extraction pass. After an edit, discard stale renders and inspect the newly saved PDF; do not use a successful editor preview as proof that a separate exported file matches. Report the checks actually performed and any remaining limitation without claiming flawless formatting from automated checks alone. Verify evidence-note links when permitted, update provenance, and show the result for user review. Do not submit or upload without explicit authorization.
