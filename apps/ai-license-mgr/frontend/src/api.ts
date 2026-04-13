import type { ApiListResponse } from './types'

export const apiBaseUrl = import.meta.env.VITE_API_BASE_URL ?? ''

export async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${apiBaseUrl}${path}`, {
    headers: {
      'Content-Type': 'application/json',
      ...(init?.headers ?? {}),
    },
    ...init,
  })
  if (!response.ok) {
    const message = await response.text()
    throw new Error(message || `请求失败：${path}`)
  }
  return (await response.json()) as T
}

export async function fetchList<T>(path: string): Promise<T[]> {
  const payload = await request<ApiListResponse<T>>(path)
  return payload.items
}

export function statusTone(status: string): 'good' | 'warn' | 'danger' | 'neutral' {
  if (['active', 'issued', 'valid', 'ready', 'completed'].includes(status)) return 'good'
  if (['isolated', 'disabled', 'failed', 'expired'].includes(status)) return 'danger'
  if (['draft', 'pending', 'created'].includes(status)) return 'warn'
  return 'neutral'
}

export function issueExportUrl(issueRecordId: number, format: 'bin' | 'pubkey'): string {
  return `${apiBaseUrl}/api/v1/license-issues/${issueRecordId}/export?export_format=${format}`
}

export function toolExportUrl(releaseId: number, format: 'archive' | 'manifest' | 'readme' | 'diagnostics' | 'vectors'): string {
  return `${apiBaseUrl}/api/v1/tool-releases/${releaseId}/export?export_format=${format}`
}
