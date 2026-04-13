import type { ApiListResponse, AnnotationSampleItem, AnnotationDraft } from './types'

export const apiBaseUrl = import.meta.env.VITE_API_BASE_URL ?? ''
export const emptyAnnotationDraft: AnnotationDraft = {
  label: '',
  note: '',
  attributesJson: '{}',
  objectsJson: '[]',
  text: '',
  regionsJson: '[]',
  fieldsJson: '{}',
  confidenceJson: '{}',
}

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
    let detail = ''
    try {
      const parsed = JSON.parse(message) as { detail?: string }
      detail = parsed.detail ?? ''
    } catch {
      detail = ''
    }
    throw new Error(detail || message || `请求失败：${path}`)
  }
  if (response.status === 204) {
    return undefined as T
  }
  const payload = await response.text()
  if (!payload.trim()) {
    return undefined as T
  }
  return JSON.parse(payload) as T
}

export async function fetchList<T>(path: string): Promise<T[]> {
  const payload = await request<ApiListResponse<T>>(path)
  return payload.items
}

export function prettyJson(value: unknown): string {
  return JSON.stringify(value ?? {}, null, 2)
}

export function formatDateTime(value?: string | null): string {
  if (!value) return '-'
  const parsed = new Date(value)
  if (Number.isNaN(parsed.getTime())) return value
  return parsed.toLocaleString('zh-CN')
}

export function formatFileSize(bytes?: number): string {
  if (bytes == null || bytes <= 0) return '0 B'
  if (bytes >= 1024 * 1024 * 1024) return `${(bytes / 1024 / 1024 / 1024).toFixed(2)} GB`
  if (bytes >= 1024 * 1024) return `${(bytes / 1024 / 1024).toFixed(2)} MB`
  if (bytes >= 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${bytes} B`
}

export function statusTone(status: string): 'good' | 'warn' | 'danger' | 'neutral' {
  if (['completed', 'ready', 'submitted', 'success'].includes(status)) return 'good'
  if (['failed', 'error'].includes(status)) return 'danger'
  if (['running', 'pending', 'created', 'draft'].includes(status)) return 'warn'
  return 'neutral'
}

export function extractDraft(sample: AnnotationSampleItem): AnnotationDraft {
  const annotation = sample.annotation ?? {}
  return {
    ...emptyAnnotationDraft,
    label: typeof annotation.label === 'string' ? annotation.label : emptyAnnotationDraft.label,
    note: typeof annotation.note === 'string' ? annotation.note : emptyAnnotationDraft.note,
    attributesJson: prettyJson(annotation.attributes ?? {}),
    objectsJson: prettyJson(annotation.objects ?? []),
    text: typeof annotation.text === 'string' ? annotation.text : emptyAnnotationDraft.text,
    regionsJson: prettyJson(annotation.regions ?? []),
    fieldsJson: prettyJson(annotation.fields ?? {}),
    confidenceJson: prettyJson(annotation.confidence ?? {}),
  }
}

export function parseJsonInput(raw: string, fallback: unknown): unknown {
  const normalized = raw.trim()
  if (!normalized) return fallback
  return JSON.parse(normalized) as unknown
}

export function buildAnnotationPayload(sampleId: string, draft: AnnotationDraft, taskType: string): Record<string, unknown> | null {
  if (taskType === 'classification') {
    if (!draft.label.trim()) return null
    return {
      sample_id: sampleId,
      label: draft.label.trim(),
      note: draft.note.trim(),
      attributes: parseJsonInput(draft.attributesJson, {}),
    }
  }
  if (taskType === 'detection') {
    const objects = parseJsonInput(draft.objectsJson, [])
    if (!Array.isArray(objects) || objects.length === 0) return null
    return {
      sample_id: sampleId,
      objects,
      note: draft.note.trim(),
    }
  }
  if (taskType === 'ocr') {
    if (!draft.text.trim()) return null
    return {
      sample_id: sampleId,
      text: draft.text.trim(),
      regions: parseJsonInput(draft.regionsJson, []),
      note: draft.note.trim(),
    }
  }
  const fields = parseJsonInput(draft.fieldsJson, {})
  if (typeof fields !== 'object' || fields == null || Array.isArray(fields) || Object.keys(fields).length === 0) {
    return null
  }
  return {
    sample_id: sampleId,
    fields,
    confidence: parseJsonInput(draft.confidenceJson, {}),
    note: draft.note.trim(),
  }
}
