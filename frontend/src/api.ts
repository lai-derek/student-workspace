// Typed client for the local server. Every request carries the session cookie
// automatically (same origin); writes also send the header the server requires.

export type Kind = "section" | "entry" | "bullet";

export interface Section {
  id: string;
  label: string;
  path: string;
}

export interface ToolStatus {
  name: string;
  version: string | null;
  status: "ok" | "stale" | "error";
  detail: string[];
}

export interface WorkspaceStatus {
  root: string;
  status: "current" | "stale" | "error";
  findings: string[];
  tools: ToolStatus[];
}

export interface Evidence {
  id: string;
  title: string;
  body: string;
  source_path: string | null;
}

export interface Variant {
  id: string;
  text: string;
  source: "manual" | "ai";
  request_id: string | null;
}

export interface Bullet {
  id: string;
  text: string;
  library_text: string;
  override_text: string | null;
  variant_id: string | null;
  raw_typst: string | null;
  hidden: boolean;
  variants: Variant[];
  evidence: Evidence[];
}

export interface Entry {
  id: string;
  kind: string;
  title: string;
  url: string | null;
  tech: string;
  details: string;
  subtitle: string;
  location: string;
  dates: string;
  note: string;
  hidden: boolean;
  evidence: Evidence[];
  bullets: Bullet[];
}

export interface ResumeSection {
  id: string;
  title: string;
  kind: string;
  hidden: boolean;
  entries: Entry[];
}

export interface Contact {
  text: string;
  url: string | null;
}

export interface SkillLine {
  label: string;
  value: string;
}

export interface Settings {
  font_size: number;
  spacing: number;
  margin: number;
}

export interface ExportState {
  state: "not-exported" | "current" | "outdated" | "changed-outside" | "missing";
  exported_at: string | null;
  source_path: string;
  pdf_path: string;
}

export interface Version {
  id: string;
  resume_id: string;
  application_folder: string;
  posting_text: string;
  name: string;
  template: string;
  settings: Settings;
  header: { name: string; contact: Contact[] };
  skills: SkillLine[];
  updated_at: string;
  sections: ResumeSection[];
  export: ExportState;
  versions: { id: string; name: string }[];
}

export interface Box {
  page: number;
  x: number;
  top: number;
  bottom: number;
}

export interface Preview {
  pages: number;
  fill: number;
  page_width: number;
  page_height: number;
  boxes: Record<string, Box>;
  warnings: string[];
  pdf_base64: string;
}

export interface Finding {
  level: "ok" | "warning" | "error";
  code: string;
  message: string;
}

export interface Checks {
  parse: { result: "ok" | "warning" | "error"; pages: number; findings: Finding[] };
  keywords: {
    covered: number;
    missing: number;
    terms: { term: string; count: number; covered: boolean; evidence: { id: string; title: string }[] }[];
  };
}

export interface ResumeSummary {
  id: string;
  application_folder: string;
  updated_at: string;
  versions: { id: string; name: string; template: string; updated_at: string; exported_at: string | null }[];
}

export interface HandoffRequest {
  request_path: string;
  request_id: string;
  section: string | null;
  status: string;
  created_at: string | null;
  imported_variants: number;
}

