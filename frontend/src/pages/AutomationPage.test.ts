import { describe, expect, it } from "vitest";
import { normalizeScheduleTimes } from "./scheduleTime";

describe("normalizacija termina automatskog pokretača", () => {
  it("normalizuje sate i uklanja završnu interpunkciju", () => {
    expect(normalizeScheduleTimes("8:30, 10:00, 14:00.")).toEqual([
      "08:30",
      "10:00",
      "14:00"
    ]);
  });

  it("odbija nevažeće vreme pre slanja backendu", () => {
    expect(() => normalizeScheduleTimes("24:00")).toThrow();
    expect(() => normalizeScheduleTimes("08:7")).toThrow();
  });
});
