import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiError, apiRequest, onUnauthorized } from "./client";

function mockFetch(response: Response | Error) {
  const fn = vi.fn(async () => {
    if (response instanceof Error) throw response;
    return response;
  });
  vi.stubGlobal("fetch", fn);
  return fn;
}

afterEach(() => vi.unstubAllGlobals());

describe("apiRequest", () => {
  it("sends the bearer token and JSON body to the configured base URL", async () => {
    const fetch = mockFetch(new Response(JSON.stringify({ ok: true }), { status: 200 }));
    await apiRequest("/discover", { method: "POST", token: "tkn", body: { query: "x" } });
    const [url, init] = fetch.mock.calls[0] as unknown as [string, RequestInit];
    expect(url).toBe("http://api.test/api/v1/discover");
    expect((init.headers as Record<string, string>).Authorization).toBe("Bearer tkn");
    expect(init.body).toBe('{"query":"x"}');
  });

  it("returns undefined for 204 responses", async () => {
    mockFetch(new Response(null, { status: 204 }));
    await expect(apiRequest("/session", { method: "DELETE", token: "t" })).resolves.toBeUndefined();
  });

  it("maps the error envelope, keeping the request ID", async () => {
    mockFetch(
      new Response(
        JSON.stringify({
          error: { code: "PREREQUISITES_INCOMPLETE", message: "Blocked", details: [], request_id: "req_1" },
        }),
        { status: 409 },
      ),
    );
    const error = await apiRequest("/x").catch((e: unknown) => e);
    expect(error).toBeInstanceOf(ApiError);
    expect(error).toMatchObject({ status: 409, code: "PREREQUISITES_INCOMPLETE", requestId: "req_1" });
  });

  it("reports network failures without inventing data", async () => {
    mockFetch(new TypeError("Failed to fetch"));
    await expect(apiRequest("/health")).rejects.toMatchObject({ code: "NETWORK_ERROR", status: 0 });
  });

  it("notifies the session layer on 401", async () => {
    const listener = vi.fn();
    const unsubscribe = onUnauthorized(listener);
    mockFetch(
      new Response(
        JSON.stringify({ error: { code: "SESSION_EXPIRED", message: "x", details: [], request_id: "r" } }),
        { status: 401 },
      ),
    );
    await apiRequest("/session").catch(() => undefined);
    unsubscribe();
    expect(listener).toHaveBeenCalledOnce();
    expect(listener.mock.calls[0][0]).toMatchObject({ code: "SESSION_EXPIRED" });
  });
});
