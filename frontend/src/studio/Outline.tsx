// The editable outline: sections, entries and bullets of one version, in page order.
import { useState } from "react";
import { api, type Bullet, type Entry, type Evidence, type ResumeSection, type Version } from "../api";
import { Badge, Button, Field } from "../kit";
import { formatted } from "../markup";
import MarkupEditor from "./MarkupEditor";

export type Run = (action: () => Promise<Version>) => Promise<void>;

interface Props {
  version: Version;
  selected: string | null;
  onSelect: (id: string | null) => void;
  run: Run;
  editingEntry: string | null;
  setEditingEntry: (id: string | null) => void;
}

const KINDS = ["education", "experience", "project", "leadership", "other"];

function Controls({
  onUp,
  onDown,
  hidden,
  onToggle,
  extra,
}: {
  onUp?: () => void;
  onDown?: () => void;
  hidden: boolean;
  onToggle: () => void;
  extra?: React.ReactNode;
}) {
  return (
    <span className="controls" onClick={(e) => e.stopPropagation()}>
      <Button size="small" variant="ghost" onClick={onUp} disabled={!onUp} aria-label="Move up">
        ↑
      </Button>
      <Button size="small" variant="ghost" onClick={onDown} disabled={!onDown} aria-label="Move down">
        ↓
      </Button>
      <Button size="small" variant="ghost" onClick={onToggle} aria-label={hidden ? "Show" : "Hide"}>
        {hidden ? "Show" : "Hide"}
      </Button>
      {extra}
    </span>
  );
}

export default function Outline(props: Props) {
  const { version, run } = props;
  const [adding, setAdding] = useState(false);
  const [title, setTitle] = useState("");
  const [kind, setKind] = useState("experience");
  const sections = version.sections;

  return (
    <div>
      {sections.map((section, i) => (
        <SectionBlock
          key={section.id}
          {...props}
          section={section}
          onUp={i > 0 ? () => run(() => api.move(version.id, "section", section.id, i - 1)) : undefined}
          onDown={i < sections.length - 1 ? () => run(() => api.move(version.id, "section", section.id, i + 1)) : undefined}
        />
      ))}
      {adding ? (
        <div className="details">
          <div className="row">
            <Field label="Section title">
              <input type="text" value={title} onChange={(e) => setTitle(e.target.value)} placeholder="Experience" />
            </Field>
            <Field label="Kind">
              <select value={kind} onChange={(e) => setKind(e.target.value)}>
                {KINDS.map((k) => (
                  <option key={k}>{k}</option>
                ))}
              </select>
            </Field>
          </div>
          <div className="row">
            <Button
              variant="primary"
              size="small"
              disabled={!title.trim()}
              onClick={() => run(() => api.addSection(version.id, title.trim(), kind)).then(() => setAdding(false))}
            >
              Add section
            </Button>
            <Button size="small" onClick={() => setAdding(false)}>
              Cancel
            </Button>
          </div>
        </div>
      ) : (
        <Button size="small" onClick={() => setAdding(true)}>
          + Section
        </Button>
      )}
    </div>
  );
}

function SectionBlock(props: Props & { section: ResumeSection; onUp?: () => void; onDown?: () => void }) {
  const { version, section, run } = props;
  const [adding, setAdding] = useState(false);
  return (
    <div className={`outline-section ${section.hidden ? "hidden-item" : ""}`}>
      <div className="outline-section-title">
        <span className="grow">{section.title}</span>
        <Controls
          onUp={props.onUp}
          onDown={props.onDown}
          hidden={section.hidden}
          onToggle={() => run(() => api.hide(version.id, "section", section.id, !section.hidden))}
          extra={
            <Button size="small" variant="ghost" onClick={() => setAdding(!adding)}>
              + Entry
            </Button>
          }
        />
      </div>
      {adding && (
        <EntryForm
          title="New entry"
          entry={{ title: "", subtitle: "", location: "", dates: "", tech: "", details: "", note: "", url: null }}
          onCancel={() => setAdding(false)}
          onSave={(fields) =>
            run(() => api.addEntry(version.id, section.id, { ...fields, kind: section.kind })).then(() => setAdding(false))
          }
        />
      )}
      {section.entries.map((entry, i) => (
        <EntryBlock
          key={entry.id}
          {...props}
          entry={entry}
          onUp={i > 0 ? () => run(() => api.move(version.id, "entry", entry.id, i - 1)) : undefined}
          onDown={
            i < section.entries.length - 1 ? () => run(() => api.move(version.id, "entry", entry.id, i + 1)) : undefined
          }
        />
      ))}
    </div>
  );
}

type EntryFields = Pick<Entry, "title" | "subtitle" | "location" | "dates" | "tech" | "details" | "note" | "url">;

