import { describe, expect, it } from "vitest";

import { mappingFieldPreview, mappingFieldValue } from "./mappingPreview";

const selected = {
  values: {
    NAME: "Izabrani artikal",
    DESCRIPTION: null,
    EMPTY: ""
  }
};

describe("mapping preview isolation", () => {
  it("shows values only from the selected record", () => {
    expect(mappingFieldPreview(selected, "NAME", ["Nasumični artikal"]))
      .toBe("Izabrani artikal");
  });

  it("does not fall back to another record when selected value is missing", () => {
    expect(mappingFieldPreview(selected, "DESCRIPTION", ["Tuđi opis"]))
      .toBe("—");
    expect(mappingFieldPreview(selected, "EMPTY", ["Tuđi opis"]))
      .toBe("—");
    expect(mappingFieldValue(selected, "DESCRIPTION", ["Tuđi opis"]))
      .toBe("");
  });

  it("keeps schema samples before a record is selected", () => {
    expect(mappingFieldPreview(null, "DESCRIPTION", ["Prvi", "Drugi"]))
      .toBe("Prvi · Drugi");
    expect(mappingFieldValue(null, "DESCRIPTION", ["Prvi", "Drugi"]))
      .toBe("Prvi");
  });
});
