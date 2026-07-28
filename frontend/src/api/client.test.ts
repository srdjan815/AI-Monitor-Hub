import { beforeAll, describe, expect, it } from "vitest";

const values = new Map<string, string>();

beforeAll(() => {
  Object.defineProperty(globalThis, "sessionStorage", {
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

  it("čuva token samo u sessionStorage i čita permission claim", async () => {
    const { decodeTokenPermissions, getAccessToken, setAccessToken } =
      await import("./client");
    const payload = btoa(
      JSON.stringify({ permissions: ["suppliers.read", "incidents.read"] })
    )
      .replaceAll("+", "-")
      .replaceAll("/", "_")
      .replaceAll("=", "");
    const token = `header.${payload}.signature`;
    setAccessToken(`Bearer ${token}`);
    expect(getAccessToken()).toBe(token);
    expect(decodeTokenPermissions()).toEqual([
      "suppliers.read",
      "incidents.read"
    ]);
    setAccessToken("");
    expect(getAccessToken()).toBe("");
  });

  it("izvodi UI dozvole iz Foundation JWT roles claim-a", async () => {
    const { decodeTokenPermissions } = await import("./client");
    const payload = btoa(JSON.stringify({ roles: ["supplier_admin"] }))
      .replaceAll("+", "-")
      .replaceAll("/", "_")
      .replaceAll("=", "");
    const permissions = decodeTokenPermissions(`header.${payload}.signature`);
    expect(permissions).toContain("suppliers.write");
    expect(permissions).toContain("supplier_sources.validate");
  });

  it("daje sve UI akcije system_admin ulozi", async () => {
    const { decodeTokenPermissions } = await import("./client");
    const payload = btoa(JSON.stringify({ roles: ["system_admin"] }))
      .replaceAll("+", "-")
      .replaceAll("/", "_")
      .replaceAll("=", "");
    expect(decodeTokenPermissions(`header.${payload}.signature`)).toContain("*");
  });
});
