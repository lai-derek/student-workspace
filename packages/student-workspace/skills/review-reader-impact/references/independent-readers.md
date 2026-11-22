# Independent readers for substantial writing

When the main skill calls for independent readers and there is time to act on their feedback, use two fresh agents with no inherited conversation (Codex: `fork_turns="none"`; Claude Code: two `Agent` calls with `subagent_type: "general-purpose"`, never `"fork"`, sent in the same message so they run in parallel). Give each the same bounded recipient-facing packet: draft, prompts, limits, audience, and relevant published program or role information. Do not send the authoring conversation, private evidence, preferred conclusions, suspected flaws, full workspace, or irrelevant skills. Readers neither confer nor see each other's findings.

- **Audience reader:** What does the recipient understand and remember about this person? What gives them reason to select, trust, or respond? Where do attention and comprehension weaken?
- **Critical reader:** Which passages have weak on-page support, interchangeable language, structural problems, or unearned conclusions? Across the packet, what repeats and what does each answer add?

Ask for initial reactions and specific passages before proposed fixes. Reports should prioritize consequential findings and remain proportionate; readers need not rewrite the draft or produce exhaustive line edits. They assess what the text communicates, not whether hidden evidence proves a claim, and do not invent an unpublished rubric.

The parent editor consults private evidence afterward, resolves consequential findings in the draft, and revises once. For packet reviews, check what each answer adds to the overall impression without demanding one repeated theme. Do not rerun readers merely to approve routine sentence edits; follow the main skill's material-change threshold.
