import { describe, expect, it } from "vitest";
import { archivePathError, operationErrorMessage } from "./artifactArchiveValidation";

describe("archivePathError", () => {
  it.each(["C:\\arhiv", "D:/archive", "/archive", "\\\\server\\share"])(
    "odbija apsolutnu putanju %s",
    (value) => expect(archivePathError(value)).toContain("relativnu putanju")
  );

  it("odbija izlazak iz montiranog korena", () => {
    expect(archivePathError("cenovnici/../tajne")).toContain("'..'");
  });

  it("prihvata bezbedne relativne podfoldere", () => {
    expect(archivePathError("cenovnici")).toBeNull();
    expect(archivePathError("cenovnici/2026")).toBeNull();
  });
});

describe("operationErrorMessage", () => {
  it("prikazuje poruku API greške koja nije Error instanca", () => {
    expect(operationErrorMessage({ message: "Putanja nije dozvoljena" })).toBe("Putanja nije dozvoljena");
  });
});
