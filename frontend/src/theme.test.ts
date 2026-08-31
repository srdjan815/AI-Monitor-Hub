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

  it("primenjuje globalno bezbedno pozicioniranje tooltip-a", () => {
    const tooltip = createAppTheme("light").components?.MuiTooltip
      ?.defaultProps;
    const popper = tooltip?.slotProps?.popper;

    expect(tooltip?.placement).toBe("top");
    expect(tooltip?.disableFocusListener).toBe(true);
    expect(tooltip?.disableInteractive).toBe(true);
    expect(popper).toMatchObject({
      disablePortal: false,
      sx: { pointerEvents: "none" },
      modifiers: [
        { name: "offset", options: { offset: [0, 10] } },
        {
          name: "flip",
          options: {
            fallbackPlacements: ["bottom", "right", "left"],
            padding: 8
          }
        },
        {
          name: "preventOverflow",
          options: {
            altAxis: true,
            boundary: "viewport",
            padding: 8,
            tether: true
          }
        }
      ]
    });
  });
});
