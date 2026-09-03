import { beforeAll, describe, expect, it } from "vitest";

const values = new Map<string, string>();
const sessionValues = new Map<string, string>();

beforeAll(() => {
  Object.defineProperty(globalThis, "sessionStorage", {
    value: {
      getItem: (key: string) => sessionValues.get(key) ?? null,
      setItem: (key: string, value: string) => sessionValues.set(key, value),
      removeItem: (key: string) => sessionValues.delete(key)
    },
    configurable: true
  });
  Object.defineProperty(globalThis, "localStorage", {
    value: {
      getItem: (key: string) => values.get(key) ?? null,
      setItem: (key: string, value: string) => values.set(key, value),
      removeItem: (key: string) => values.delete(key)
    },
    configurable: true
  });
});

describe("Supplier API client", () => {
  it("gradi determinističan query string bez praznih vrednosti", async () => {
    const { queryString } = await import("./client");
    expect(
      queryString({ limit: 25, offset: 0, status: "", active_only: true })
    ).toBe("?limit=25&offset=0&active_only=true");
  });

  it("ne čuva administratorski token u browser storage-u", async () => {
    await import("./client");
    expect(values.has("amh.access_token")).toBe(false);
    expect(sessionValues.has("amh.access_token")).toBe(false);
  });

  it("pretvara 422 listu validacionih grešaka u čitljivu poruku", async () => {
    const originalFetch = globalThis.fetch;
    globalThis.fetch = async () =>
      new Response(
        JSON.stringify({
          detail: [
            { loc: ["body", "times", 0], msg: "Field required" }
          ]
        }),
        { status: 422, headers: { "Content-Type": "application/json" } }
      );
    try {
      const { api } = await import("./client");
      await expect(api("/test")).rejects.toMatchObject({
        status: 422,
        message: "times.0: Field required"
      });
    } finally {
      globalThis.fetch = originalFetch;
    }
  });
});
