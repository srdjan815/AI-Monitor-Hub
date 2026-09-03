import type { ApiError } from "../types";

export interface SupplierFormValue {
  company_name: string;
  address: string;
  tax_identifier: string;
  registration_number: string;
  status: string;
}

export function supplierPayload(form: SupplierFormValue): Record<string, unknown> {
  return {
    ...form,
    company_name: form.company_name.trim(),
    address: form.address.trim() || null,
    tax_identifier: form.tax_identifier.trim() || null,
    registration_number: form.registration_number.trim() || null
  };
}

export function supplierErrorMessage(error: ApiError): string {
  const message = error.message.toLowerCase();
  const missing: string[] = [];
  if (message.includes("tax_identifier")) missing.push("PIB");
  if (message.includes("registration_number")) missing.push("matični broj");

  if (missing.length > 0 && message.includes("at least 1 character")) {
    return missing.length === 1
      ? `${missing[0]} nije unet.`
      : `${missing.join(" i ")} nisu uneti.`;
  }
  return error.message || "Dobavljač nije sačuvan. Proverite unete podatke.";
}
