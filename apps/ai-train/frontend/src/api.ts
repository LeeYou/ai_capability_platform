import type { ApiListResponse, AnnotationSampleItem, AnnotationDraft } from './types'

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

export function prettyJson(value: unknown): string {
  return JSON.stringify(value ?? {}, null, 2)
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
    label: typeof annotation.label === 'string' ? annotation.label : '',
    note: typeof annotation.note === 'string' ? annotation.note : '',
    attributesJson: prettyJson(annotation.attributes ?? {}),
    objectsJson: prettyJson(annotation.objects ?? []),
    text: typeof annotation.text === 'string' ? annotation.text : '',
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
