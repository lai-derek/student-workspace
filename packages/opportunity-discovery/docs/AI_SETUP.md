# Set up your profile and first recommendations

Follow these steps after installing with the Student Workspace setup.
Open your Student Workspace folder as a project in your AI tool. It needs
access to files and local commands; reviewing opportunities also needs web access.
The included AGENTS.md and CLAUDE.md point to WORKSPACE.md. With another tool,
ask it to read WORKSPACE.md.

## 1. Add your information

Put a résumé, notes, project descriptions, or other useful files in `inbox/`.
You can also give your AI text, images, links, or files directly. Writing samples
are optional. Start with what you have.

Send this prompt:

> Read WORKSPACE.md and the current profile instructions in
> tools/opportunity-discovery/docs/PRIVATE_WORKSPACE_OPERATIONS.md. Organize my supplied material and inbox
> into a profile and catalog, preserving the originals. Use documented answers
> first; ask concise questions about missing information that affects screening,
> including study stage, major, graduation, interests, and available locations.
> Ask whether I want early programs, standard internships, or entry-level jobs,
> and whether short programs elsewhere are acceptable with covered travel.
> Research surrounding metropolitan regions for my cities unless I request a
> narrower boundary. Save and import my private screening preferences, then
> summarize the regions, settings, and unresolved questions. Keep unknown
> credentials unknown.

Your AI organizes the material in `sources/` and `knowledge/`.
Read `knowledge/PROFILE.md` to check what it understood.
`knowledge/CATALOG.md` points to useful supporting material.
You can customize WORKSPACE.md to suit how you want your AI to work.

The AI also saves your preferences (locations, interests and the kind of
opportunities you want) as settings the app uses to rank leads. Check its
summary and correct anything it got wrong. If you chose early programs, broadly
related exploratory programs stay visible even when fit is unclear.

To add something later, give it to your AI and ask it to update your profile
and catalog.

## 2. Get your first recommendations

Your board is the list of opportunities your AI has reviewed and recommends.
Send this prompt to create it:

> Read WORKSPACE.md and the current review instructions in
> tools/opportunity-discovery/docs/PRIVATE_WORKSPACE_OPERATIONS.md and
> INTEGRATION_CONTRACT.md beside it. Create my
> opportunity board: collect leads, screen the full collection, and investigate
> a recommended compact batch, including promising leads that need clarification.
> Reuse saved findings and documented profile answers. Prioritize new or changed
> leads, approaching deadlines, and stale useful findings. Interpret captured
> requirements when needed and check official pages before recommending action.
> Keep unresolved facts visible. Save and import your findings, confirm the import,
> then open the dashboard in its own window. Report source failures and coverage:
> screened, plausible, officially checked, awaiting investigation, and selected
> or deferred for later work.

Your AI needs web and command access to complete this step. The first
collection in a new workspace takes about 10 minutes before screening starts.

The dashboard has two views:

- **Home** shows opportunities your AI has reviewed that need your attention.
  It's empty until the first review is imported.
- **Explore** shows every collected lead, ranked against your screening profile.
  Leads your AI has checked on the official page are labeled separately from
  leads that were only screened. Large employers are capped so they don't
  crowd out everything else; use the filters to see more. Without a screening
  profile, Explore shows the general public list.

## 3. Open and use it afterward

On Windows, double-click **Open Dashboard.cmd** in your workspace.
Keep its window open while using the dashboard. Close it or press Ctrl+C to stop.
If the browser does not open, visit [the dashboard](http://127.0.0.1:8765/).

Use **Done** when no further action is needed, **Delete** to hide an unwanted
item, and **Restore** to bring either back.

Daily collection, if you turned it on in setup, adds new leads to Explore but
doesn't update Home; to turn it on later, see
[Collection on Windows](OPERATIONS_WINDOWS.md#daily-collection). To refresh
recommendations, stop the dashboard and send the step 2 prompt again. Ranking
runs locally; only the research your AI does uses your AI tool.

For application drafts, select an opportunity's **Application preparation**
section and describe what you want. Give the resulting HANDOFF.md to your AI.
Review drafts yourself before applying.

See [workspace operations](PRIVATE_WORKSPACE_OPERATIONS.md) for manual commands, or [troubleshooting](TROUBLESHOOTING.md) if a step fails.
