# Application handoffs

A handoff is a request your AI agent works on: it creates a folder of
instructions for one application (a resume, cover letter, essay or short
answers). The agent drafts the material from your saved evidence, and a check
confirms that the result is complete before you use it. Nothing is submitted
for you.

Opportunity Discovery creates handoffs from its dashboard. For any other
application, create one yourself as shown below.

Open PowerShell in your workspace folder and set two variables:

```powershell
$workspace = (Get-Location).Path
$sw = ".\tools\.venv\Scripts\student-workspace.exe"
```

## Create a handoff

```powershell
& $sw apply request-url $workspace applications/example-program https://example.org/apply short-answer "Draft answers using my supplied prompts and evidence."
```

- `applications/example-program` is the folder for this application. Existing
  drafts and notes in it are kept.
- The URL is saved for reference only. It is not opened and nothing is checked
  against it.
- The kind of material is one of `resume`, `cover-letter`, `essay`,
  `short-answer`, `application-notes`, `interview-prep` or `other`.

The command prints the path of a new `requests/req_...` folder. Ask your agent
to follow the `HANDOFF.md` inside it. The agent saves drafts in that folder's
`drafts/` (later versions in `revisions/`) and writes `response.json` when it's
done.

## Check the result

Use the request path the command printed:

```powershell
& $sw apply check $workspace applications/example-program/requests/REQUEST_ID
```

The check makes no changes. It confirms that:
- the response is complete and its drafts exist;
- its evidence points to files below `sources/` or `knowledge/`, or to web
  pages (which aren't opened);
- links between your Markdown files work;
- the drafts fit any length limits.

It exits 0 when everything passes and 1 on errors. If a cited file changed after
the request, you get a warning rather than an error, since your notes can change
over time. The check confirms structure only; you still review the content
yourself.

### Length limits (optional)

To check word or character limits, have each answer saved as its own UTF-8
text file and add `checks.json` to the request folder. Paths are relative to
that folder:

```json
{
  "schema_version": "1.0",
  "fields": [
    {"path": "drafts/answer.txt", "max_words": 150, "max_characters": 1000}
  ],
  "custom": {}
}
```

Words are counted between spaces, and characters include line breaks.
Application portals sometimes count differently, so confirm with the portal's
own counter. Formats: [field checks](../schemas/application-checks.schema.json),
[check report](../schemas/application-check-report.schema.json).
