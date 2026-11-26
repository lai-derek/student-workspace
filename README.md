# Student Workspace

A private folder on your computer where your AI agent (Claude Code or Codex) and
a few local tools work with your own material: resumes, transcripts, notes and
applications. Student Workspace sets up the folder, installs and updates the
tools, keeps track of the documents you save, makes backups, and gives your
agent instructions for writing applications. You bring the AI agent; the tools
run locally.

Tools you can install with it:

- [Opportunity Discovery](packages/opportunity-discovery): collect and rank internships, research positions, programs and events, with a local dashboard.
- [Academic Planning](packages/academic-planning): UCLA course plans and section schedules.

## Install (Windows)

You need Python 3.14 or newer (3.15 recommended). If setup can't find Python,
it offers to install it with winget. Bring an agent that can read files and run
commands for application drafts and planning.

1. Download [Student-Tools-Setup.zip](https://github.com/lai-derek/student-workspace/releases/latest/download/Student-Tools-Setup.zip) and extract it (right-click, Extract All).
2. In the extracted folder, double-click `Install.cmd`.
3. In the wizard, choose a folder (default `Documents\Student Workspace`) and the
   tools you want. Select **Open folder** on the last page to find your workspace.

Your files stay in that folder. The installed tool code goes in its `tools/`
subfolder.

## Use

With the released setup (2026.11.1), open the workspace folder in your AI agent
and ask it to help you draft an application. Each installed tool adds its own
requests, such as "find internships for me" with
Opportunity Discovery or "plan winter" with Academic Planning. The generated
`WORKSPACE.md` tells the agent how the folder and tools work.

To check the setup from PowerShell in the workspace folder:

```powershell
.\tools\.venv\Scripts\student-workspace.exe check .
```

It prints `workspace check: current` when all is well. Otherwise it names the
tool that needs attention and what to do.

## Try Application Studio from source

The Studio is available from the source checkout. With Python 3.15 and Node.js
24 installed, open PowerShell in the repository and run:

```powershell
py -3.15 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e packages/student-workspace
npm.cmd ci --prefix frontend
npm.cmd run build --prefix frontend
```

After the build succeeds, start the app with a new demo workspace:

```powershell
$demo = Join-Path $env:TEMP ("student-workspace-demo-" + [guid]::NewGuid())
.\.venv\Scripts\student-workspace.exe init $demo
.\.venv\Scripts\student-workspace.exe serve $demo
```

Keep the PowerShell window open while using the app. In **Applications**,
select **New resume**. Start with a blank resume or import a Jake-style LaTeX
file. Double-click bullets in the preview to edit them. **Export .typ + .pdf**
writes Typst source and a PDF to the application folder. **Screening checks**
checks PDF readability and highlights the job posting terms your resume covers.

To ask your own agent for alternatives, use **Agent handoff**. Give it the
saved `HANDOFF.md`, then refresh the request list and import its variants.

## Update or add tools

Download the latest `Student-Tools-Setup.zip` again and run `Install.cmd` on
the same folder. Setup backs up the workspace before updating the installed
tools and restores the previous tools if the update fails.

More: [backup and recovery](packages/student-workspace/docs/recovery.md),
[application drafts](packages/student-workspace/docs/applications.md),
[troubleshooting](packages/student-workspace/docs/troubleshooting.md) (including updating from PowerShell),
[validation](packages/student-workspace/VALIDATION.md).

## Repository layout

Each tool is its own Python package, installed only if the student chooses it:

- `packages/student-workspace/`: the core (setup, workspace state, backups, application handoffs, shared skills) and the setup wizard in `installer/`.
- `packages/opportunity-discovery/`, `packages/academic-planning/`: the tools.
- `scripts/build_release.py`: builds one tested release of all packages.

MIT license; see [LICENSE](LICENSE).
