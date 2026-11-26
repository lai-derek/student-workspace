import { afterEach, describe, expect, it, vi } from "vitest";
import { api, ApiError } from "./api";

function mockFetch(status: number, body: unknown) {
  // A Response body can be read once, so each call gets a new one.
  const fn = vi.fn(
    async (_url: string, _init: RequestInit & { headers: Record<string, string>; body?: string }) =>
      new Response(JSON.stringify(body), { status, statusText: "X" }),
  );
  vi.stubGlobal("fetch", fn);
  return fn;
}

afterEach(() => vi.unstubAllGlobals());

describe("api client", () => {
  it("sends the write header only on writes", async () => {
    const fetch = mockFetch(200, { id: "ver_1" });
    await api.version("ver_1");
    expect(fetch.mock.calls[0][1].headers).toEqual({});
    await api.editBullet("ver_1", "bul_1", "New text");
    const [url, init] = fetch.mock.calls[1];
    expect(url).toBe("/api/studio/versions/ver_1/bullets/bul_1/edit");
    expect(init.method).toBe("POST");
    expect(init.headers["X-Student-Workspace"]).toBe("1");
    expect(JSON.parse(String(init.body))).toEqual({ text: "New text" });
  });

  it("raises the server's message", async () => {
    mockFetch(400, { detail: "bullet can't be empty" });
    await expect(api.editBullet("ver_1", "bul_1", " ")).rejects.toEqual(new ApiError(400, "bullet can't be empty"));
  });
});
