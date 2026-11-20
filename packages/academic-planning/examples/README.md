# Sample outputs

`workspace/` holds a fictional student's records, saved documents and generated
outputs. It is not a real transcript or course recommendation.

Open the [planner](workspace/artifacts/academic-planning/Academic-Planner.xlsx), [advising brief](workspace/artifacts/academic-planning/Academic-Advising.pdf), [abroad brief](workspace/artifacts/academic-planning/Abroad-Brief.pdf), or [readable record](workspace/artifacts/academic-planning/Current-Academic-Record.md).

To build a fresh copy after installing, run this from PowerShell in your
workspace folder. Each run needs a new folder, so this one includes the time:

```powershell
$demo = Join-Path $env:TEMP ("academic-demo-" + (Get-Date -Format "yyyyMMdd-HHmmss"))
.\tools\.venv\Scripts\academic-planning.exe --workspace $demo demo
```

The output lists the files it built in `$demo\artifacts\academic-planning`. If
you edit a generated file by hand, the next build stops instead of overwriting
your edit.
