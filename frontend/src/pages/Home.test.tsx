import { cleanup, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { afterEach, expect, it, vi } from "vitest";
import { api } from "../api";
import Home from "./Home";

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

it("reports a resume load failure without showing the empty state", async () => {
  vi.spyOn(api, "resumes").mockRejectedValue(new Error("Workspace unavailable"));
  render(<MemoryRouter><Home /></MemoryRouter>);

  expect(screen.getByText("Loading resumes…")).toBeTruthy();
  expect((await screen.findByRole("alert")).textContent).toContain("Workspace unavailable");
  expect(screen.queryByText("No resumes yet")).toBeNull();
});
