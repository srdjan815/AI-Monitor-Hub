import { describe, expect, it } from "vitest";

import { initialSuggestions, suggestedTarget, type AnalysisField } from "./mappingConfiguration";

describe("mapping suggestions", () => {
  it.each([
    ["Šifra", "product_code"],
    ["acEAN", "ean"],
    ["Naziv", "name"],
    ["anPrice", "price"],
    ["garantni_rok", "warranty"],
  ])("maps %s to %s", (source, target) => {
    expect(suggestedTarget(source)).toBe(target);
  });

  it("does not assign the same target to multiple source fields", () => {
    const fields: AnalysisField[] = [
      { field: { id: "first", name: "EAN", data_type: "string", position: 0 }, sample_values: [] },
      { field: { id: "second", name: "barcode", data_type: "string", position: 1 }, sample_values: [] },
    ];

    expect(initialSuggestions(fields)).toEqual({ first: "ean" });
  });
});
