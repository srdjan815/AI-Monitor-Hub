export type JsonObject = Record<string, unknown>;

export interface Page<T> {
  items: T[];
  total: number;
  limit?: number;
  offset?: number;
  has_more?: boolean;
}

export interface Supplier {
  id: string;
  supplier_code: string;
  company_name: string;
  status: string;
  is_active: boolean;
  address?: string | null;
  tax_identifier?: string | null;
  registration_number?: string | null;
  version: number;
  created_at: string;
  updated_at: string;
}

export interface Source {
  id: string;
  supplier_id: string;
  source_code: string;
  name: string;
  source_type: string;
  status: string;
  is_active: boolean;
  description?: string | null;
  configuration: Record<string, unknown>;
  has_secret_reference: boolean;
  credentials_available: boolean;
  last_validation_at?: string | null;
  last_validation_status?: string | null;
  last_validation_message?: string | null;
  version: number;
  created_at: string;
  updated_at: string;
}

export interface SourceProbeResult {
  successful: boolean;
  tested_at: string;
  duration_ms: number;
  detected_format?: string | null;
  size_bytes: number;
  approximate_record_count?: number | null;
  message: string;
  steps: Array<{ label: string; successful: boolean }>;
  preview: Array<Record<string, unknown>>;
  http_status?: number | null;
  content_type?: string | null;
  checksum?: string | null;
}

export interface SupplierSchedule {
  id: string;
  source_connection_id: string;
  supplier_id?: string;
  supplier_name?: string;
  source_name?: string;
  source_code?: string;
  status: "MANUAL" | "ENABLED" | "PAUSED";
  schedule_type?: "DAILY" | "MULTI_DAILY" | "INTERVAL" | "WEEKDAYS" | "WEEKLY" | null;
  timezone: string;
  schedule_configuration: {
    times?: string[];
    weekdays?: number[];
    interval_hours?: number;
  };
  automation_depth: "FETCH_ONLY" | "FETCH_AND_ANALYZE" | "FULL_PIPELINE";
  next_run_at?: string | null;
  last_run_at?: string | null;
  last_result?: string | null;
  last_duration_ms?: number | null;
  consecutive_failures: number;
  timeout_seconds: number;
  max_attempts: number;
  version: number;
  created_at: string;
  updated_at: string;
}

export interface PipelineRunQueued {
  pipeline_run_id: string;
  pipeline_code: string;
  job_id: string;
  status: string;
  automation_depth: string;
}

export interface Operation {
  id: string;
  supplier_id: string;
  source_connection_id: string;
  status: string;
  created_at: string;
  acquisition_code?: string;
  snapshot_code?: string;
  delta_code?: string;
  incident_code?: string;
  title?: string;
  priority?: string;
  severity?: string;
  storage_state?: string;
  assigned_user_id?: string | null;
  [key: string]: unknown;
}

export interface SearchResult {
  resource_type: string;
  id: string;
  code: string;
  display_name: string;
  short_context?: string | null;
  status?: string | null;
  resource_path: string;
}

export interface PlatformCount {
  value: number | null;
  permitted: boolean;
}

export interface Overview {
  range_from: string;
  range_to: string;
  active_suppliers: PlatformCount;
  active_source_connections: PlatformCount;
  recent_acquisitions: PlatformCount;
  failed_acquisitions: PlatformCount;
  ready_snapshots: PlatformCount;
  archived_snapshots: PlatformCount;
  recent_deltas: PlatformCount;
  active_incidents: PlatformCount;
  overdue_incidents: PlatformCount;
  unassigned_incidents: PlatformCount;
  latest_operations: Array<{
    resource_type: string;
    id: string;
    code: string;
    status: string;
    occurred_at: string;
    resource_path: string;
  }>;
  recent_failures: Array<{
    resource_type: string;
    id: string;
    code: string;
    status: string;
    occurred_at: string;
    resource_path: string;
    supplier_name?: string | null;
    source_name?: string | null;
    failure_code?: string | null;
    failure_message?: string | null;
    error_count?: number | null;
  }>;
  latest_acquisition?: {
    resource_type: string;
    id: string;
    code: string;
    status: string;
    occurred_at: string;
    resource_path: string;
    supplier_name?: string | null;
    source_name?: string | null;
    failure_code?: string | null;
    failure_message?: string | null;
    error_count?: number | null;
  } | null;
  supplier_processes: Array<{
    supplier_id: string;
    supplier_name: string;
    source_id?: string | null;
    source_name?: string | null;
    source_format?: string | null;
    connection_status: string;
    schema_status: string;
    mapping_status: string;
    acquisition_status: string;
    last_success_at?: string | null;
    article_count?: number | null;
    content_changed?: boolean | null;
    warning?: string | null;
  }>;
}

export interface ApiError {
  code: string;
  message: string;
  requestId?: string;
  correlationId?: string;
  fieldErrors?: unknown[];
  status: number;
}

export interface BulkResponse {
  requested_count: number;
  succeeded_count: number;
  failed_count: number;
  skipped_count: number;
  results: Array<{
    input_reference: string;
    status: string;
    resource_id?: string;
    resource_code?: string;
    error_code?: string;
    message: string;
  }>;
}
