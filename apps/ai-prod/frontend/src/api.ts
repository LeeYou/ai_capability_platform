import type {
  HealthResponse,
  ListResponse,
  CapabilityItem,
  LicenseStatus,
  RuntimeMetrics,
  RuntimeRevisionItem,
  RuntimeOperationItem,
  AuditLogItem,
  DashboardState,
  InferResponse,
} from './types'

export const runtimeApiPrefix = '/api/v1'
export const internalApiPrefix = '/internal'
export const runtimeApiBaseUrl = import.meta.env.VITE_RUNTIME_API_BASE_URL ?? ''
export const internalApiBaseUrl = import.meta.env.VITE_INTERNAL_API_BASE_URL ?? ''

export const initialState: DashboardState = {
  health: null,
  capabilities: [],
  licenseStatus: null,
  runtimeMetrics: null,
  revisions: [],
  operations: [],
  auditLogs: [],
}

export async function fetchJson<T>(baseUrl: string, path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${baseUrl}${path}`, {
    headers: {
      'Content-Type': 'application/json',
      ...(options?.headers ?? {}),
    },
    ...options,
  })
  if (!response.ok) {
    const message = await response.text()
    throw new Error(message || `请求失败：${path}`)
  }
  return (await response.json()) as T
}

export function statusTone(status: string): 'good' | 'warn' | 'danger' | 'neutral' {
  if (['ok', 'completed', 'active', 'ready', 'success'].includes(status)) return 'good'
  if (['failed', 'error', 'denied', 'offline'].includes(status)) return 'danger'
  if (['running', 'pending', 'created'].includes(status)) return 'warn'
  return 'neutral'
}

export async function loadDashboard(): Promise<DashboardState> {
  const [health, capabilities, licenseStatus, runtimeMetrics, revisions, operations, auditLogs] = await Promise.all([
    fetchJson<HealthResponse>(runtimeApiBaseUrl, `${runtimeApiPrefix}/health`),
    fetchJson<ListResponse<CapabilityItem>>(runtimeApiBaseUrl, `${runtimeApiPrefix}/capabilities`),
    fetchJson<LicenseStatus>(runtimeApiBaseUrl, `${runtimeApiPrefix}/license/status`),
    fetchJson<RuntimeMetrics>(runtimeApiBaseUrl, `${runtimeApiPrefix}/admin/metrics`),
    fetchJson<ListResponse<RuntimeRevisionItem>>(internalApiBaseUrl, `${internalApiPrefix}/admin/revisions`),
    fetchJson<ListResponse<RuntimeOperationItem>>(internalApiBaseUrl, `${internalApiPrefix}/admin/operations`),
    fetchJson<ListResponse<AuditLogItem>>(internalApiBaseUrl, `${internalApiPrefix}/audit-logs?limit=8`),
  ])
  return {
    health,
    capabilities: capabilities.items,
    licenseStatus,
    runtimeMetrics,
    revisions: revisions.items,
    operations: operations.items,
    auditLogs: auditLogs.items,
  }
}

export async function runInfer(
  capabilityName: string,
  inputType: string,
  payload: string,
  preferDevice: string,
): Promise<InferResponse> {
  return fetchJson<InferResponse>(runtimeApiBaseUrl, `${runtimeApiPrefix}/infer/${capabilityName}`, {
    method: 'POST',
    body: JSON.stringify({
      input_type: inputType,
      payload,
      prefer_device: preferDevice,
      options: {},
    }),
  })
}

export async function runtimeAction(action: 'reload' | 'rollback', targetRevisionId?: number): Promise<void> {
  await fetchJson(runtimeApiBaseUrl, `${runtimeApiPrefix}/admin/reload`, {
    method: 'POST',
    body: JSON.stringify({
      action,
      target_revision_id: targetRevisionId,
    }),
  })
}
