import type { Source } from "../../types";

export function displayMethod(source: Source): string {
  if (source.source_type === "HTTP") return "Direktan URL";
  if (source.configuration.authentication_type === "PORTAL_FORM") return "Portal sa prijavom";
  if (source.source_type === "API") return "API / zaštićeni URL";
  if (source.source_type === "MANUAL_UPLOAD") return "Ručno učitavanje";
  return source.source_type;
}

export function displayFormat(source: Source): string {
  const configured = source.configuration.expected_content_type;
  if (typeof configured === "string") return configured;
  const accepted = source.configuration.accepted_file_types;
  if (Array.isArray(accepted)) return accepted.join(", ");
  return ["CSV", "EXCEL", "XML"].includes(source.source_type) ? source.source_type : "Automatski";
}

export function formatDate(value: unknown): string {
  return typeof value === "string" ? new Intl.DateTimeFormat("sr-RS", { dateStyle: "medium", timeStyle: "short" }).format(new Date(value)) : "Nije dostupno";
}

export function detailValue(value: unknown, reason: string): string {
  return value === null || value === undefined || value === "" ? reason : String(value);
}
