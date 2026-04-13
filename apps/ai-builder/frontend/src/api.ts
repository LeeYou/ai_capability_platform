import type { ListResponse } from './types'

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
  const payload = await request<ListResponse<T>>(path)
  return payload.items
}

export function statusTone(status: string): 'good' | 'warn' | 'danger' | 'neutral' {
  if (['completed', 'ready', 'success', 'ok'].includes(status)) return 'good'
  if (['failed', 'error'].includes(status)) return 'danger'
  if (['running', 'pending', 'queued', 'created'].includes(status)) return 'warn'
  return 'neutral'
}

export function taskDeliveryDownloadUrl(taskId: number): string {
  return `${apiBaseUrl}/api/v1/build-tasks/${taskId}/delivery-package/download`
}

export function targetDownloadUrl(targetId: number): string {
  return `${apiBaseUrl}/api/v1/build-targets/${targetId}/download`
}
