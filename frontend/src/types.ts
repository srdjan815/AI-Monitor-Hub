export type JsonObject = Record<string, unknown>;

export interface Page<T> {
  items: T[];
  total: number;
  limit?: number;
  offset?: number;
  has_more?: boolean;
}

export interface ArticleReview {
  id: string;
  supplier_id: string;
  supplier_name: string;
  source_connection_id: string;
  source_name: string;
  delta_run_id: string;
  delta_code: string;
  delta_item_id: string;
  product_code: string;
  ean?: string | null;
  status: string;
  severity: string;
  issue_codes: string[];
  control_details: Record<string, unknown>;
  previous_data?: Record<string, unknown> | null;
  current_data?: Record<string, unknown> | null;
  field_changes: Array<Record<string, unknown>>;
  decision_comment?: string | null;
  decided_by?: string | null;
  opened_at: string;
  decided_at?: string | null;
  version: number;
}

export interface EolSupplierPresence {
  supplier_id: string;
  supplier_name: string;
  product_code: string;
  last_seen_at: string;
  is_currently_offered: boolean;
}

export interface EolCandidate {
  identity_key: string;
  ean?: string | null;
  product_name?: string | null;
  last_seen_at: string;
  inactive_days: number;
  status: "EOL_CANDIDATE" | "MARKED_FOR_DEACTIVATION" | "DEACTIVATED";
  export_batch_code?: string | null;
  export_eligible: boolean;
  suppliers: EolSupplierPresence[];
}

export interface EolCandidatePage {
  items: EolCandidate[];
  total: number;
  inactivity_months: number;
  cutoff_at: string;
}

export interface EolDeactivationBatch {
  id: string;
  batch_code: string;
  status: string;
  inactivity_months: number;
  target_systems: string[];
  item_count: number;
  created_by: string;
  created_at: string;
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
  portal_supplier_code?: string | null;
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
  schedule_type?:
    | "DAILY"
    | "MULTI_DAILY"
    | "INTERVAL"
    | "WEEKDAYS"
    | "WEEKLY"
    | null;
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

export interface SupplierCurrencySetting {
  id: string;
  supplier_id: string;
  supplier_name: string;
  source_connection_id?: string | null;
  source_name?: string | null;
  portal_supplier_code?: string | null;
  currency_code: string;
  currency_source: "CONFIGURED" | "PRICE_LIST";
  rate_mode: "FIXED" | "MANUAL" | "AUTOMATIC";
  automatic_source_url?: string | null;
  extraction_method:
    | "JSON_PATH"
    | "CSS_SELECTOR"
    | "XPATH"
    | "REGEX"
    | "TEXT_LABEL";
  extraction_expression?: string | null;
  fallback_extraction_method?:
    | "JSON_PATH"
    | "CSS_SELECTOR"
    | "XPATH"
    | "REGEX"
    | "TEXT_LABEL"
    | null;
  fallback_extraction_expression?: string | null;
  decimal_separator: "." | ",";
  daily_check_time: string;
  next_check_at?: string | null;
  last_check_at?: string | null;
  last_check_status?: string | null;
  last_check_message?: string | null;
  max_rate_age_hours: number;
  current_rate?: string | null;
  current_rate_effective_at?: string | null;
  rate_status: "CURRENT" | "STALE" | "MISSING";
  version: number;
}

export interface SupplierExchangeRate {
  id: string;
  rate_to_rsd: string;
  effective_at: string;
  status: string;
  source_type: string;
  evidence_checksum?: string | null;
  source_excerpt?: string | null;
  source_content_type?: string | null;
  note?: string | null;
  created_by: string;
  created_at: string;
}

export interface CurrencySourceTestResult {
  rate_to_rsd: string;
  fetched_at: string;
  source_excerpt: string;
  evidence_checksum: string;
  content_type: string;
  previous_rate?: string | null;
  difference_percent?: string | null;
  extraction_method_used: string;
}

export interface SystemCapacity {
  total_bytes: number | null;
  used_bytes: number | null;
  free_bytes: number | null;
  used_percent: number | null;
  status: "OK" | "UPOZORENJE" | "KRITIČNO" | "NEPOZNATO";
}

export interface SystemInventory {
  runtime: {
    processor_count: number;
    processor_load_percent: number | null;
    memory: SystemCapacity;
    disk: SystemCapacity;
    measured_at: string;
  };
  database_size_bytes: number;
  categories: Array<{
    code: string;
    label: string;
    size_bytes: number;
    file_count: number;
    status: "OK" | "UPOZORENJE" | "KRITIČNO" | "NEPOZNATO";
    cleanup_allowed: boolean;
    protection_reason?: string | null;
    scan_truncated: boolean;
  }>;
}

export interface CleanupPreview {
  category: "LOGOVI" | "PRIVREMENI_FAJLOVI";
  older_than_days: number;
  candidate_files: number;
  candidate_bytes: number;
  expires_at: string;
  confirmation_token: string;
}

export interface CleanupAudit {
  id: string;
  category: string;
  older_than_days: number;
  status: string;
  deleted_files: number;
  deleted_bytes: number;
  actor_id: string;
  error_message?: string | null;
  created_at: string;
}

export interface ArtifactArchiveSetting {
  id: string;
  backend_type: "MOUNT";
  display_name: string;
  relative_path: string;
  enabled: boolean;
  local_retention_days: number;
  last_tested_at?: string | null;
  last_test_status?: string | null;
  last_test_message?: string | null;
  version: number;
}

export interface ArtifactArchiveStatus {
  setting?: ArtifactArchiveSetting | null;
  pending_transfers: number;
  verified_transfers: number;
  failed_transfers: number;
  verified_bytes: number;
  duplicate_artifacts: number;
  duplicate_bytes: number;
}

export interface RetentionPolicy {
  source_connection_id: string;
  supplier_name: string;
  source_name: string;
  enabled: boolean;
  configured: boolean;
  staging_retention_days: number;
  snapshot_online_days: number;
  minimum_online_snapshots: number;
  cleanup_batch_size: number;
  version: number | null;
}

export interface RetentionPreview {
  run_id: string;
  source_connection_id: string;
  staging_cutoff: string;
  snapshot_cutoff: string;
  candidate_staging_rows: number;
  candidate_staging_bytes: number;
  referenced_staging_rows: number;
  candidate_snapshots: number;
  candidate_snapshot_items: number;
  candidate_snapshot_bytes: number;
  observations_preserved: number;
  snapshots_ready_for_offload: number;
  snapshots_requiring_archive: number;
  protected_snapshots: number;
  execution_allowed: boolean;
  blockers: string[];
  created_at: string;
}

export interface RetentionRun {
  id: string;
  source_connection_id: string;
  source_name: string;
  status: string;
  staging_cutoff: string;
  snapshot_cutoff: string;
  candidate_staging_rows: number;
  candidate_snapshots: number;
  preserved_observations: number;
  deleted_staging_rows: number;
  offloaded_snapshot_items: number;
  created_by: string;
  created_at: string;
  completed_at: string | null;
  failure_message: string | null;
}
