# Application Studio benchmarks

`scripts/benchmark_studio.py` measures how long structural edits take without
AI and whether the exported Typst source reproduces the PDF. Run it from the
repository with the core package installed:

```powershell
python scripts/benchmark_studio.py --edits 300 --output report.md
python scripts/benchmark_studio.py --tex path\to\resume.tex   # your own Jake's-style resume
```

It starts the real server on 127.0.0.1 in a throwaway workspace, imports a
resume, and sends requests over HTTP the way the browser does. Each "edit" below
is the change request plus the preview the interface loads afterwards.

## Results, 2026-11-22

Windows 11, Intel Core Ultra 5 335, Python 3.15.2, Typst 0.15.2.

| | Synthetic test resume (4 entries, 4 bullets) | A real one-page resume (7 entries, 12 bullets) |
| --- | --- | --- |
| 15 structural edits | 0 AI turns, 298 ms in total | 0 AI turns, 371 ms in total |
| One edit, median (change + new preview) | 20.7 ms | 26.6 ms |
| Exported PDF reproduced from its source | yes, byte for byte | yes, byte for byte |
| Parse check | ok | ok |
| 300 edits in a row: median / p95 / max | 22.0 / 24.3 / 108.7 ms | 26.7 / 30.4 / 118.7 ms |
| Server memory across those 300 edits | 110.2 → 110.5 MB | 121.2 → 121.6 MB |

The real resume is the one from the AI-assisted editing session that motivated the studio.
Only its counts and timings are recorded here. It imported from LaTeX with
every word intact (442 words before and after), and its edits were the kinds
that each took an AI turn in that session: moving and hiding bullets, rewording,
picking a variant, and tightening spacing to fit the page.

### Where the time goes (real resume)

| Operation | Time |
| --- | --- |
| Typst compile after an edit, median / p95 (Jake-style; Classic and Modern within 1 ms) | 8.4 / 10.2 ms |
| Typst first compile of a template | 53–67 ms |
| Change request (save to SQLite, return the updated resume) | 10–14 ms |
| Preview request (compile, find bullet positions, send the PDF) | 14–16 ms |
| Import the LaTeX resume | 89 ms |
| Export (.typ + .pdf) | 114 ms |
| Verify an export (recompile from disk and compare) | 61 ms |
| Screening checks (parse check + keyword coverage) | 56 ms |

A preview response is about 61 KB (the PDF plus bullet positions); the exported
PDF is 45 KB.

### Measured separately

- Starting `student-workspace serve` until it prints its link: about 960 ms,
  mostly loading Python packages. The first preview after that took 71–75 ms in
  two runs.
- In the browser, the first preview after opening the studio showed 1.7 s while
  the page was still loading its scripts and pdf.js; every later edit showed
  about 18 ms there.
- The occasional slow edit (max about 110 ms of 300) did not grow over the run.

Results come from one computer. Typst against LaTeX is in
[decisions.md](decisions.md#2026-11-20-the-resume-studio-typesets-with-typst-not-latex).
