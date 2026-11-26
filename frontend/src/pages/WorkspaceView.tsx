import { useCallback, useEffect, useState } from "react";
import { api, type WorkspaceStatus } from "../api";
import { Badge, Button, Card, ErrorNote } from "../kit";

const tone = { ok: "ok", current: "ok", stale: "warning", error: "error" } as const;

export default function WorkspaceView() {
  const [status, setStatus] = useState<WorkspaceStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(() => {
    setLoading(true);
    setError(null);
    api
      .workspace()
      .then(setStatus, (e: Error) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  useEffect(load, [load]);

  return (
    <>
      <h1>Workspace</h1>
      <ErrorNote error={error} />
      <Card
        title={
          <>
            Workspace check {status && <Badge tone={tone[status.status]}>{status.status}</Badge>}
          </>
        }
        actions={
          <Button onClick={load} disabled={loading}>
            {loading ? "Checking…" : "Check again"}
          </Button>
        }
      >
        {status ? (
          <>
            <p className="muted small">{status.root}</p>
            {status.findings.length > 0 && (
              <ul className="small">
                {status.findings.map((f) => (
                  <li key={f}>{f}</li>
                ))}
              </ul>
            )}
          </>
        ) : (
          <p className="muted">{loading ? "Running every tool's check (a few seconds)…" : ""}</p>
        )}
      </Card>
      {status?.tools.map((tool) => (
        <Card
          key={tool.name}
          title={
            <>
              {tool.name} <span className="muted">{tool.version}</span> <Badge tone={tone[tool.status]}>{tool.status}</Badge>
            </>
          }
        >
          {tool.detail.length ? (
            <pre className="small" style={{ whiteSpace: "pre-wrap", margin: 0 }}>
              {tool.detail.join("\n")}
            </pre>
          ) : (
            <p className="muted small">No messages.</p>
          )}
        </Card>
      ))}
    </>
  );
}
