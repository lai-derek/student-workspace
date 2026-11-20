# Security & privacy

## Posture

- **Local-only**: collector SQLite + files under `data/`, `output/`, `logs/`;
  private workspace commands are also shipped here. Keep their runtime state
  outside the Git checkout.
- **No credentials**: no API keys, no logins, nothing authenticated. If a
  source requires an Authorization-Key (e.g. USAJOBS), it is out of scope.
- **No AI/model dependencies** and no telemetry.
- **No submissions**: the engine never applies, messages, uploads, or saves
  anything to any service.
- **Selected workspace**: workspace commands take an explicit workspace root
  and never copy private state into public exports. The collector database and
  exports for a workspace live in its `.student-workspace/opportunity-discovery/`
  folder. Screening refuses to write when private state is tracked by Git; a
  workspace that merely sits inside a Git folder gets a warning from
  `student-workspace audit` instead.
- **Bounded public HTTP**: remote URLs must use HTTP(S), may not embed
  credentials, resolve only to public addresses, and are revalidated at each
  redirect. Redirect count and response body size are capped. Program-page
  redirects are additionally confined to the exact configured host set.

## What is never stored

Collector SQLite and public outputs never store personal data: applicant
profiles, eligibility decisions, resumes/transcripts/essays, application
history or outcomes, or demographic data. The engine stores only what public
sources state about opportunities. A selected private workspace may contain
private user material and decisions by design. Its files must be kept out of any
published Git checkout; `student-workspace audit` reports tracked private files.
Backups and restore are provided by student-workspace.
Knowledge history operations reject symlinks in every path component, and the
workspace audit treats manifested symlinked or out-of-sources files as errors.
These checks do not provide encryption or access control.

## Git hygiene

Committed content is limited to code, config templates, the public registry,
schemas, fixtures, docs, tests, and safe scripts. `.gitignore` excludes
`data/`, `output/`, `logs/`, databases/journals, caches, virtualenvs, `.env`,
keys. Generated live data must never be tracked.

## Publication audit

`opdisc audit` (or `.venv/bin/python -m opportunity_discovery.audit`) scans
tracked files for:

- common credential patterns (AWS/GitHub/Slack/Google/OpenAI keys, generic
  secret assignments, private-key blocks, connection strings);
- `.env` / key / certificate files;
- Windows user paths (`C:\Users\…`), WSL user mounts (`/mnt/c/Users/…`),
  absolute `/home/<user>/` paths;
- databases, logs, caches, live payloads in generated directories;
- obvious personal application data (resume/cv/transcript filenames,
  application-status language) as warnings.

It exits non-zero on errors. Run it before every push/publish.

`student-workspace audit WORKSPACE` is separate. It checks whether the private
workspace is inside Git, reports every tracked private file, and verifies
preserved source paths, hashes and references.

### Limitations (documented honestly)

- Pattern-based: novel secret formats can slip through; high-entropy scanning
  is deliberately conservative to avoid false positives.
- Only scans textual files; binary payloads are caught by filename/suffix
  rules only.
- No path is exempt: the rules apply to `tests/` and `examples/` like every
  other tracked file. Tests that need detection-shaped values construct them
  from runtime fragments, so a real credential or machine path committed under
  those trees is still flagged (regression-tested).
- It inspects the working tree/tracked files at scan time; it cannot vouch for
  history already pushed elsewhere.
