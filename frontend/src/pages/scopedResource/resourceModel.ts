import type { Operation } from "../../types";

export interface ResourceConfiguration {
  resource: string;
  title: string;
  description: string;
  codeField: string;
  permissionRead: string;
  permissionWrite?: string;
  statusField?: string;
  extraColumns?: Array<{ key: string; label: string; tooltip: string }>;
  actions?: Array<{
    name: string;
    label: string;
    tooltip: string;
    permission: string;
    icon: "play" | "upload" | "cancel" | "retry";
    body?: Record<string, unknown>;
  }>;
}

export interface SchemaAnalysis {
  profile: Operation;
  original_filename?: string | null;
  detected_format: string;
  encoding?: string | null;
  delimiter?: string | null;
  header_row?: number | null;
  record_count: number;
  sampled_record_count: number;
  fields: Array<{
    field: { id: string; position: number; name: string; data_type: string; nullable: boolean };
    sample_values: string[];
    confidence: number;
  }>;
}

export interface PriceListRecord {
  manufacturer_code?: string | null;
  ean?: string | null;
  name?: string | null;
  price?: string | null;
  duplicate_count: number;
  values: Record<string, string | null>;
}

export interface PriceListRecordPage {
  items: PriceListRecord[];
  total: number;
  source_record_count: number;
}

export function isSchemaAnalysis(value: unknown): value is SchemaAnalysis {
  return Boolean(value && typeof value === "object" && "profile" in value && "fields" in value && Array.isArray((value as SchemaAnalysis).fields));
}

export function readableSupplierValue(value: string | null): string {
  if (!value) return "—";
  if (!/<[a-z][\s\S]*>/i.test(value)) return value;
  const document = new DOMParser().parseFromString(value, "text/html");
  const rows = [...document.querySelectorAll("tr")]
    .map((row) => {
      const label = row.querySelector("th")?.textContent?.trim();
      const content = row.querySelector("td")?.textContent?.trim();
      return label && content ? `${label}: ${content}` : null;
    })
    .filter((row): row is string => Boolean(row));
  if (rows.length) return rows.join("\n");
  return (document.body.textContent ?? "").replace(/\s+/g, " ").trim() || "—";
}