export class ApiError extends Error {
  readonly status: number;

  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function request<T>(method: "GET" | "POST", path: string, body?: unknown, signal?: AbortSignal): Promise<T> {
  const headers: Record<string, string> = {};
  if (method !== "GET") {
    headers["Content-Type"] = "application/json";
    headers["X-Student-Workspace"] = "1"; // required by the server for every write
  }
  const response = await fetch(path, {
    method,
    headers,
    body: method === "GET" ? undefined : JSON.stringify(body ?? {}),
    credentials: "same-origin",
    signal,
  });
  if (!response.ok) {
    let message = `${response.status} ${response.statusText}`;
    try {
      const data = await response.json();
      if (typeof data.detail === "string") message = data.detail;
    } catch {
      // not JSON: keep the status line
    }
    throw new ApiError(response.status, message);
  }
  return (await response.json()) as T;
}

const studio = (path: string) => `/api/studio${path}`;
const v = (id: string, rest = "") => studio(`/versions/${encodeURIComponent(id)}${rest}`);

export const api = {
  sections: () => request<Section[]>("GET", "/api/sections"),
  workspace: () => request<WorkspaceStatus>("GET", "/api/workspace"),

  resumes: () => request<ResumeSummary[]>("GET", studio("/resumes")),
  createResume: (body: {
    application_folder: string;
    name: string;
    template: string;
    contact?: Contact[];
    tex?: string;
    copy_from?: string;
  }) => request<Version>("POST", studio("/resumes"), body),

  version: (id: string) => request<Version>("GET", v(id)),
  preview: (id: string, signal?: AbortSignal) => request<Preview>("GET", v(id, "/preview"), undefined, signal),
  checks: (id: string) => request<Checks>("GET", v(id, "/checks")),

  editBullet: (id: string, bullet: string, text: string) => request<Version>("POST", v(id, `/bullets/${bullet}/edit`), { text }),
  saveToLibrary: (id: string, bullet: string) => request<Version>("POST", v(id, `/bullets/${bullet}/save-to-library`)),
  chooseVariant: (id: string, bullet: string, variant_id: string | null) =>
    request<Version>("POST", v(id, `/bullets/${bullet}/variant`), { variant_id }),
  addVariant: (id: string, bullet: string, text: string) => request<Version>("POST", v(id, `/bullets/${bullet}/variants`), { text }),
  setRaw: (id: string, bullet: string, text: string | null) => request<Version>("POST", v(id, `/bullets/${bullet}/raw`), { text }),
  removeBullet: (id: string, bullet: string) => request<Version>("POST", v(id, `/bullets/${bullet}/remove`)),
  addBullet: (id: string, entry: string, text: string) => request<Version>("POST", v(id, `/entries/${entry}/bullets`), { text }),
  updateEntry: (id: string, entry: string, fields: Partial<Entry>) => request<Version>("POST", v(id, `/entries/${entry}`), fields),
  hide: (id: string, kind: Kind, target: string, hidden: boolean) => request<Version>("POST", v(id, "/hide"), { kind, id: target, hidden }),
  move: (id: string, kind: Kind, target: string, position: number) =>
    request<Version>("POST", v(id, "/move"), { kind, id: target, position }),
  addSection: (id: string, title: string, kind: string) => request<Version>("POST", v(id, "/sections"), { title, kind }),
  addEntry: (id: string, section: string, fields: Partial<Entry> & { entry_id?: string }) =>
    request<Version>("POST", v(id, `/sections/${section}/entries`), fields),
  setTemplate: (id: string, template: string) => request<Version>("POST", v(id, "/template"), { template }),
  setSettings: (id: string, settings: Partial<Settings>) => request<Version>("POST", v(id, "/settings"), settings),
  setHeader: (id: string, header: { name: string; contact: Contact[] }) => request<Version>("POST", v(id, "/header"), header),
  setSkills: (id: string, skills: SkillLine[]) => request<Version>("POST", v(id, "/skills"), skills),
  setPosting: (id: string, text: string) => request<Version>("POST", v(id, "/posting"), { text }),
  newVersion: (id: string) => request<Version>("POST", v(id, "/new-version")),
  deleteVersion: (id: string) => request<Version>("POST", v(id, "/delete")),
  exportFiles: (id: string, replace = false) =>
    request<{ result: { source_path: string; pdf_path: string }; version: Version }>("POST", v(id, "/export"), { replace }),
  requests: (id: string) => request<HandoffRequest[]>("GET", v(id, "/requests")),
  askAi: (id: string, section_id: string, text: string) =>
    request<{ request_path: string; request_id: string }>("POST", v(id, "/ask-ai"), { section_id, request: text }),
  importVariants: (id: string, request_path: string) =>
    request<{ result: { added: number; skipped: string[] }; version: Version }>("POST", v(id, "/import-variants"), { request_path }),

  evidence: () => request<Evidence[]>("GET", studio("/evidence")),
  importEvidence: (path: string) => request<{ ids: string[] }>("POST", studio("/evidence/import"), { path }),
  linkEvidence: (note: string, kind: "entry" | "bullet", target_id: string, linked: boolean) =>
    request<{ status: string }>("POST", studio(`/evidence/${note}/links`), { kind, target_id, linked }),
};
