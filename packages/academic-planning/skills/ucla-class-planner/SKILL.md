---
name: ucla-class-planner
description: Inspect and manage saved UCLA MyUCLA Class Planner plans through an authenticated browser, with read-back verification. Use for requested plan creation or edits; excludes enrollment.
---

# UCLA Class Planner

Manage saved plans at https://be.my.ucla.edu/ClassPlanner/ClassPlan.aspx within the user's requested scope. Accept exact courses and components from an exported schedule or a sufficiently specified user request. Do not redesign an approved course mix during entry. When an actual section choice is missing, resolve it using current official information or the scheduling workflow before writing.

Use available supported browser tools and their current documentation. Prefer an existing authenticated tab; inventory tabs before opening a separate login session. Let the user handle authentication when necessary. Current page state governs selectors and actions.

Read [browser procedure](references/browser.md) for the known search, linking, copying and save behavior. These are observed interface quirks, not permanent selectors.

Before mutation, inspect the term, existing plan names, active plan and primary designation. Preserve unrelated plans and the primary designation unless instructed otherwise. Inspect state after uncertain outcomes before retrying, so retries do not create duplicate courses or plans. Stop dependent mutations if an unexpected term, ambiguous plan identity or persistent save failure makes the target uncertain; report the concrete unresolved action.

After each affected plan is saved, reload it and read the course components and units from the UI independently of the expected input. Verify section IDs from visible details/links when the summary omits IDs. Do not copy expected IDs into an observation without verifying them. Produce separate observations for every affected plan.

If the scheduling module is available, use its `receipt` command to compare observations with stored plans; see the [receipt contract](../plan-course-schedules/references/interface.md#planner-observation). Otherwise report expected versus observed differences directly. A receipt is an agent-reported observation, not independently authenticated browser evidence. Keep screenshots or other evidence references when useful.

Report verified successes and incomplete actions separately. Saved plans never imply enrollment or academic-record assignments. Actual enrollment is outside this skill. Do not select Enroll while managing saved plans.
