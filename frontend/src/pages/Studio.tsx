// Application Studio: the outline on the left, the live PDF on the right.
// Every change goes to the server, which saves it and returns the updated version;
// the preview then recompiles (milliseconds with Typst) and redraws in place.
import { useCallback, useEffect, useRef, useState } from "react";
import { Link, useNavigate, useParams } from "react-router";
import { api, type Bullet, type Preview, type Settings, type Version } from "../api";
import { Badge, Button, ErrorNote, Meter, Toolbar } from "../kit";
import MarkupEditor from "../studio/MarkupEditor";
import Outline from "../studio/Outline";
import { AskAiPanel, ChecksPanel, HeaderPanel } from "../studio/Panels";
import PdfPreview from "../studio/PdfPreview";

type Tab = "edit" | "header" | "checks" | "ai";

function findBullet(version: Version, id: string): Bullet | undefined {
  for (const section of version.sections)
    for (const entry of section.entries) for (const bullet of entry.bullets) if (bullet.id === id) return bullet;
  return undefined;
}

function isEntry(version: Version, id: string) {
  return version.sections.some((s) => s.entries.some((e) => e.id === id));
}

const exportTone = {
  current: "ok",
  outdated: "warning",
  "not-exported": "neutral",
  "changed-outside": "error",
  missing: "warning",
} as const;
const exportLabel = {
  current: "Export up to date",
  outdated: "Edited since export",
  "not-exported": "Not exported",
  "changed-outside": "Export changed outside Studio",
  missing: "Export files missing",
} as const;

