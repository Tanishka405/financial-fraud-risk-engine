import { ApiError, api, qs } from "@/api/client";
import { mockApi } from "./utils";

describe("api client", () => {
  it("drops empty params when building a query string", () => { expect(qs({ a: 1, b: "", c: undefined, d: false, e: true })).toBe("?a=1&e=true"); });
  it("maps the backend error envelope to ApiError", async () => {
    mockApi({ "/api/x": [422, { error: { code: "INVALID_FILTER", message: "bad date", details: { field: "from" } } }] });
    await expect(api.get("/api/x")).rejects.toMatchObject({ name: "ApiError", status: 422, code: "INVALID_FILTER", message: "bad date" });
  });
  it("reports an unreachable backend distinctly", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => { throw new TypeError("fetch failed"); }));
    const e = await api.get("/api/x").catch((x: unknown) => x);
    expect(e).toBeInstanceOf(ApiError); expect((e as ApiError).code).toBe("NETWORK_ERROR");
  });
  it("returns parsed JSON on success", async () => { mockApi({ "/api/ok": { a: 1 } }); await expect(api.get("/api/ok")).resolves.toEqual({ a: 1 }); });
});
