export type StatusTone = 'good' | 'warn' | 'danger' | 'neutral'

const GOOD_STATUSES = new Set([
  'completed', 'ready', 'success', 'ok', 'active', 'issued', 'valid', 'passed', 'submitted',
])
const DANGER_STATUSES = new Set([
  'failed', 'error', 'rejected', 'denied', 'offline', 'isolated', 'disabled', 'expired',
])
const WARN_STATUSES = new Set([
  'running', 'pending', 'queued', 'created', 'draft',
])

export function statusTone(status: string): StatusTone {
  if (GOOD_STATUSES.has(status)) return 'good'
  if (DANGER_STATUSES.has(status)) return 'danger'
  if (WARN_STATUSES.has(status)) return 'warn'
  return 'neutral'
}
