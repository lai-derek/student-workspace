# Decisions

One entry per decision that shapes the product or the code: the problem, the
options considered, the choice, why, and how we'll know whether it worked.
Newest first. Entries are not edited after the fact; when a decision changes,
add a new entry that replaces it and link the two.

---

## Open: one app, or separately installed tools?

**Problem.** Students choose which tools to install. That made sense when the
tools were separate projects. Now they ship from one repository, and every
target student (a UCLA undergraduate) would use both tools.

**Options.**
1. Keep optional installs: a tool picker in setup, a version per tool with
   compatibility ranges, and every install combination to test.
2. One app: always install every package, give the app one version, and make
   features optional inside the app (daily collection, the first collection,
   academic setup). Packages stay separate in the code.

**Leaning.** Option 2, decided before the 0.2.0 release. Not yet decided.

---

## 2026-11-22: Front-end packages pinned to established versions

**Problem.** The interface needs React, a router, a bundler, TypeScript and
pdf.js. In November 2026 several of these had brand-new major versions (React
19.3, react-router 8, Vite 8, TypeScript 7, pdf.js 6), some released days
earlier.

**Choice.** Exact versions from the previous major line, each released at least
two weeks earlier: React 19.2.9, react-router 7.18.5, Vite 7.3.7, TypeScript
5.9.3, pdf.js 5.7.284, Vitest 3.2.7. `package-lock.json` pins the rest. The
release build runs `npm ci`, so every release uses the same packages.

**Reason.** Known, stable APIs, and a short wait lets the community catch a
broken or compromised release before we ship it.

**How we'll know.** Upgrades happen on purpose, one major at a time, behind the
front-end tests.

---

## 2026-11-22: The Modern template uses the system's sans-serif font

**Problem.** Typst bundles serif fonts only. The Modern template needs a
sans-serif.

**Choice.** It asks for Segoe UI, then Calibri, then Arial, which Windows has;
elsewhere Typst falls back to a bundled serif. No font is downloaded or bundled
yet.

**How we'll know.** If students on other systems use Modern, bundle an
open-licensed sans-serif (for example Source Sans 3, OFL) with the package.

---

## 2026-11-21: Old repositories keep a pointer README, not archived

**Problem.** `opportunity-discovery` and `academic-planning` were separate
repositories. Their code now lives in `packages/`.

**Options.** Delete them; make them private; archive them (read-only); leave
only a pointer README.

**Choice.** Each keeps only a README pointing to its package here, plus its
license. Neither is archived. Opportunity Discovery's ruleset was disabled,
because its required checks came from the CI workflow that was removed.

**Reason.** Nothing should depend on the old code, and nobody uses the project
yet, so old deep links don't matter. A pointer still tells a visitor where the
project went.

**How we'll know.** Nothing outside this repository refers to the old code
paths.

---

## 2026-11-20: The resume studio typesets with Typst, not LaTeX

