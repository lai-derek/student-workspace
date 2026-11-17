# Student Workspace

A private folder on your computer where your AI agent (Claude Code or Codex) and
a few local tools work with your own material: resumes, transcripts, notes and
applications. Student Workspace sets up the folder, installs and updates the
tools, keeps a record of the evidence you save, makes backups, and provides
skills your agent uses to write applications. Nothing here calls an AI service;
your own agent does that work.

Tools you can install with it:

- [Opportunity Discovery](https://github.com/lai-derek/opportunity-discovery): collect and screen internships, programs and events, with a local dashboard.
- [Academic Planning](https://github.com/lai-derek/academic-planning): UCLA course plans and section schedules.

## Install (Windows)

You need Python 3.14 or newer (3.15 recommended). If setup can't find it, it
offers to install it with winget and asks first.

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

Exit code 0 means everything is current, 2 means something needs a refresh (the
output names the tool), and 1 is an error to fix.

## Update or add tools

Download the latest `Student-Tools-Setup.zip` again and run `Install.cmd` on
the same folder. Setup backs up the workspace first, replaces only `tools/`, and
puts the previous tools back if anything fails. It keeps the three most recent
of these automatic backups in `.student-workspace\backups\`. From PowerShell in
the workspace folder, `.\tools\.venv\Scripts\student-workspace.exe update .`
does the same without the wizard, and does nothing if you're already current.

More: [backup and recovery](docs/recovery.md),
[application handoffs](docs/applications.md),
[troubleshooting](docs/troubleshooting.md), [validation](VALIDATION.md).

MIT license; see [LICENSE](LICENSE).
