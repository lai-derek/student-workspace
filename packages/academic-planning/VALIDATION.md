# Validation

Version 0.3.1, checked 2026-11-17 on native Windows 11 with Python 3.15.2.
0.3.1 adds `check --summary`, a one-line result that `student-workspace check`
shows instead of the JSON that agents read.

- `python -m unittest discover -s tests`: 89 tests passed.
- GitHub CI (0.3.0): Windows 3.14 and 3.15, Ubuntu 3.15 passed.
- Installed from the published 2026.11.0 release (0.3.0) alone, with
  Opportunity Discovery, and through the visible setup wizard: setup created the
  records, `INTAKE.md`, the skill pointers and the WORKSPACE.md section;
  `student-workspace check` exited 0; the README's `demo` command built all
  four files.
- Local 0.3.1 test release: `student-workspace check` shows one line ("0
  requirements, 0 planned courses; outputs not built yet"), and the tests check
  the line for stale outputs.
- The synthetic example in `examples/workspace/` was generated with `demo`
  (0.3.0; 0.3.1 changes no outputs).

Not verified yet: other operating systems and live MyUCLA operation (tests
never use a real browser session).
