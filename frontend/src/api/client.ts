import type { ApiError, JsonObject } from "../types";

const API_ROOT = "/api/v1";

export const AUTHENTICATION_FAILED_EVENT = "amh:authentication-failed";

function correlationId(): string {
  return `ui-${crypto.randomUUID()}`;
}

function apiError(status: number, payload: any): ApiError {
  const rawMessage =
    payload?.error?.message ??
    payload?.detail?.message ??
    payload?.detail ??
    "Zahtev nije uspeo";
  const message = Array.isArray(rawMessage)
    ? rawMessage
        .map((item) =>
          typeof item?.msg === "string"
            ? `${Array.isArray(item.loc) ? item.loc.slice(1).join(".") : "polje"}: ${item.msg}`
            : JSON.stringify(item)
        )
        .join("; ")
    : typeof rawMessage === "string"
      ? rawMessage
      : JSON.stringify(rawMessage);
  return {
    status,
    code: payload?.error?.code ?? payload?.code ?? "INTERNAL_ERROR",
    message,
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
  let response: Response;
  try {
    response = await fetch(
      path.startsWith("/api/") ? path : `${API_ROOT}${path}`,
      { ...options, headers, body: body as BodyInit | null | undefined, credentials: "same-origin" }
    );
  } catch {
    throw {
      status: 0,
      code: "API_UNAVAILABLE",
      message: "API još nije spreman ili server nije dostupan."
    } satisfies ApiError;
  }
  if (!response.ok) {
    let payload: unknown = {};
    try {
      payload = await response.json();
    } catch {
      payload = { detail: response.statusText };
    }
    const error = apiError(response.status, payload);
    if (response.status === 401) {
      window.dispatchEvent(new CustomEvent(AUTHENTICATION_FAILED_EVENT));
    }
    throw error;
  }
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

export async function createSession(token: string): Promise<void> {
  await api<void>("/auth/session", { method: "POST", body: { token } });
}

export async function deleteSession(): Promise<void> {
  await api<void>("/auth/session", { method: "DELETE" });
}

export async function downloadApiFile(path: string, fallbackFilename: string): Promise<void> {
  const response = await fetch(path.startsWith("/api/") ? path : `${API_ROOT}${path}`, {
    credentials: "same-origin",
    headers: { Accept: "application/octet-stream", "X-Correlation-ID": correlationId() }
  });
  if (!response.ok) {
    let payload: unknown = {};
    try {
      payload = await response.json();
    } catch {
      payload = { detail: response.statusText };
    }
    throw apiError(response.status, payload);
  }
  const disposition = response.headers.get("Content-Disposition") ?? "";
  const encoded = disposition.match(/filename\*=UTF-8''([^;]+)/i)?.[1];
  const plain = disposition.match(/filename="?([^";]+)"?/i)?.[1];
  let filename = fallbackFilename;
  try {
    filename = encoded ? decodeURIComponent(encoded) : plain || fallbackFilename;
  } catch {
    filename = fallbackFilename;
  }
  const url = URL.createObjectURL(await response.blob());
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
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
