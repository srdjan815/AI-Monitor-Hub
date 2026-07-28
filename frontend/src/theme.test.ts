import { describe, expect, it } from "vitest";
import { createAppTheme } from "./theme";

describe("Supplier Admin teme", () => {
  it("gradi odvojene light i dark palete sa vidljivim focus stilom", () => {
    const light = createAppTheme("light");
    const dark = createAppTheme("dark");
    expect(light.palette.mode).toBe("light");
    expect(dark.palette.mode).toBe("dark");
    expect(light.palette.background.default).not.toBe(
      dark.palette.background.default
    );
    expect(light.components?.MuiCssBaseline).toBeDefined();
  });
});
