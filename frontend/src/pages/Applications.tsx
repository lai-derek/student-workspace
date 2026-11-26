import { useEffect, useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router";
import { api, type ResumeSummary } from "../api";
import { Button, Card, EmptyState, ErrorNote, Field } from "../kit";

type Start = "empty" | "tex" | "copy";

export default function Applications() {
  const navigate = useNavigate();
  const [resumes, setResumes] = useState<ResumeSummary[] | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);
  const [saving, setSaving] = useState(false);
  const [folder, setFolder] = useState("");
  const [name, setName] = useState("");
  const [template, setTemplate] = useState("jake");
  const [start, setStart] = useState<Start>("empty");
  const [tex, setTex] = useState("");
  const [copyFrom, setCopyFrom] = useState("");

  useEffect(() => {
    api.resumes().then(setResumes, (e: Error) => setLoadError(e.message));
  }, []);

  const slug = folder.trim().toLowerCase().replace(/[^a-z0-9._-]+/g, "-").replace(/^-+|-+$/g, "");

  async function readFile(input: HTMLInputElement) {
    const file = input.files?.[0];
    setTex("");
    setError(null);
    if (!file) return;
    try {
      const contents = await file.text();
      if (input.isConnected && input.files?.[0] === file) setTex(contents);
    } catch (e) {
      if (input.isConnected && input.files?.[0] === file) {
        setError(`Could not read the LaTeX file. ${(e as Error).message}`);
      }
    }
  }

  async function submit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    setSaving(true);
    try {
      const version = await api.createResume({
        application_folder: `applications/${slug}`,
        name: name || "Your Name",
        template,
        tex: start === "tex" ? tex : undefined,
        copy_from: start === "copy" ? copyFrom : undefined,
      });
      navigate(`/applications/${version.id}`);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setSaving(false);
    }
  }

  return (
    <>
      <h1>Applications</h1>
      <ErrorNote error={error} onClose={() => setError(null)} />
      <Card
        title="Resumes"
        actions={
          <Button variant="primary" disabled={saving} onClick={() => {
            setTex("");
            setError(null);
            setCreating(!creating);
          }}>
            {creating ? "Cancel" : "New resume"}
          </Button>
        }
      >
        {creating && (
          <form onSubmit={submit} className="card" style={{ background: "#fafbfc" }}>
            <Field label="Application name" hint={slug ? `Folder: applications/${slug}` : "For example, Summer research internship"}>
              <input type="text" value={folder} onChange={(e) => setFolder(e.target.value)} required />
            </Field>
            <div className="row">
              <Field label="Start from">
                <select value={start} onChange={(e) => {
                  setTex("");
                  setStart(e.target.value as Start);
                }}>
                  <option value="empty">Blank resume</option>
                  <option value="copy" disabled={!resumes?.length}>
                    Copy an existing resume
                  </option>
                  <option value="tex">Import a LaTeX resume (Jake's style)</option>
                </select>
              </Field>
              {start !== "copy" && (
                <Field label="Template">
                  <select value={template} onChange={(e) => setTemplate(e.target.value)}>
                    <option value="jake">Jake-style</option>
                    <option value="classic">Classic (Harvard-style)</option>
                    <option value="modern">Modern</option>
                  </select>
                </Field>
              )}
            </div>
            {start === "tex" && (
              <Field
                label=".tex file"
                hint="Studio uses this file to import your resume content. Previews and exports use Typst."
              >
                <input type="file" accept=".tex,text/plain" required onChange={(e) => readFile(e.currentTarget)} />
              </Field>
            )}
            {start === "copy" && (
              <Field label="Resume to copy" hint="The new resume starts with the same template and layout.">
                <select value={copyFrom} onChange={(e) => setCopyFrom(e.target.value)} required>
                  <option value="">Choose…</option>
                  {resumes?.flatMap((r) =>
                    r.versions.map((v) => (
                      <option key={v.id} value={v.id}>
                        {r.application_folder.replace("applications/", "")} · {v.name}
                      </option>
                    )),
                  )}
                </select>
              </Field>
            )}
            {start === "empty" && (
              <Field label="Your name">
                <input type="text" value={name} onChange={(e) => setName(e.target.value)} required />
              </Field>
            )}
            <Button variant="primary" type="submit" disabled={saving || !slug || (start === "tex" && !tex)}>
              {saving ? "Creating…" : "Create resume"}
            </Button>
          </form>
        )}
        {loadError ? (
          <ErrorNote error={`Could not load resumes. ${loadError}`} />
        ) : resumes === null ? (
          <p className="muted">Loading resumes…</p>
        ) : resumes.length === 0 ? (
          creating ? null : <EmptyState title="No resumes yet" />
        ) : (
          <table className="terms">
            <thead>
              <tr>
                <th>Application</th>
                <th>Latest version</th>
                <th>Exported</th>
              </tr>
            </thead>
            <tbody>
              {resumes.map((r) => (
                <tr key={r.id}>
                  <td>
                    <Link to={`/applications/${r.versions[0].id}`}>{r.application_folder.replace("applications/", "")}</Link>
                  </td>
                  <td>{r.versions[0].name}</td>
                  <td className="muted">{r.versions[0].exported_at ? r.versions[0].exported_at.slice(0, 10) : "not yet"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Card>
    </>
  );
}
