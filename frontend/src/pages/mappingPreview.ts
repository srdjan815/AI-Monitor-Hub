export interface MappingPreviewRecord {
  values: Record<string, string | null>;
}

export function mappingFieldPreview(
  record: MappingPreviewRecord | null,
  fieldName: string,
  sampleValues: string[]
): string {
  if (record) {
    const value = record.values[fieldName];
    return value == null || value === "" ? "—" : value;
  }

  return sampleValues.slice(0, 3).join(" · ") || "—";
}

export function mappingFieldValue(
  record: MappingPreviewRecord | null,
  fieldName: string,
  sampleValues: string[]
): string {
  if (record) return record.values[fieldName] ?? "";
  return sampleValues[0] ?? "";
}
