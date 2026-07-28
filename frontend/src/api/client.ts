import type { ApiError, JsonObject } from "../types";

const API_ROOT = "/api/v1";

let accessToken = sessionStorage.getItem("amh.access_token") ?? "";

const ROLE_PERMISSIONS: Record<string, string[]> = {
  system_admin: ["*"],
  supplier_admin: [
    "suppliers.read", "suppliers.write",
    "supplier_sources.read", "supplier_sources.write", "supplier_sources.validate",
    "schema_profiles.read", "schema_profiles.write", "schema_profiles.activate",
    "mapping_profiles.read", "mapping_profiles.write", "mapping_profiles.activate",
    "acquisitions.read", "acquisitions.execute", "acquisitions.upload", "acquisitions.cancel",
    "snapshots.read", "snapshots.create", "snapshots.verify", "snapshots.archive",
    "snapshots.offload", "snapshots.restore",
    "deltas.read", "deltas.calculate", "deltas.cancel",
    "incidents.read", "incidents.create", "incidents.acknowledge", "incidents.assign",
    "incidents.manage", "incidents.resolve", "incidents.dismiss", "incidents.suppress",
    "incidents.comment", "incident_rules.read", "incident_rules.manage",
    "supplier_platform.overview", "supplier_platform.search"
  ],
  supplier_source_validator: ["supplier_sources.read", "supplier_sources.validate"],
  schema_profile_editor: ["supplier_sources.read", "schema_profiles.read", "schema_profiles.write"],
  schema_profile_activator: ["supplier_sources.read", "schema_profiles.read", "schema_profiles.activate"],
  mapping_profile_editor: [
    "supplier_sources.read", "schema_profiles.read",
    "mapping_profiles.read", "mapping_profiles.write"
  ],
  mapping_profile_activator: [
    "supplier_sources.read", "schema_profiles.read",
    "mapping_profiles.read", "mapping_profiles.activate"
  ],
  acquisition_operator: [
    "suppliers.read", "supplier_sources.read", "schema_profiles.read",
    "mapping_profiles.read", "acquisitions.read", "acquisitions.execute",
    "acquisitions.upload", "acquisitions.cancel"
  ],
  read_only: [
    "suppliers.read", "supplier_sources.read", "schema_profiles.read",
    "mapping_profiles.read", "acquisitions.read", "snapshots.read",
    "deltas.read", "incidents.read", "incident_rules.read",
    "supplier_platform.overview", "supplier_platform.search"
  ],
  internal_service: ["*"]
};

export function setAccessToken(token: string): void {
  accessToken = token.trim().replace(/^Bearer\s+/i, "");
  if (accessToken) sessionStorage.setItem("amh.access_token", accessToken);
  else sessionStorage.removeItem("amh.access_token");
}

export function getAccessToken(): string {
  return accessToken;
}

export function decodeTokenPermissions(token = accessToken): string[] {
  try {
    const part = token.split(".")[1];
    if (!part) return [];
    const normalized = part.replace(/-/g, "+").replace(/_/g, "/");
    const payload = JSON.parse(atob(normalized)) as {
      permissions?: string[];
      roles?: string[];
    };
    const permissions = new Set(payload.permissions ?? []);
    for (const role of payload.roles ?? []) {
      for (const permission of ROLE_PERMISSIONS[role] ?? []) {
        permissions.add(permission);
      }
    }
    return [...permissions];
  } catch {
    return [];
  }
}

function correlationId(): string {
  return `ui-${crypto.randomUUID()}`;
}

function apiError(status: number, payload: any): ApiError {
  return {
    status,
    code: payload?.error?.code ?? payload?.code ?? "INTERNAL_ERROR",
    message:
      payload?.error?.message ??
      payload?.detail?.message ??
      payload?.detail ??
      "Zahtev nije uspeo",
    requestId: payload?.request_id,
    correlationId: payload?.correlation_id,
    fieldErrors: payload?.error?.field_errors
  };
}

export async function api<T>(
  path: string,
  options: Omit<RequestInit, "body"> & {
    body?: BodyInit | JsonObject | null;
  } = {}
): Promise<T> {
  const headers = new Headers(options.headers);
  headers.set("Accept", "application/json");
  headers.set("X-Correlation-ID", correlationId());
  if (accessToken) headers.set("Authorization", `Bearer ${accessToken}`);
  let body = options.body;
  if (
    body &&
    typeof body === "object" &&
    !(body instanceof Blob) &&
    !(body instanceof FormData) &&
    !(body instanceof URLSearchParams) &&
    !(body instanceof ArrayBuffer)
  ) {
    headers.set("Content-Type", "application/json");
    body = JSON.stringify(body);
  }
  const response = await fetch(
    path.startsWith("/api/") ? path : `${API_ROOT}${path}`,
    { ...options, headers, body: body as BodyInit | null | undefined }
  );
  if (!response.ok) {
    let payload: unknown = {};
    try {
      payload = await response.json();
    } catch {
      payload = { detail: response.statusText };
    }
    throw apiError(response.status, payload);
  }
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

export function queryString(
  values: Record<string, string | number | boolean | null | undefined>
): string {
  const params = new URLSearchParams();
  Object.entries(values).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== "") {
      params.set(key, String(value));
    }
  });
  const value = params.toString();
  return value ? `?${value}` : "";
}