function EntryForm({
  title,
  entry,
  onSave,
  onCancel,
}: {
  title: string;
  entry: EntryFields;
  onSave: (fields: EntryFields) => void;
  onCancel: () => void;
}) {
  const [fields, setFields] = useState<EntryFields>(entry);
  const set = (key: keyof EntryFields) => (e: React.ChangeEvent<HTMLInputElement>) =>
    setFields({ ...fields, [key]: key === "url" && !e.target.value ? null : e.target.value });
  return (
    <div className="details">
      <h3>{title}</h3>
      <Field label="Title (school, role or project)">
        <input type="text" value={fields.title} onChange={set("title")} />
      </Field>
      <div className="row">
        <Field label="Subtitle (degree or organization)">
          <input type="text" value={fields.subtitle} onChange={set("subtitle")} />
        </Field>
        <Field label="Dates">
          <input type="text" value={fields.dates} onChange={set("dates")} placeholder="2025 -- Present" />
        </Field>
      </div>
      <div className="row">
        <Field label="Location">
          <input type="text" value={fields.location} onChange={set("location")} />
        </Field>
        <Field label="Technologies">
          <input type="text" value={fields.tech} onChange={set("tech")} />
        </Field>
      </div>
      <Field label="Details after the title" hint="Shown after a | on the title line">
        <input type="text" value={fields.details} onChange={set("details")} />
      </Field>
      <Field label="Extra line">
        <input type="text" value={fields.note} onChange={set("note")} />
      </Field>
      <Field label="Link (https://…)">
        <input type="text" value={fields.url ?? ""} onChange={set("url")} />
      </Field>
      <div className="row">
        <Button variant="primary" size="small" disabled={!fields.title.trim()} onClick={() => onSave(fields)}>
          Save
        </Button>
        <Button size="small" onClick={onCancel}>
          Cancel
        </Button>
      </div>
    </div>
  );
}

function EntryBlock(props: Props & { entry: Entry; onUp?: () => void; onDown?: () => void }) {
  const { version, entry, run, selected, onSelect, editingEntry, setEditingEntry } = props;
  const [adding, setAdding] = useState(false);
  const bullets = entry.bullets;
  return (
    <div className={`outline-entry ${entry.hidden ? "hidden-item" : ""}`}>
      <div
        className={`outline-entry-title ${selected === entry.id ? "selected" : ""}`}
        onClick={() => onSelect(entry.id)}
        data-entry={entry.id}
      >
        <span className="grow">
          {entry.title}
          {entry.dates && <span className="muted small"> · {entry.dates}</span>}
        </span>
        <Controls
          onUp={props.onUp}
          onDown={props.onDown}
          hidden={entry.hidden}
          onToggle={() => run(() => api.hide(version.id, "entry", entry.id, !entry.hidden))}
          extra={
            <>
              <Button size="small" variant="ghost" onClick={() => setEditingEntry(entry.id)}>
                Edit
              </Button>
              <Button size="small" variant="ghost" onClick={() => setAdding(true)}>
                + Bullet
              </Button>
            </>
          }
        />
      </div>
      {editingEntry === entry.id && (
        <EntryForm
          title="Edit entry (changes every resume that uses it)"
          entry={entry}
          onCancel={() => setEditingEntry(null)}
          onSave={(fields) => run(() => api.updateEntry(version.id, entry.id, fields)).then(() => setEditingEntry(null))}
        />
      )}
      {bullets.map((bullet, i) => (
        <BulletRow
          key={bullet.id}
          {...props}
          bullet={bullet}
          onUp={i > 0 ? () => run(() => api.move(version.id, "bullet", bullet.id, i - 1)) : undefined}
          onDown={i < bullets.length - 1 ? () => run(() => api.move(version.id, "bullet", bullet.id, i + 1)) : undefined}
        />
      ))}
      {adding && (
        <div className="details">
          <MarkupEditor
            initial=""
            saveLabel="Add bullet"
            onCancel={() => setAdding(false)}
            onSave={(text) => run(() => api.addBullet(version.id, entry.id, text)).then(() => setAdding(false))}
          />
        </div>
      )}
    </div>
  );
}

function BulletRow(props: Props & { bullet: Bullet; onUp?: () => void; onDown?: () => void }) {
  const { version, bullet, run, selected, onSelect } = props;
  const [editing, setEditing] = useState(false);
  const isSelected = selected === bullet.id;
  return (
    <>
      <div
        className={`bullet ${isSelected ? "selected" : ""} ${bullet.hidden ? "hidden-item" : ""}`}
        data-bullet={bullet.id}
        onClick={() => onSelect(bullet.id)}
      >
        <span>•</span>
        {editing ? (
          <div className="grow" onClick={(e) => e.stopPropagation()}>
            <MarkupEditor
              initial={bullet.text}
              onCancel={() => setEditing(false)}
              onSave={(text) => run(() => api.editBullet(version.id, bullet.id, text)).then(() => setEditing(false))}
            />
          </div>
        ) : (
          <span className="bullet-text" onDoubleClick={() => setEditing(true)}>
            {bullet.raw_typst ? <code>{bullet.raw_typst}</code> : formatted(bullet.text)}{" "}
            {bullet.override_text && <span className="edited-mark">edited here</span>}
            {bullet.variants.length > 0 && <Badge tone="neutral">{bullet.variants.length} variants</Badge>}
          </span>
        )}
        {!editing && (
          <Controls
            onUp={props.onUp}
            onDown={props.onDown}
            hidden={bullet.hidden}
            onToggle={() => run(() => api.hide(version.id, "bullet", bullet.id, !bullet.hidden))}
            extra={
              <Button size="small" variant="ghost" onClick={() => setEditing(true)}>
                Edit
              </Button>
            }
          />
        )}
      </div>
      {isSelected && !editing && <BulletDetails version={version} bullet={bullet} run={run} />}
    </>
  );
}

