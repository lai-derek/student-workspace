# Observed UCLA planner behavior

Use only supported browser APIs and selectors grounded in the current page. Check term and plan identity before each sequence. These observations came from a prior working workflow and must be rechecked when the UI changes.

## Search and add

1. Select Search By → Class ID. Wait for the nine-digit Class ID field.
2. Fill the exact ID. The Go button may require a keyboard event after filling; pressing End triggered validation in the observed interface. Verify Go is enabled rather than repeatedly submitting.
3. Wait for the expected section result. Searching a discussion ID can return its parent lecture; expand it and verify the discussion link's class ID.
4. Select both the lecture and its linked discussion, or the required lab. Verify the combination matches the input.
5. Select “Add as Class … in your current plan” when shown. Other radio choices may add an alternate instead.
6. Select Add Class to Plan. Wait for the success panel and close it before the next search. Check that the course and components persisted in the plan.

## Create, copy and edit

- New Plan creates an empty plan. Rename may become available only after adding a course. Inspect the actual name-length limit and use short distinguishable labels.
- Save a Copy opens name/notes fields. Wait until the heading identifies the new copy before editing it.
- Remove a superseded course from the new copy before adding its replacement. A row's action menu may remove the whole course and its linked components; confirm the resulting state.
- Exact-ID search is often faster than Find More Sections, which can reset the search mode and expand all sections.
- Actions can save asynchronously. Wait for expected semantic state; avoid fixed sleeps and repeated clicks.

## Verify

Load each affected plan by exact name, confirm term, and inspect all expected components, units and absence of unintended duplicate courses. Reload before reporting success. Preserve original plans and primary designation unless requested otherwise. Record which plan was left open.

If a save is uncertain, inspect the plan list and content before retrying. If section IDs cannot be established, mark the observation incomplete rather than treating matching times as proof of section identity.