**Problem.** The studio recompiles the resume after every edit, and its
click-to-edit preview needs to know where each bullet landed on the page. The
existing template is LaTeX (Jake's Resume, compiled with Tectonic).

**Options.** Tectonic with LaTeX templates; Typst through its Python package
(`typst`).

**Measured** on one machine (Intel Core Ultra 5 335, Windows) with a synthetic
one-page resume in both systems:

| | Tectonic 0.17.0 | Typst 0.15.2 |
| --- | --- | --- |
| Recompile after one edit | 563 ms | 9.8 ms (compiler kept running) |
| First run on a new machine | 62.8 s, downloads 41.7 MB | 111 ms, no download |
| Peak memory | 192 MB | 37 MB (whole Python process) |
| Bullet positions for click-to-edit | would need extra LaTeX markers | built-in query, 0.1 ms |

Text extraction was also checked with three PDF readers. The LaTeX template's
PDF extracted "efficient" and "office" with a ligature character, so a plain
search for those words fails. Typst's PDF extracted them as plain letters.
Hostile input (Typst markup typed into a bullet) rendered as text and never
ran. Accented, Greek and Cyrillic names worked with Typst's bundled fonts;
Chinese, Japanese and Korean names and emoji need system fonts.

**Choice.** Typst. The templates (Jake-style, Classic, Modern) are written for
this project and render from the same data.

**Reason.** Edits feel instant, there's nothing extra to install, and position
queries make click-to-edit simple. Exact copies of Jake's or Harvard's
templates aren't required, only the overall look.

**Costs.** Exports are `.typ` and `.pdf`, so they can't be opened in Overleaf
(typst.app is the online editor for `.typ`). Typst is still pre-1.0, so the
`typst` package version is pinned and upgraded behind tests.

**How we'll know.** Edits show in the preview without a noticeable wait, and
exported PDFs pass the studio's parse check.

---

## 2026-11-20: The studio stores resumes in SQLite

**Problem.** A resume has entries, bullets, variants, versions, evidence links
and an order, and the interface writes many small changes.

**Options.** Files (YAML or JSON); SQLite; Postgres.

**Choice.** SQLite through Python's `sqlite3`, with numbered SQL migrations
(the pattern Opportunity Discovery already uses). Bullets live in a shared
library that each application's resume selects from and can override. Exports
(`.typ` and `.pdf`) stay files, with their hashes recorded.

**Reason.** The data is relational and written by one user and one process.
Postgres would add a server to install, start, back up and upgrade on every
laptop, and embedded Postgres packages found so far don't support Python 3.14.
The existing backup code already copies SQLite safely.

**How we'll know.** Structural edits never need a file to be hand-edited, and
backups restore studio data.

---

## 2026-11-20: Two earlier rules dropped

**Problem.** "Files are the source of truth" and "students install only
Python" were limiting the studio's design.

**Choice.** Both are dropped. A database and bundled dependencies are fine
where a feature needs them. Still in force: everything runs locally, nothing is
sent or submitted for the student, and the student's own AI agent does the AI
work.

**How we'll know.** New dependencies each come with a feature that needs them.

---

## 2026-11-20: Studio scope for resume screening (ATS)

**Problem.** Students worry about applicant tracking systems.

**What we found.** These systems mostly parse the text into fields for
recruiter search and form autofill. Automatic rejection is mostly knockout
questions (work authorization, location), and no standard "ATS score" exists.
Parsers struggle with columns, tables, text boxes and unusual headings.

**Choice.** A parse check of the compiled PDF (one page, readable text,
standard headings in order, links, nothing past the margins), plus keyword
coverage against the posting, with each term linked to evidence. No score.

**How we'll know.** Exported resumes pass the parse check, and coverage shows
gaps a student can fix honestly.

---

## 2026-11-20: Editing in the studio is direct, not by AI

**Problem.** In one AI-assisted resume session, about 15 small structural edits
each took an AI turn and a recompile, and final edits made in Overleaf left the
LaTeX source and the PDF out of sync.

**Choice.** The student edits the resume directly: click a bullet in the PDF or
the list, type, reorder, hide, pick a variant. Template settings cover spacing
and size. A rare raw override exists per bullet. "Ask the AI" works on one
section through the existing application handoff and returns variants to pick
from. There's no separate full-source editing mode; Export writes the source
and the PDF.

**How we'll know.** A tailored resume can be edited without AI turns, and
recompiling the exported Typst source reproduces the exported PDF in the benchmark.

---

## 2026-11-20: Local AI models are not used yet

**Problem.** A local model could draft bullet variants without an agent.

**Choice.** Not in Phase 1. Small local models write fluent text but are least
reliable at what the resume work needs most: keeping a claim's scope (for
example "on one recorded talk", "in simulation"). Students bring their own
agent. Local embeddings may come with the lab finder.

**How we'll know.** Revisit with a measured benchmark on real bullets before
adding a local model.

---

## 2026-11-20: One repository, separate packages

**Problem.** Releases already shipped as one tested set of three repositories,
so changes across them took three PRs and cross-repository CI pins.

**Choice.** `student-workspace` became the single repository (its name stays,
because installed copies update from its releases). The tools were imported
with their history into `packages/`. One CI workflow tests all packages, and one
release tag covers them; each package is still zipped and installed on its own.
Each package carries its own `.gitattributes`, and release archives are built
with `core.autocrlf` off, so every machine produces the same ZIPs.

**How we'll know.** A cross-cutting change is one PR with one CI run. Installs
from 2026.11.1 update cleanly (checked with a local test release).

---

## 2026-11-20: Earlier decisions, from the roadmap

- **FastAPI + React, introduced with the Application Studio.** The studio needs
  a live, editable interface; the existing pages didn't justify a rewrite on
  their own.
- **The app is organized by student task** (Home, Applications, Opportunities,
  Courses, Workspace). Students shouldn't need to know which tool does what.
- **Opportunities owns application status; Applications owns documents.** One
  source of truth for each piece of information; other sections change it only
  through the owner's API.
- **The lab finder is its own module,** linked to Opportunity Discovery through
  its export file: labs are lasting records with their own workflow.
- **Course research belongs in Academic Planning,** which already owns course
  decisions.
- **Combine repositories at the start of Phase 1** (done; see above).
- **Daily collection is off by default.** A scheduled task should be the
  student's choice.
