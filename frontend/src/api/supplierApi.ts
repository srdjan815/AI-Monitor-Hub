import { api, queryString } from "./client";
import type {
  BulkResponse,
  ArticleReview,
  Operation,
  Overview,
  Page,
  SearchResult,
  Source,
  SourceProbeResult,
  SupplierSchedule,
  SupplierCurrencySetting,
  CurrencySourceTestResult,
  SupplierExchangeRate,
  PipelineRunQueued,
  Supplier
} from "../types";

export const supplierApi = {
  get: <T>(path: string, params: Record<string, unknown> = {}) =>
    api<T>(`${path}${queryString(params as any)}`),
  overview: () => api<Overview>("/suppliers/platform/overview"),
  search: (query: string, limit = 20) =>
    api<Page<SearchResult>>(
      `/suppliers/platform/search${queryString({ query, limit })}`
    ),
  suppliers: (params: Record<string, unknown>) =>
    api<Page<Supplier>>(`/suppliers${queryString(params as any)}`),
  supplier: (id: string) => api<Supplier>(`/suppliers/${id}`),
  createSupplier: (body: Record<string, unknown>) =>
    api<Supplier>("/suppliers", { method: "POST", body }),
  updateSupplier: (id: string, body: Record<string, unknown>) =>
    api<Supplier>(`/suppliers/${id}`, { method: "PATCH", body }),
  deactivateSupplier: (id: string) =>
    api<void>(`/suppliers/${id}`, { method: "DELETE" }),
  createContact: (supplierId: string, body: Record<string, unknown>) =>
    api(`/suppliers/${supplierId}/contacts`, { method: "POST", body }),
  sources: (supplierId: string, params: Record<string, unknown>) =>
    api<Page<Source>>(
      `/suppliers/${supplierId}/sources${queryString(params as any)}`
    ),
  source: (supplierId: string, sourceId: string) =>
    api<Source>(`/suppliers/${supplierId}/sources/${sourceId}`),
  createSource: (supplierId: string, body: Record<string, unknown>) =>
    api<Source>(`/suppliers/${supplierId}/sources`, {
      method: "POST",
      body
    }),
  updateSource: (
    supplierId: string,
    sourceId: string,
    body: Record<string, unknown>
  ) =>
    api<Source>(`/suppliers/${supplierId}/sources/${sourceId}`, {
      method: "PATCH",
      body
    }),
  deactivateSource: (supplierId: string, sourceId: string) =>
    api<void>(`/suppliers/${supplierId}/sources/${sourceId}`, {
      method: "DELETE"
    }),
  validateSource: (supplierId: string, sourceId: string) =>
    api(`/suppliers/${supplierId}/sources/${sourceId}/validate`, {
      method: "POST"
    }),
  probeSource: (supplierId: string, sourceId: string) =>
    api<SourceProbeResult>(
      `/suppliers/${supplierId}/sources/${sourceId}/probe`,
      { method: "POST" }
    ),
  probeUploadedSource: (
    supplierId: string,
    sourceId: string,
    file: File
  ) =>
    api<SourceProbeResult>(
      `/suppliers/${supplierId}/sources/${sourceId}/probe-upload${queryString({
        filename: file.name
      })}`,
      {
        method: "POST",
        headers: { "Content-Type": file.type || "application/octet-stream" },
        body: file
      }
    ),
  writeSourceCredentials: (
    supplierId: string,
    sourceId: string,
    body: Record<string, unknown>
  ) =>
    api<{ configured: boolean }>(
      `/suppliers/${supplierId}/sources/${sourceId}/credentials`,
      { method: "PUT", body }
    ),
  writeSourceCertificate: (
    supplierId: string,
    sourceId: string,
    certificate: File,
    password: string
  ) =>
    certificate.arrayBuffer().then((buffer) => {
      const bytes = new Uint8Array(buffer);
      let binary = "";
      for (let offset = 0; offset < bytes.length; offset += 8192) {
        binary += String.fromCharCode(...bytes.subarray(offset, offset + 8192));
      }
      return api<{ configured: boolean }>(
        `/suppliers/${supplierId}/sources/${sourceId}/credentials`,
        {
          method: "PUT",
          body: {
            placement: "HEADER",
            password,
            certificate_base64: btoa(binary)
          }
        }
      );
    }),
  schedule: (supplierId: string, sourceId: string) =>
    api<SupplierSchedule | null>(
      `/suppliers/${supplierId}/sources/${sourceId}/schedule`
    ),
  schedules: () =>
    api<Page<SupplierSchedule>>(
      "/suppliers/platform/source-schedules?limit=500&offset=0"
    ),
  saveSchedule: (
    supplierId: string,
    sourceId: string,
    body: Record<string, unknown>
  ) =>
    api<SupplierSchedule>(
      `/suppliers/${supplierId}/sources/${sourceId}/schedule`,
      { method: "PUT", body }
    ),
  reportScheduleReadinessIncident: (supplierId: string, sourceId: string) =>
    api<Operation>(
      `/suppliers/${supplierId}/sources/${sourceId}/schedule-readiness-incident`,
      { method: "POST", body: null }
    ),
  runPipelineNow: (
    supplierId: string,
    sourceId: string,
    automationDepth: string
  ) =>
    api<PipelineRunQueued>(
      `/suppliers/${supplierId}/sources/${sourceId}/pipeline-runs`,
      {
        method: "POST",
        body: {
          automation_depth: automationDepth,
          idempotency_key: `manual:${sourceId}:${crypto.randomUUID()}`
        }
      }
    ),
  collection: <T = Operation>(
    supplierId: string,
    sourceId: string,
    resource: string,
    params: Record<string, unknown>
  ) =>
    api<Page<T>>(
      `/suppliers/${supplierId}/sources/${sourceId}/${resource}${queryString(
        params as any
      )}`
    ),
  nestedCollection: <T = Operation>(path: string, params = {}) =>
    api<Page<T>>(`${path}${queryString(params)}`),
  detail: <T = Operation>(path: string) => api<T>(path),
  mutate: <T = Operation>(
    path: string,
    method: "POST" | "PATCH" | "DELETE",
    body?: Record<string, unknown> | Blob
  ) => api<T>(path, { method, body: body ?? null }),
  incidents: (params: Record<string, unknown>) =>
    api<Page<Operation>>(
      `/suppliers/platform/incidents${queryString(params as any)}`
    ),
  incidentDetail: (id: string) =>
    api<Operation>(`/suppliers/platform/supplier-incidents/${id}`),
  incidentEvents: (id: string) =>
    api<Page<Operation>>(
      `/suppliers/platform/supplier-incidents/${id}/events`
    ),
  incidentComments: (id: string) =>
    api<Page<Operation>>(
      `/suppliers/platform/supplier-incidents/${id}/comments`
    ),
  incidentAction: (
    id: string,
    action: string,
    body?: Record<string, unknown>
  ) =>
    api<Operation>(
      `/suppliers/platform/supplier-incidents/${id}/${action}`,
      { method: "POST", body: body ?? null }
    ),
  bulkAssign: (items: Array<Record<string, unknown>>) =>
    api<BulkResponse>("/suppliers/platform/bulk/incidents/assign", {
      method: "POST",
      body: { items }
    }),
  bulkPriority: (items: Array<Record<string, unknown>>) =>
    api<BulkResponse>("/suppliers/platform/bulk/incidents/priority", {
      method: "POST",
      body: { items }
    }),
  articleReviews: (params: Record<string, unknown>) =>
    api<Page<ArticleReview>>(
      `/suppliers/platform/article-reviews${queryString(params as any)}`
    ),
  articleReview: (id: string) =>
    api<ArticleReview>(`/suppliers/platform/article-reviews/${id}`),
  decideArticleReview: (
    id: string,
    action: "approve" | "reject",
    expectedVersion: number,
    comment: string
  ) =>
    api<ArticleReview>(`/suppliers/platform/article-reviews/${id}/${action}`, {
      method: "POST",
      body: { expected_version: expectedVersion, comment }
    }),
  monitorCurrency: () =>
    api<{ currency_code: "RSD"; rate_to_rsd: string; version: number }>(
      "/suppliers/platform/supplier-currencies/monitor"
    ),
  currencySettings: () =>
    api<Page<SupplierCurrencySetting>>(
      "/suppliers/platform/supplier-currencies"
    ),
  saveCurrencySetting: (supplierId: string, body: Record<string, unknown>) =>
    api<SupplierCurrencySetting>(
      `/suppliers/platform/supplier-currencies/${supplierId}`,
      { method: "PUT", body }
    ),
  exchangeRates: (supplierId: string) =>
    api<SupplierExchangeRate[]>(
      `/suppliers/platform/supplier-currencies/${supplierId}/rates`
    ),
  addExchangeRate: (supplierId: string, body: Record<string, unknown>) =>
    api<SupplierExchangeRate>(
      `/suppliers/platform/supplier-currencies/${supplierId}/rates`,
      { method: "POST", body }
    ),
  testCurrencySource: (supplierId: string, body: Record<string, unknown>) =>
    api<CurrencySourceTestResult>(
      `/suppliers/platform/supplier-currencies/${supplierId}/test-source`,
      { method: "POST", body }
    ),
  refreshCurrencyRate: (supplierId: string) =>
    api<SupplierExchangeRate>(
      `/suppliers/platform/supplier-currencies/${supplierId}/refresh`,
      { method: "POST" }
    )
};
