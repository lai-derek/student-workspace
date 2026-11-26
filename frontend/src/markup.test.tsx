import { render } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { formatted, linkSelection, wrapSelection } from "./markup";

describe("markup editing", () => {
  it("wraps and unwraps the selection", () => {
    const wrapped = wrapSelection("cut costs 40%", 4, 9, "**");
    expect(wrapped).toEqual({ value: "cut **costs** 40%", start: 6, end: 11 });
    expect(wrapSelection(wrapped.value, wrapped.start, wrapped.end, "**").value).toBe("cut costs 40%");
  });

  it("inserts a link around the selection", () => {
    expect(linkSelection("see the demo", 8, 12, "https://example.com").value).toBe(
      "see the [demo](https://example.com)",
    );
  });

  it("shows bold, italic and links formatted", () => {
    const { container } = render(<p>{formatted("**Led** a *small* team; [demo](https://x.org) 2 * 3")}</p>);
    expect(container.querySelector("strong")?.textContent).toBe("Led");
    expect(container.querySelector("em")?.textContent).toBe("small");
    expect(container.querySelector("u")?.textContent).toBe("demo");
    expect(container.textContent).toBe("Led a small team; demo 2 * 3");
  });
});
