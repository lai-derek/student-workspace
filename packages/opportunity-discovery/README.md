# Opportunity Discovery

Internship, research, program and event listings are spread across hundreds of
company job boards and community lists. Opportunity Discovery collects them in
one place, tracks what changed, ranks them against your interests, and lets you
review leads and track applications in a local dashboard. It's meant for
undergraduate students. Your own AI agent (Claude Code or Codex) builds your
profile, looks into promising leads and helps with drafts; the app runs locally
and never submits anything for you.

## Install

Opportunity Discovery installs with [Student Workspace](https://github.com/lai-derek/student-workspace).
You need Windows, Python 3.14 or newer (setup can install it), and an AI agent
that can read files, run commands and browse the web.

1. Download [Student-Tools-Setup.zip](https://github.com/lai-derek/student-workspace/releases/latest/download/Student-Tools-Setup.zip), extract it and run `Install.cmd`.
2. Choose Opportunity Discovery in the wizard. You can also turn on daily
   collection at 7:30 a.m.; it's off unless you check it.
3. Follow [set up your profile and first recommendations](docs/AI_SETUP.md).
   The first collection takes about 10 minutes.

To update, download the latest setup ZIP and run it on the same workspace.

## Use

Double-click **Open Dashboard.cmd** in your workspace. **Home** shows the
opportunities your AI has reviewed and recommends; **Explore** lets you search
every collected lead. Mark items done or hide them as you go.

To refresh recommendations, close the dashboard and send the step 2 prompt from
the [setup guide](docs/AI_SETUP.md) again. For help with an application, open
the opportunity's **Application preparation** section and give the resulting
request to your AI.

## More

- [Collection on Windows](docs/OPERATIONS_WINDOWS.md): where data lives, manual and daily runs.
- [Troubleshooting](docs/TROUBLESHOOTING.md).
- [Review commands](docs/PRIVATE_WORKSPACE_OPERATIONS.md) and [integration contract](docs/INTEGRATION_CONTRACT.md), mostly for your AI agent.
- [Architecture](docs/ARCHITECTURE.md), [data model](docs/DATA_MODEL.md), [adapters](docs/ADAPTERS.md).
- Contributors: read `AGENTS.md`; current checks are in [docs/VALIDATION.md](docs/VALIDATION.md).

MIT license; see [LICENSE](LICENSE).
