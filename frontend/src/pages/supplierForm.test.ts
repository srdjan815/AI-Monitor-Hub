import { describe, expect, it } from "vitest";
import { supplierErrorMessage, supplierPayload } from "./supplierForm";

describe("supplier form", () => {
  it("sends empty optional identifiers as null", () => {
    expect(
      supplierPayload({
        company_name: "  Novi dobavljač  ",
        address: " ",
        tax_identifier: "",
        registration_number: "   ",
        status: "ACTIVE"
      })
    ).toEqual({
      company_name: "Novi dobavljač",
      address: null,
      tax_identifier: null,
      registration_number: null,
      status: "ACTIVE"
    });
  });

  it("keeps and trims entered identifiers", () => {
    const payload = supplierPayload({
      company_name: "Dobavljač",
      address: " Adresa 1 ",
      tax_identifier: " 123 ",
      registration_number: " 456 ",
      status: "ACTIVE"
    });
    expect(payload.tax_identifier).toBe("123");
    expect(payload.registration_number).toBe("456");
  });

  it("translates identifier validation errors", () => {
    expect(
      supplierErrorMessage({
        status: 422,
        code: "VALIDATION_ERROR",
        message:
          "tax_identifier: String should have at least 1 character; registration_number: String should have at least 1 character"
      })
    ).toBe("PIB i matični broj nisu uneti.");
  });
});