export default function Studio() {
  const { versionId = "" } = useParams();
  const navigate = useNavigate();
  const [version, setVersion] = useState<Version | null>(null);
  const [preview, setPreview] = useState<Preview | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const [editing, setEditing] = useState<string | null>(null);
  const [editingEntry, setEditingEntry] = useState<string | null>(null);
  const [tab, setTab] = useState<Tab>("edit");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [settings, setSettings] = useState<Settings | null>(null);
  const settingsTimer = useRef<number | undefined>(undefined);

  useEffect(() => {
    let active = true;
    setError(null);
    setVersion(null);
    setPreview(null);
    api.version(versionId).then(
      (v) => {
        if (!active) return;
        setVersion(v);
        setSettings(v.settings);
      },
      (e: Error) => {
        if (active) setError(e.message);
      },
    );
    return () => { active = false; };
  }, [versionId]);

  // Recompile the preview whenever the version changes; a newer request cancels an older one.
  useEffect(() => {
    if (!version) return;
    const controller = new AbortController();
    api.preview(version.id, controller.signal).then(
      setPreview,
      (e: Error) => {
        if (e.name !== "AbortError") setError(e.message);
      },
    );
    return () => controller.abort();
  }, [version?.id, version?.updated_at, version?.template]); // eslint-disable-line react-hooks/exhaustive-deps

  const run = useCallback(async (action: () => Promise<Version>) => {
    setBusy(true);
    setError(null);
    try {
      const next = await action();
      setVersion(next);
      setSettings(next.settings);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }, []);

  function changeSetting(key: keyof Settings, value: number) {
    if (!settings || !version) return;
    setSettings({ ...settings, [key]: value });
    window.clearTimeout(settingsTimer.current);
    settingsTimer.current = window.setTimeout(() => run(() => api.setSettings(version.id, { [key]: value })), 250);
  }

  function onPreviewSelect(id: string) {
    setSelected(id);
    setTab("edit");
    const row = document.querySelector(`[data-bullet="${id}"], [data-entry="${id}"]`);
    row?.scrollIntoView({ block: "nearest", behavior: "smooth" });
  }

  function onPreviewEdit(id: string) {
    if (!version) return;
    if (findBullet(version, id)) {
      setSelected(id);
      setEditing(id);
    } else if (isEntry(version, id)) {
      setTab("edit");
      setSelected(id);
      setEditingEntry(id);
    }
  }

  async function doExport() {
    if (!version) return;
    let replace = false;
    if (version.export.state === "changed-outside") {
      replace = window.confirm(
        `${version.export.source_path} or its PDF was changed outside the studio. Replace those files with the studio's version?`,
      );
      if (!replace) return;
    }
    await run(async () => (await api.exportFiles(version.id, replace)).version);
  }

  if (!version) {
    return (
      <>
        <ErrorNote error={error} />
        {error ? <Link to="/applications">Back to Applications</Link> : <p className="muted">Loading resume…</p>}
      </>
    );
  }

  const fillLabel = preview && (preview.pages > 1
    ? `${preview.pages} pages`
    : `${Math.round(preview.fill * 100)}% of the page used`);

  return (
    <>
      <div className="row" style={{ marginBottom: 12 }}>
        <h1 className="grow" style={{ margin: 0 }}>
          <Link to="/applications">Applications</Link> / {version.application_folder.replace("applications/", "")}
        </h1>
        <Badge tone={exportTone[version.export.state]}>{exportLabel[version.export.state]}</Badge>
      </div>
      <ErrorNote error={error} onClose={() => setError(null)} />
      <div className="card">
        <Toolbar>
          <select aria-label="Resume version" disabled={busy} value={version.id} onChange={(e) => navigate(`/applications/${e.target.value}`)} style={{ width: "auto" }}>
            {version.versions.map((v) => (
              <option key={v.id} value={v.id}>
                {v.name}
              </option>
            ))}
          </select>
          <Button size="small" disabled={busy} onClick={() => run(async () => {
            const next = await api.newVersion(version.id);
            navigate(`/applications/${next.id}`);
            return next;
          })}>
            New version
          </Button>
          {version.versions.length > 1 && (
            <Button
              size="small"
              variant="danger"
              disabled={busy}
              onClick={() => {
                if (!window.confirm(`Delete ${version.name}? Exported files stay in the application folder.`)) return;
                void run(async () => {
                  const next = await api.deleteVersion(version.id);
                  navigate(`/applications/${next.id}`);
                  return next;
                });
              }}
            >
              Delete version
            </Button>
          )}
          <select
            value={version.template}
            onChange={(e) => run(() => api.setTemplate(version.id, e.target.value))}
            style={{ width: "auto" }}
            aria-label="Template"
          >
            <option value="jake">Jake-style</option>
            <option value="classic">Classic (Harvard-style)</option>
            <option value="modern">Modern</option>
          </select>
          <span className="grow" />
          <Button variant="primary" onClick={doExport} disabled={busy}>
            Export .typ + .pdf
          </Button>
        </Toolbar>
        {settings && (
          <Toolbar>
            <label className="small">
              Font {settings.font_size.toFixed(2)} pt{" "}
              <input type="range" min={9} max={12} step={0.25} value={settings.font_size} onChange={(e) => changeSetting("font_size", Number(e.target.value))} />
            </label>
            <label className="small">
              Spacing {settings.spacing.toFixed(2)}×{" "}
              <input type="range" min={0.5} max={1.6} step={0.05} value={settings.spacing} onChange={(e) => changeSetting("spacing", Number(e.target.value))} />
            </label>
            <label className="small">
              Margins {settings.margin.toFixed(2)} in{" "}
              <input type="range" min={0.4} max={1} step={0.05} value={settings.margin} onChange={(e) => changeSetting("margin", Number(e.target.value))} />
            </label>
          </Toolbar>
        )}
        {(version.export.state === "current" || version.export.state === "outdated") && (
          <p className="small muted" style={{ margin: "6px 0 0" }}>
            Exported to <code>{version.export.pdf_path}</code>
          </p>
        )}
      </div>

      <div className="studio">
        <div className="studio-left card">
          <div className="tabs" role="tablist">
            {(
              [
                ["edit", "Edit"],
                ["header", "Header & skills"],
                ["checks", "Screening checks"],
                ["ai", "Agent handoff"],
              ] as const
            ).map(([key, label]) => (
              <button key={key} className={`tab ${tab === key ? "active" : ""}`} role="tab" aria-selected={tab === key} onClick={() => setTab(key)}>
                {label}
              </button>
            ))}
          </div>
          {tab === "edit" && (
            <Outline
              version={version}
              selected={selected}
              onSelect={setSelected}
              run={run}
              editingEntry={editingEntry}
              setEditingEntry={setEditingEntry}
            />
          )}
          {tab === "header" && <HeaderPanel key={version.id} version={version} run={run} />}
          {tab === "checks" && <ChecksPanel key={version.id} version={version} run={run} />}
          {tab === "ai" && <AskAiPanel key={version.id} version={version} run={run} />}
        </div>
        <div className="studio-right">
          <div className="preview-status">
            {preview && fillLabel && (
              <Meter value={preview.pages > 1 ? 1 : preview.fill} label={fillLabel} warnAbove={preview.pages > 1 ? 1 : 1.01} />
            )}
            {busy && <span className="small muted" role="status">Saving…</span>}
            {!preview && !error && <span className="small muted">Preparing preview…</span>}
          </div>
          {!!preview?.warnings.length && (
            <details className="small">
              <summary>Preview warnings</summary>
              <ul>{[...new Set(preview.warnings)].map((warning) => <li key={warning}>{warning}</li>)}</ul>
            </details>
          )}
          {preview && (
            <PdfPreview
              preview={preview}
              marginIn={version.settings.margin}
              selected={selected}
              editing={editing}
              onSelect={onPreviewSelect}
              onEdit={onPreviewEdit}
              renderEditor={(id) => {
                const bullet = findBullet(version, id);
                return bullet ? (
                  <MarkupEditor
                    initial={bullet.text}
                    onCancel={() => setEditing(null)}
                    onSave={(text) => run(() => api.editBullet(version.id, id, text)).then(() => setEditing(null))}
                  />
                ) : null;
              }}
            />
          )}
          {preview && <p className="small muted">Double-click a bullet or entry in the preview to edit it.</p>}
        </div>
      </div>
    </>
  );
}
