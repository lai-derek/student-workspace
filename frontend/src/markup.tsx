// The studio's inline markup, as the server reads it: **bold**, *italic*, [text](url).
import type { ReactNode } from "react";

export interface Selection {
  value: string;
  start: number;
  end: number;
}

/** Wrap the selected text in a marker (or unwrap it if it's already wrapped). */
export function wrapSelection(value: string, start: number, end: number, marker: string): Selection {
  const before = value.slice(0, start);
  const selected = value.slice(start, end);
  const after = value.slice(end);
  if (before.endsWith(marker) && after.startsWith(marker)) {
    return {
      value: before.slice(0, -marker.length) + selected + after.slice(marker.length),
      start: start - marker.length,
      end: end - marker.length,
    };
  }
  return { value: before + marker + selected + marker + after, start: start + marker.length, end: end + marker.length };
}

/** Insert a link around the selection, using `url`. */
export function linkSelection(value: string, start: number, end: number, url: string): Selection {
  const selected = value.slice(start, end) || "link text";
  const inserted = `[${selected}](${url})`;
  return { value: value.slice(0, start) + inserted + value.slice(end), start: start + 1, end: start + 1 + selected.length };
}

const TOKEN = /\*\*(.+?)\*\*|\*(\S(?:.*?\S)?)\*|\[([^\]]+)\]\(([^)\s]+)\)/g;

/** Show markup formatted (for reading in lists); editing still uses the raw text. */
export function formatted(text: string): ReactNode[] {
  const out: ReactNode[] = [];
  let last = 0;
  for (const match of text.matchAll(TOKEN)) {
    const index = match.index ?? 0;
    if (index > last) out.push(text.slice(last, index));
    if (match[1] !== undefined) out.push(<strong key={index}>{match[1]}</strong>);
    else if (match[2] !== undefined) out.push(<em key={index}>{match[2]}</em>);
    else out.push(<u key={index}>{match[3]}</u>);
    last = index + match[0].length;
  }
  if (last < text.length) out.push(text.slice(last));
  return out;
}
