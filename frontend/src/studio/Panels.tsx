// Studio side panels for screening checks, agent handoffs, and the header and skills.
import { useCallback, useEffect, useState } from "react";
import { api, type Checks, type Contact, type HandoffRequest, type SkillLine, type Version } from "../api";
import { Badge, Button, ErrorNote, Field } from "../kit";
import type { Run } from "./Outline";

export function ChecksPanel({ version, run }: { version: Version; run: Run }) {
  const [checks, setChecks] = useState<Checks | null>(null);
  const [posting, setPosting] = useState(version.posting_text);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(() => {
    setLoading(true);
    setError(null);
    api
      .checks(version.id)
      .then(setChecks, (e: Error) => setError(e.message))
      .finally(() => setLoading(false));
  }, [version.id]);

  useEffect(load, [load, version.updated_at]);

  return (
    <div>
      <div className="row" style={{ marginBottom: 8 }}>
        <h3 className="grow" style={{ margin: 0 }}>
          PDF readability {checks && <Badge tone={checks.parse.result}>{checks.parse.result}</Badge>}
        </h3>
        <Button size="small" onClick={load} disabled={loading}>
          {loading ? "Checking…" : "Check again"}
        </Button>
      </div>
      <ErrorNote error={error && `Could not run screening checks. ${error}`} />
      <ul className="findings">
        {checks?.parse.findings.map((f) => (
          <li key={f.code}>
            <Badge tone={f.level}>{f.level}</Badge> {f.message}
          </li>
        ))}
      </ul>
      <h3 style={{ marginTop: 16 }}>Posting keywords</h3>
      <Field label="Job posting text" hint="Paste the posting to see which of its terms your resume covers.">
        <textarea value={posting} onChange={(e) => setPosting(e.target.value)} style={{ minHeight: 100 }} />
      </Field>
      <Button size="small" onClick={() => run(() => api.setPosting(version.id, posting))}>
        Save posting
      </Button>
      {checks && checks.keywords.terms.length > 0 && (
        <>
          <p className="small">
            Covered {checks.keywords.covered} of {checks.keywords.terms.length} frequent terms. Add a term only where
            your evidence supports it.
          </p>
          <table className="terms small">
            <thead>
              <tr>
                <th>Term</th>
                <th>In posting</th>
                <th>In resume</th>
                <th>Evidence that mentions it</th>
              </tr>
            </thead>
            <tbody>
              {checks.keywords.terms.map((t) => (
                <tr key={t.term}>
                  <td>{t.term}</td>
                  <td>{t.count}×</td>
                  <td>{t.covered ? <Badge tone="ok">yes</Badge> : <Badge tone="warning">no</Badge>}</td>
                  <td className="muted">{t.evidence.map((e) => e.title).join("; ")}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
      )}
    </div>
  );
}

const requestStatus: Record<string, string> = {
  "awaiting-response": "Waiting for agent",
  "needs-input": "Agent needs input",
  "invalid-response": "Invalid response",
  drafted: "Ready to import",
};

export function AskAiPanel({ version, run }: { version: Version; run: Run }) {
  const [section, setSection] = useState(version.sections[0]?.id ?? "");
  const [text, setText] = useState("");
  const [requests, setRequests] = useState<HandoffRequest[] | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);

  const load = useCallback(() => {
    setError(null);
    return api.requests(version.id).then(setRequests, (e: Error) => setError(`Could not load requests. ${e.message}`));
  }, [version.id]);
  useEffect(() => { void load(); }, [load]);

  async function ask() {
    setCreating(true);
    setError(null);
    setMessage(null);
    try {
      const result = await api.askAi(version.id, section, text);
      setMessage(`Request saved. Give your agent ${result.request_path}/HANDOFF.md.`);
      setText("");
      await load();
    } catch (e) {
      setError(`Could not create a request. ${(e as Error).message}`);
    } finally {
      setCreating(false);
    }
  }

  async function importFrom(path: string) {
    await run(async () => {
      const result = await api.importVariants(version.id, path);
      const count = result.result.added;
      setMessage(`Imported ${count} ${count === 1 ? "variant" : "variants"}. Open a bullet in Edit to choose one.`);
      return result.version;
    });
    load();
  }

  return (
    <div>
      <p className="small muted">
        Save a request for one section, then give its <code>HANDOFF.md</code> to your agent. When it finishes, select
        Refresh requests and import the suggested wordings.
      </p>
      <ErrorNote error={error} />
      <Field label="Section">
        <select value={section} onChange={(e) => setSection(e.target.value)}>
          {version.sections.map((s) => (
            <option key={s.id} value={s.id}>
              {s.title}
            </option>
          ))}
        </select>
      </Field>
      <Field label="What should change?">
        <textarea
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder="Make the benchmark bullet more specific for a research engineering role"
        />
      </Field>
      <Button variant="primary" size="small" disabled={creating || !text.trim() || !section} onClick={ask}>
        {creating ? "Saving…" : "Save request"}
      </Button>
      {message && <p className="small" style={{ overflowWrap: "anywhere" }} role="status">{message}</p>}
      <h3 style={{ marginTop: 16 }}>Requests</h3>
      {requests?.length === 0 && <p className="muted small">No requests yet.</p>}
      {requests === null && !error && <p className="muted small">Loading requests…</p>}
      {requests?.map((r) => (
        <div className="small" key={r.request_id} style={{ padding: "4px 0" }}>
          <div className="row">
            <span className="grow">
              {r.section} <span className="muted">{r.created_at?.slice(0, 16).replace("T", " ")}</span>
            </span>
            <Badge tone={r.status === "drafted" ? "ok" : r.status.startsWith("invalid") ? "error" : "neutral"}>
              {r.status === "drafted" && r.imported_variants ? "Imported" : requestStatus[r.status] ?? r.status}
            </Badge>
            {r.status === "drafted" && (
              <Button size="small" onClick={() => importFrom(r.request_path)}>
                {r.imported_variants ? "Import again" : "Import variants"}
              </Button>
            )}
          </div>
          <code className="muted" style={{ overflowWrap: "anywhere" }}>{r.request_path}/HANDOFF.md</code>
        </div>
      ))}
      <Button size="small" variant="ghost" onClick={load}>
        Refresh requests
      </Button>
    </div>
  );
}

export function HeaderPanel({ version, run }: { version: Version; run: Run }) {
  const [name, setName] = useState(version.header.name);
  const [contact, setContact] = useState<Contact[]>(version.header.contact);
  const [skills, setSkills] = useState<SkillLine[]>(version.skills);

  const updateContact = (i: number, patch: Partial<Contact>) =>
    setContact(contact.map((c, j) => (j === i ? { ...c, ...patch } : c)));
  const updateSkill = (i: number, patch: Partial<SkillLine>) =>
    setSkills(skills.map((s, j) => (j === i ? { ...s, ...patch } : s)));

  return (
    <div>
      <Field label="Name">
        <input type="text" value={name} onChange={(e) => setName(e.target.value)} />
      </Field>
      <h3>Contact line</h3>
      {contact.map((c, i) => (
        <div className="row" key={i} style={{ marginBottom: 6 }}>
          <input type="text" value={c.text} placeholder="Shown text" onChange={(e) => updateContact(i, { text: e.target.value })} />
          <input
            type="text"
            value={c.url ?? ""}
            placeholder="Link (optional)"
            onChange={(e) => updateContact(i, { url: e.target.value || null })}
          />
          <Button size="small" variant="ghost" onClick={() => setContact(contact.filter((_, j) => j !== i))}>
            ×
          </Button>
        </div>
      ))}
      <Button size="small" onClick={() => setContact([...contact, { text: "", url: null }])}>
        + Contact item
      </Button>
      <div style={{ marginTop: 8 }}>
        <Button size="small" variant="primary" onClick={() => run(() => api.setHeader(version.id, { name, contact }))}>
          Save header
        </Button>
      </div>
      <h3 style={{ marginTop: 16 }}>Skills lines</h3>
      {skills.map((s, i) => (
        <div className="row" key={i} style={{ marginBottom: 6 }}>
          <input type="text" value={s.label} placeholder="Languages" style={{ maxWidth: 160 }} onChange={(e) => updateSkill(i, { label: e.target.value })} />
          <input type="text" value={s.value} placeholder="Python, C++, SQL" onChange={(e) => updateSkill(i, { value: e.target.value })} />
          <Button size="small" variant="ghost" onClick={() => setSkills(skills.filter((_, j) => j !== i))}>
            ×
          </Button>
        </div>
      ))}
      <Button size="small" onClick={() => setSkills([...skills, { label: "", value: "" }])}>
        + Skills line
      </Button>
      <div style={{ marginTop: 8 }}>
        <Button size="small" variant="primary" onClick={() => run(() => api.setSkills(version.id, skills))}>
          Save skills
        </Button>
      </div>
    </div>
  );
}
