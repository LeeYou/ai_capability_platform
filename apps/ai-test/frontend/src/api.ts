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

export async function fetchList<T>(path: string): Promise<ApiListResponse<T>> {
  return request<ApiListResponse<T>>(path)
}

export function statusTone(status: string): 'good' | 'warn' | 'danger' | 'neutral' {
  if (['passed', 'completed', 'ready', 'success', 'ok'].includes(status)) return 'good'
  if (['failed', 'error', 'rejected'].includes(status)) return 'danger'
  if (['running', 'pending', 'queued', 'created'].includes(status)) return 'warn'
  return 'neutral'
}

export function parseBatchCases(raw: string): Array<{ case_name: string; input_path: string; expected_output?: string }> {
  return raw
    .split('\n')
    .map((line) => line.trim())
    .filter(Boolean)
    .map((line) => {
      const [case_name, input_path, expected_output] = line.split('|')
      return {
        case_name: case_name.trim(),
        input_path: input_path.trim(),
        expected_output: expected_output?.trim() || undefined,
      }
    })
}
