// The live preview: pdf.js draws each page; transparent boxes over each bullet and
// entry (positions from the server) make the PDF clickable. Click selects, double-click edits.
import * as pdfjs from "pdfjs-dist";
import workerUrl from "pdfjs-dist/build/pdf.worker.min.mjs?url";
import { useEffect, useLayoutEffect, useRef, useState, type ReactNode } from "react";
import type { Box, Preview } from "../api";

pdfjs.GlobalWorkerOptions.workerSrc = workerUrl;

function decode(base64: string): Uint8Array {
  const binary = atob(base64);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);
  return bytes;
}

export default function PdfPreview({
  preview,
  marginIn,
  selected,
  editing,
  onSelect,
  onEdit,
  renderEditor,
}: {
  preview: Preview;
  marginIn: number;
  selected: string | null;
  editing: string | null;
  onSelect: (id: string) => void;
  onEdit: (id: string) => void;
  renderEditor: (id: string) => ReactNode;
}) {
  const container = useRef<HTMLDivElement>(null);
  const holders = useRef<(HTMLDivElement | null)[]>([]);
  const [width, setWidth] = useState(600);

  useLayoutEffect(() => {
    const el = container.current;
    if (!el) return;
    const observer = new ResizeObserver(() => setWidth(el.clientWidth - 24));
    observer.observe(el);
    setWidth(el.clientWidth - 24);
    return () => observer.disconnect();
  }, []);

  const scale = Math.max(width, 200) / preview.page_width;

  useEffect(() => {
    let cancelled = false;
    const task = pdfjs.getDocument({ data: decode(preview.pdf_base64) });
    (async () => {
      const doc = await task.promise;
      const ratio = window.devicePixelRatio || 1;
      for (let n = 1; n <= doc.numPages; n++) {
        const page = await doc.getPage(n);
        const viewport = page.getViewport({ scale: scale * ratio });
        const canvas = document.createElement("canvas");
        canvas.width = Math.floor(viewport.width);
        canvas.height = Math.floor(viewport.height);
        canvas.style.width = `${viewport.width / ratio}px`;
        canvas.style.height = `${viewport.height / ratio}px`;
        await page.render({ canvas, canvasContext: canvas.getContext("2d")!, viewport }).promise;
        // Swap only when drawn, so the page never flashes blank between edits.
        if (!cancelled) holders.current[n - 1]?.replaceChildren(canvas);
      }
      await doc.destroy();
    })().catch((error: Error) => {
      if (!cancelled) console.error("preview failed", error);
    });
    return () => {
      cancelled = true;
    };
  }, [preview.pdf_base64, scale]);

  const right = preview.page_width - marginIn * 72;
  const place = (box: Box) => ({
    left: (box.x - 8) * scale,
    top: (box.top - 3) * scale,
    width: (right - box.x + 12) * scale,
    height: Math.max((box.bottom - box.top + 1) * scale, 14),
  });

  return (
    <div className="preview" ref={container}>
      {Array.from({ length: preview.pages }, (_, index) => (
        <div
          key={index}
          className="preview-page"
          style={{ width: preview.page_width * scale, height: preview.page_height * scale }}
        >
          <div ref={(el) => void (holders.current[index] = el)} />
          {Object.entries(preview.boxes)
            .filter(([, box]) => box.page === index + 1)
            .map(([id, box]) => (
              <div
                key={id}
                className={`hit ${selected === id ? "selected" : ""}`}
                style={place(box)}
                title="Click to select, double-click to edit"
                data-id={id}
                onClick={() => onSelect(id)}
                onDoubleClick={() => onEdit(id)}
              />
            ))}
          {editing && preview.boxes[editing]?.page === index + 1 && (
            <div
              className="inline-editor"
              style={{ ...place(preview.boxes[editing]), height: "auto", minWidth: 320 }}
              onClick={(e) => e.stopPropagation()}
            >
              {renderEditor(editing)}
            </div>
          )}
        </div>
      ))}
    </div>
  );
}
