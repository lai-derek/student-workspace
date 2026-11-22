# Academic Planning

Planning UCLA courses means cross-checking a degree audit, transfer and AP
credit, and each quarter's section times. Academic Planning keeps those records
together in your private student workspace and works with your AI agent (Claude
Code or Codex) to plan terms and build ranked section schedules. It generates an
Excel planner, an advising PDF and a readable academic record. It never enrolls
you or changes MyUCLA on its own.

## Install

Academic Planning installs with [Student Workspace](https://github.com/lai-derek/student-workspace).
You need Windows, Python 3.14 or newer (setup can install it), and an AI agent
that can read files, run commands and browse the web.

1. Download [Student-Tools-Setup.zip](https://github.com/lai-derek/student-workspace/releases/latest/download/Student-Tools-Setup.zip), extract it and run `Install.cmd`.
2. Choose Academic Planning in the wizard.

To update, download the latest setup ZIP and run it on the same workspace.

## Use

Open your workspace in your AI agent. To start, give it your degree audit (DARS)
and ask it to set up your academic records. It saves the original audit, shows
you what it read and what's unclear, and adds the records only after you've
reviewed them. After that, ask things like "plan winter" or "build me a
schedule".

The generated files are in `artifacts/academic-planning/`:
`Academic-Planner.xlsx`, `Academic-Advising.pdf` and `Current-Academic-Record.md`
(plus `Abroad-Brief.pdf` if you plan study abroad). To see what they look like
first, open the [sample outputs](examples/) made from a fictional student.

More: [record formats](docs/records.md) (mostly for your agent),
[how it fits the workspace](docs/integration.md), [validation](VALIDATION.md).

## License

MIT; see [LICENSE](LICENSE) and [NOTICE.md](NOTICE.md).
