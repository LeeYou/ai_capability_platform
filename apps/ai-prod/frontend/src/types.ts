export type CapabilityItem = {
  capability_name: string
  plugin_target: string
  model_version: string
  backend_type: string
  active_source: string
  device_mode: string
  pool_size: number
  revision_id: number | null
}

export type LicenseStatus = {
  valid: boolean
  reason: string
  result: string
  code: string
  stage: string
  details: Record<string, unknown>
  diagnostics_version: string
  checked_at_cst: string
  customer_code: string | null
  capability_scope: string[]
  version_constraints: Record<string, unknown>
  hardware_fingerprint: string | null
  runtime_revision_id: number | null
}

export type RuntimeRevisionItem = {
  revision_id: number
  revision_token: string
  action: string
  status: string
  license_valid: boolean
  capability_names: string[]
  source_summary: Record<string, unknown>
  detail: Record<string, unknown>
  rollback_of_revision_id: number | null
  created_at: string | null
}

export type RuntimeOperationItem = {
  operation_id: number
  action: string
  status: string
  detail: Record<string, unknown>
  revision_id: number | null
  created_at: string | null
}

export type InferResponse = {
  request_id: string
  capability_name: string
  model_version: string
  backend_type: string
  plugin_target: string
  device: string
  runtime_revision_id: number
  license_valid: boolean
  result: Record<string, unknown>
}

export type AuditLogItem = {
  happened_at_cst: string
  action: string
  entity_type: string
  entity_id: string
  detail: Record<string, unknown>
}

export type ListResponse<T> = { items: T[] }

export type HealthResponse = {
  status: string
  runtime_revision_id: number | null
  capability_count: number
  license_valid: boolean
}

export type RuntimeMetrics = {
  uptime_seconds: number
  active_request_count: number
  runtime_revision_id: number | null
  pool_summary: {
    capability_count: number
    total_pool_slots: number
    busy_pool_slots: number
    pending_request_count: number
    idle_pool_slots: number
    utilization_ratio: number
  }
  request_summary: {
    capability_total_requests: number
    capability_failed_requests: number
    queued_request_count: number
    avg_queue_wait_ms: number
    max_queue_wait_ms: number
    busy_reject_count: number
    queue_timeout_count: number
  }
  endpoint_metrics: Record<string, { total_requests: number; successful_requests: number; failed_requests: number; p95_latency_ms: number }>
}

export type DashboardState = {
  health: HealthResponse | null
  capabilities: CapabilityItem[]
  licenseStatus: LicenseStatus | null
  runtimeMetrics: RuntimeMetrics | null
  revisions: RuntimeRevisionItem[]
  operations: RuntimeOperationItem[]
  auditLogs: AuditLogItem[]
}
