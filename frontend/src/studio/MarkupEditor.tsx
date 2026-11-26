import { useEffect, useRef, useState, type KeyboardEvent } from "react";
import { Button } from "../kit";
import { linkSelection, wrapSelection, type Selection } from "../markup";

/** A textarea for resume text: Ctrl+B bold, Ctrl+I italic, Ctrl+K link, Enter saves, Esc cancels. */
export default function MarkupEditor({
  initial,
  onSave,
  onCancel,
  saveLabel = "Save",
}: {
  initial: string;
  onSave: (text: string) => void;
  onCancel: () => void;
  saveLabel?: string;
}) {
  const [value, setValue] = useState(initial);
  const ref = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    const el = ref.current;
    if (el) {
      el.focus();
      el.setSelectionRange(el.value.length, el.value.length);
    }
  }, []);

  function apply(next: Selection) {
    setValue(next.value);
    requestAnimationFrame(() => ref.current?.setSelectionRange(next.start, next.end));
  }

  function onKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    const el = event.currentTarget;
    const mod = event.ctrlKey || event.metaKey;
    if (mod && event.key.toLowerCase() === "b") {
      event.preventDefault();
      apply(wrapSelection(value, el.selectionStart, el.selectionEnd, "**"));
    } else if (mod && event.key.toLowerCase() === "i") {
      event.preventDefault();
      apply(wrapSelection(value, el.selectionStart, el.selectionEnd, "*"));
    } else if (mod && event.key.toLowerCase() === "k") {
      event.preventDefault();
      const url = window.prompt("Link address (https://…)");
      if (url) apply(linkSelection(value, el.selectionStart, el.selectionEnd, url));
    } else if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      if (value.trim()) onSave(value.trim());
    } else if (event.key === "Escape") {
      event.preventDefault();
      onCancel();
    }
  }

  return (
    <div>
      <textarea
        ref={ref}
        value={value}
        onChange={(e) => setValue(e.target.value)}
        onKeyDown={onKeyDown}
        aria-label="Bullet text"
      />
      <div className="row small" style={{ marginTop: 4 }}>
        <span className="muted grow">Enter saves · Esc cancels · Ctrl+B bold · Ctrl+I italic · Ctrl+K link</span>
        <Button size="small" onClick={onCancel}>
          Cancel
        </Button>
        <Button size="small" variant="primary" onClick={() => value.trim() && onSave(value.trim())}>
          {saveLabel}
        </Button>
      </div>
    </div>
  );
}
