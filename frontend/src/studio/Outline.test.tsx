import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { Version } from "../api";
import Outline from "./Outline";

vi.mock("../api", async (original) => {
  const actual = await original<typeof import("../api")>();
  return {
    ...actual,
    api: {
      ...actual.api,
      hide: vi.fn().mockResolvedValue({}),
      move: vi.fn().mockResolvedValue({}),
      editBullet: vi.fn().mockResolvedValue({}),
    },
  };
});

const { api } = await import("../api");

const bullet = (id: string, text: string) => ({
  id,
  text,
  library_text: text,
  override_text: null,
  variant_id: null,
  raw_typst: null,
  hidden: false,
  variants: [],
  evidence: [],
});

const version = {
  id: "ver_1",
  sections: [
    {
      id: "sec_1",
      title: "Projects",
      kind: "project",
      hidden: false,
      entries: [
        {
          id: "ent_1",
          kind: "project",
          title: "Note Taker",
          url: null,
          tech: "",
          details: "",
          subtitle: "",
          location: "",
          dates: "2026",
          note: "",
          hidden: false,
          evidence: [],
          bullets: [bullet("bul_1", "First **bold** bullet"), bullet("bul_2", "Second bullet")],
        },
      ],
    },
  ],
} as unknown as Version;

afterEach(cleanup);

function setup() {
  const run = vi.fn(async (action: () => Promise<Version>) => {
    await action();
  });
  const onSelect = vi.fn();
  render(
    <Outline version={version} selected={null} onSelect={onSelect} run={run} editingEntry={null} setEditingEntry={vi.fn()} />,
  );
  return { run, onSelect };
}

describe("Outline", () => {
  it("lists sections, entries and formatted bullets", () => {
    setup();
    expect(screen.getByText("Projects")).toBeTruthy();
    expect(screen.getByText("Note Taker")).toBeTruthy();
    expect(screen.getByText("bold").tagName).toBe("STRONG");
  });

  it("moves and hides a bullet through the API", () => {
    setup();
    const row = document.querySelector('[data-bullet="bul_2"]')!;
    fireEvent.click(row.querySelector('[aria-label="Move up"]')!);
    expect(api.move).toHaveBeenCalledWith("ver_1", "bullet", "bul_2", 0);
    fireEvent.click(row.querySelector('[aria-label="Hide"]')!);
    expect(api.hide).toHaveBeenCalledWith("ver_1", "bullet", "bul_2", true);
  });

  it("edits a bullet in place and saves with Enter", () => {
    setup();
    const row = document.querySelector('[data-bullet="bul_1"]')!;
    fireEvent.doubleClick(row.querySelector(".bullet-text")!);
    const box = screen.getByLabelText("Bullet text");
    fireEvent.change(box, { target: { value: "Rewritten bullet" } });
    fireEvent.keyDown(box, { key: "Enter" });
    expect(api.editBullet).toHaveBeenCalledWith("ver_1", "bul_1", "Rewritten bullet");
  });
});
