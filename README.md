# Student Workspace

A private folder on your computer where your AI agent (Claude Code or Codex) and
a few local tools work with your own material: resumes, transcripts, notes and
applications. Student Workspace sets up the folder, installs and updates the
tools, keeps track of the documents you save, makes backups, and gives your
agent instructions for writing applications. You bring the AI agent; the tools
run locally.

Tools you can install with it:

- [Opportunity Discovery](https://github.com/lai-derek/opportunity-discovery): collect and rank internships, research positions, programs and events, with a local dashboard.
- [Academic Planning](https://github.com/lai-derek/academic-planning): UCLA course plans and section schedules.

## Install (Windows)

You need Python 3.14 or newer (3.15 recommended) and an AI agent that can read
files and run commands. If setup can't find Python, it offers to install it with
winget and asks first.

1. Download [Student-Tools-Setup.zip](https://github.com/lai-derek/student-workspace/releases/latest/download/Student-Tools-Setup.zip) and extract it (right-click, Extract All).
2. In the extracted folder, double-click `Install.cmd`. Windows may ask once
   about an unverified publisher.
3. In the wizard, choose a folder (default `Documents\Student Workspace`) and the
   tools you want. The last page can open the folder for you.

Your files stay in that folder. The installed tool code goes in its `tools/`
subfolder.

On Linux, run `python install.py` from the extracted folder for the same wizard
(needs `python3-tk`). Only Windows has been tested.

## Use

Open the workspace folder in your AI agent and ask it to get you started, for
example "add my resume" or "help me draft this application". Each installed tool
adds its own requests, such as "find internships for me" with Opportunity
Discovery or "plan winter" with Academic Planning. The generated `WORKSPACE.md`
tells the agent how the folder and tools work.

To check that everything is set up correctly, open PowerShell in the workspace
folder and run:

```powershell
.\tools\.venv\Scripts\student-workspace.exe check .
```

It prints `workspace check: current` when all is well. Otherwise it names the
tool that needs attention and what to do.

## Update or add tools

Download the latest `Student-Tools-Setup.zip` again and run `Install.cmd` on
the same folder. Setup backs up the workspace first, replaces only `tools/`, and
puts the previous tools back if anything fails.

More: [backup and recovery](docs/recovery.md),
[application drafts](docs/applications.md),
[troubleshooting](docs/troubleshooting.md) (including updating from PowerShell),
[validation](VALIDATION.md).

MIT license; see [LICENSE](LICENSE).
