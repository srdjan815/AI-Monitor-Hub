import { describe, expect, it } from "vitest";
import { canAccess, firstAccessiblePath } from "./accessControl";

describe("page access policy", () => {
  it("does not expose supplier administration to a catalog-only role", () => {
    const permissions = ["catalog.read", "content.read", "inventory.read"];
    expect(canAccess(permissions, "suppliers.read")).toBe(false);
    expect(firstAccessiblePath(permissions)).toBeNull();
  });

  it("selects the first page actually allowed to the user", () => {
    expect(firstAccessiblePath(["incidents.read"])).toBe("/incidents");
    expect(firstAccessiblePath(["mapping_profiles.read"])).toBe("/mappings");
  });

  it("honours an explicit wildcard without treating login as authorization", () => {
    expect(canAccess([], "suppliers.read")).toBe(false);
    expect(canAccess(["*"], "suppliers.read")).toBe(true);
  });
});
