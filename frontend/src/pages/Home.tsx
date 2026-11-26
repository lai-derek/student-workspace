import { useEffect, useState } from "react";
import { Link } from "react-router";
import { api, type ResumeSummary } from "../api";
import { Card, EmptyState, ErrorNote } from "../kit";

export default function Home() {
  const [resumes, setResumes] = useState<ResumeSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.resumes().then(setResumes, (e: Error) => setError(e.message));
  }, []);

  return (
    <>
      <h1>Home</h1>
      <Card title="Recent resumes" actions={<Link to="/applications">All applications</Link>}>
        {error ? (
          <ErrorNote error={`Could not load resumes. ${error}`} />
        ) : resumes === null ? (
          <p className="muted">Loading resumes…</p>
        ) : resumes.length === 0 ? (
          <EmptyState title="No resumes yet">
            <p>
              Create a resume in <Link to="/applications">Applications</Link>.
            </p>
          </EmptyState>
        ) : (
          <ul>
            {resumes.slice(0, 5).map((r) => (
              <li key={r.id}>
                <Link to={`/applications/${r.versions[0].id}`}>{r.application_folder.replace("applications/", "")}</Link>{" "}
                <span className="muted small">
                  {r.versions[0].name}
                  {r.versions[0].exported_at ? " · exported" : ""}
                </span>
              </li>
            ))}
          </ul>
        )}
      </Card>
      <Card title="Your workspace">
        <p>
          Your files stay in your workspace folder. Your AI agent works there too: see <code>WORKSPACE.md</code>. Check
          that every tool is set up in <Link to="/workspace">Workspace</Link>.
        </p>
      </Card>
    </>
  );
}
