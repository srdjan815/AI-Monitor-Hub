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

  it("trajno čuva Bearer token u localStorage", async () => {
    const { getAccessToken, setAccessToken } = await import("./client");
    const token = "opaque.portal.token";
    setAccessToken(`Bearer ${token}`);
    expect(getAccessToken()).toBe(token);
    expect(values.get("amh.access_token")).toBe(token);
    setAccessToken("");
    expect(getAccessToken()).toBe("");
  });
});