function BulletDetails({ version, bullet, run }: { version: Version; bullet: Bullet; run: Run }) {
  const [variantText, setVariantText] = useState("");
  const [allEvidence, setAllEvidence] = useState<Evidence[] | null>(null);
  const [raw, setRaw] = useState(bullet.raw_typst ?? "");
  const [showRaw, setShowRaw] = useState(Boolean(bullet.raw_typst));
  const linked = new Set(bullet.evidence.map((e) => e.id));

  async function link(noteId: string, linkIt: boolean) {
    await api.linkEvidence(noteId, "bullet", bullet.id, linkIt);
    await run(() => api.version(version.id));
  }

  return (
    <div className="details" onClick={(e) => e.stopPropagation()}>
      {bullet.override_text && (
        <div className="row small" style={{ marginBottom: 8 }}>
          <span className="grow muted">Edited for this version only. Other resumes keep the library wording.</span>
          <Button size="small" onClick={() => run(() => api.saveToLibrary(version.id, bullet.id))}>
            Use everywhere
          </Button>
          <Button size="small" onClick={() => run(() => api.editBullet(version.id, bullet.id, bullet.library_text))}>
            Undo edit
          </Button>
        </div>
      )}
      <h3>Variants</h3>
      {bullet.variants.length === 0 && <p className="muted small">No alternative wordings yet.</p>}
      {bullet.variants.map((variant) => (
        <div className="variant" key={variant.id}>
          <span className="grow">
            {formatted(variant.text)} {variant.source === "ai" && <Badge tone="neutral">AI</Badge>}
          </span>
          {bullet.variant_id === variant.id ? (
            <Button size="small" onClick={() => run(() => api.chooseVariant(version.id, bullet.id, null))}>
              Using · undo
            </Button>
          ) : (
            <Button size="small" onClick={() => run(() => api.chooseVariant(version.id, bullet.id, variant.id))}>
              Use
            </Button>
          )}
        </div>
      ))}
      <div className="row" style={{ marginTop: 6 }}>
        <input
          type="text"
          placeholder="Add an alternative wording"
          value={variantText}
          onChange={(e) => setVariantText(e.target.value)}
        />
        <Button
          size="small"
          disabled={!variantText.trim()}
          onClick={() => run(() => api.addVariant(version.id, bullet.id, variantText.trim())).then(() => setVariantText(""))}
        >
          Add
        </Button>
      </div>

      <h3 style={{ marginTop: 12 }}>Evidence</h3>
      {bullet.evidence.length === 0 && <p className="muted small">No evidence linked.</p>}
      {bullet.evidence.map((note) => (
        <div key={note.id} className="small" style={{ marginBottom: 6 }}>
          <strong>{note.title}</strong>{" "}
          <Button size="small" variant="ghost" onClick={() => link(note.id, false)}>
            Unlink
          </Button>
          <div className="muted" style={{ whiteSpace: "pre-wrap" }}>
            {note.body}
          </div>
        </div>
      ))}
      {allEvidence === null ? (
        <Button size="small" onClick={() => api.evidence().then(setAllEvidence)}>
          Link evidence…
        </Button>
      ) : (
        <select defaultValue="" onChange={(e) => e.target.value && link(e.target.value, true)}>
          <option value="">Choose an evidence note…</option>
          {allEvidence
            .filter((n) => !linked.has(n.id))
            .map((n) => (
              <option key={n.id} value={n.id}>
                {n.title}
              </option>
            ))}
        </select>
      )}

      <div className="row" style={{ marginTop: 12 }}>
        <Button size="small" variant="ghost" onClick={() => setShowRaw(!showRaw)}>
          {showRaw ? "Hide advanced" : "Advanced: raw Typst"}
        </Button>
        <span className="grow" />
        <Button size="small" variant="danger" onClick={() => run(() => api.removeBullet(version.id, bullet.id))}>
          Remove from this version
        </Button>
      </div>
      {showRaw && (
        <div>
          <Field label="Raw Typst for this bullet" hint="Inserted as written. Leave empty to use the normal text.">
            <textarea value={raw} onChange={(e) => setRaw(e.target.value)} />
          </Field>
          <Button size="small" onClick={() => run(() => api.setRaw(version.id, bullet.id, raw.trim() || null))}>
            Apply
          </Button>
        </div>
      )}
    </div>
  );
}
