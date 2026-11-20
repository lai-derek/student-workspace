# Verification

Run `python -m unittest discover -s tests -v` in an environment with
`.[test]` and student-workspace installed. All fixtures are synthetic and
disposable; tests never operate MyUCLA or enroll.

Core checks reopen workbook and PDF outputs, reconcile current and historical
credit, distinguish assignments, proposals and current work, validate source
hashes and administrative evidence, and protect independently edited outputs.
Scheduling tests cover ranking, conflicts, linked components, travel, receipts,
SQLite transactions and backups, and compare random schedules with an exhaustive
oracle. Coverage and configuration regressions exercise empty, partial and
complete records. `tests/test_tool.py` registers the tool in a fresh Student
Workspace and checks setup, skill pointers and the workspace-wide check.
