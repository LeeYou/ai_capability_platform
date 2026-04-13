import type {
  AuditLogItem,
  CapabilityItem,
  DashboardState,
  InferResponse,
  LicenseStatus,
  RuntimeMetrics,
  RuntimeRevisionItem,
} from './types'

export type EnterpriseTone = 'good' | 'warn' | 'danger' | 'neutral'

export type EnterpriseChecklistItem = {
  label: string
  detail: string
  done: boolean
}

export type EnterpriseStageCard = {
  title: string
  score: number
  count: number
  detail: string
  tone: EnterpriseTone
}

export type EnterpriseRiskItem = {
  title: string
  detail: string
  tone: EnterpriseTone
}

export function clampScore(value: number): number {
  return Math.max(0, Math.min(100, Math.round(value)))
}

export function scoreTone(score: number): EnterpriseTone {
  if (score >= 85) return 'good'
  if (score >= 60) return 'warn'
  return 'danger'
}

function getRecordTimestamp(value?: string | null): number {
  if (!value) return Number.NEGATIVE_INFINITY
  const timestamp = new Date(value).getTime()
  return Number.isNaN(timestamp) ? Number.NEGATIVE_INFINITY : timestamp
}

export function maxEndpointP95(metrics: RuntimeMetrics | null): number {
  return Math.max(...Object.values(metrics?.endpoint_metrics ?? {}).map((item) => item.p95_latency_ms), 0)
}

export function buildOverviewInsights(dashboard: DashboardState): {
  overallScore: number
  stageCards: EnterpriseStageCard[]
  blockers: EnterpriseRiskItem[]
  actions: string[]
  latestOperations: DashboardState['operations']
  highlightedCapabilities: CapabilityItem[]
} {
  const serviceScore = dashboard.health?.status === 'ok' ? 100 : 25
  const licenseScore = dashboard.licenseStatus == null ? 0 : dashboard.licenseStatus.valid ? 100 : 20
  const queuePenalty = (dashboard.runtimeMetrics?.request_summary.queue_timeout_count ?? 0) * 12 + (dashboard.runtimeMetrics?.request_summary.busy_reject_count ?? 0) * 10 + (dashboard.runtimeMetrics?.request_summary.queued_request_count ?? 0) * 4
  const queueScore = clampScore(100 - queuePenalty)
  const revisionScore = dashboard.health?.runtime_revision_id != null && dashboard.revisions.length > 0 ? 100 : 40
  const overallScore = clampScore(serviceScore * 0.3 + licenseScore * 0.25 + queueScore * 0.25 + revisionScore * 0.2)
  const latestOperations = [...dashboard.operations].sort((left, right) => getRecordTimestamp(right.created_at) - getRecordTimestamp(left.created_at)).slice(0, 5)
  const highlightedCapabilities = [...dashboard.capabilities]
    .sort((left, right) => {
      if ((right.pool_size ?? 0) !== (left.pool_size ?? 0)) return right.pool_size - left.pool_size
      return left.capability_name.localeCompare(right.capability_name)
    })
    .slice(0, 5)

  return {
    overallScore,
    stageCards: [
      {
        title: '服务可用性',
        score: clampScore(serviceScore),
        count: dashboard.health?.capability_count ?? 0,
        detail: `${dashboard.health?.status ?? 'unknown'} / ${dashboard.health?.capability_count ?? 0} 个能力在线`,
        tone: scoreTone(serviceScore),
      },
      {
        title: '授权状态',
        score: clampScore(licenseScore),
        count: dashboard.licenseStatus?.valid ? 1 : 0,
        detail: `${dashboard.licenseStatus?.code ?? 'unknown'} / ${dashboard.licenseStatus?.stage ?? 'unknown'}`,
        tone: scoreTone(licenseScore),
      },
      {
        title: '队列健康',
        score: clampScore(queueScore),
        count: dashboard.runtimeMetrics?.request_summary.queued_request_count ?? 0,
        detail: `timeout ${dashboard.runtimeMetrics?.request_summary.queue_timeout_count ?? 0} / reject ${dashboard.runtimeMetrics?.request_summary.busy_reject_count ?? 0}`,
        tone: scoreTone(queueScore),
      },
      {
        title: '版本闭环',
        score: clampScore(revisionScore),
        count: dashboard.revisions.length,
        detail: `${dashboard.revisions.length} 个 revision / 当前 ${dashboard.health?.runtime_revision_id ?? '-'}`,
        tone: scoreTone(revisionScore),
      },
    ],
    blockers: [
      {
        title: 'License 阻塞',
        detail: dashboard.licenseStatus?.valid ? '当前授权状态正常' : `当前受限：${dashboard.licenseStatus?.code ?? 'unknown'}`,
        tone: dashboard.licenseStatus?.valid ? 'good' : 'danger',
      },
      {
        title: '排队风险',
        detail: (dashboard.runtimeMetrics?.request_summary.queue_timeout_count ?? 0) > 0 ? `${dashboard.runtimeMetrics?.request_summary.queue_timeout_count ?? 0} 次 queue timeout` : '当前无 queue timeout',
        tone: (dashboard.runtimeMetrics?.request_summary.queue_timeout_count ?? 0) > 0 ? 'warn' : 'good',
      },
      {
        title: '在线能力',
        detail: dashboard.capabilities.length > 0 ? `${dashboard.capabilities.length} 个能力已装载` : '当前无在线能力',
        tone: dashboard.capabilities.length > 0 ? 'good' : 'danger',
      },
    ],
    actions: [
      '先在首页确认 license、revision 与排队风险，再进入在线验证与高风险控制。',
      '若存在 queue timeout 或 busy reject，优先进入监控诊断页查看 admission/source_summary。',
      '在线验证通过后，再执行 reload / rollback，并保留 revision 与审计留痕。',
    ],
    latestOperations,
    highlightedCapabilities,
  }
}

export function buildVerifyChecklist(params: {
  selectedCapability: CapabilityItem | null
  payload: string
  inputType: string
  licenseStatus: LicenseStatus | null
  inferResult: InferResponse | null
  jsonPayloadValid: boolean
}): EnterpriseChecklistItem[] {
  return [
    {
      label: '能力已选择',
      detail: params.selectedCapability ? `${params.selectedCapability.capability_name} / revision ${params.selectedCapability.revision_id ?? '-'}` : '尚未选择能力',
      done: params.selectedCapability != null,
    },
    {
      label: '载荷可提交',
      detail: params.inputType === 'json' ? (params.jsonPayloadValid ? 'JSON 语法有效' : 'JSON 语法无效') : (params.payload.trim() ? '已提供输入载荷' : '尚未填写输入载荷'),
      done: params.inputType === 'json' ? params.jsonPayloadValid : params.payload.trim().length > 0,
    },
    {
      label: '授权可执行',
      detail: params.licenseStatus ? `${params.licenseStatus.code} / ${params.licenseStatus.stage}` : '尚未加载授权状态',
      done: params.licenseStatus?.valid === true,
    },
    {
      label: '结果可留痕',
      detail: params.inferResult ? `request ${params.inferResult.request_id}` : '尚未执行在线验证',
      done: params.inferResult != null,
    },
  ]
}

export function buildControlChecklist(revision: RuntimeRevisionItem | null): EnterpriseChecklistItem[] {
  if (!revision) return []
  return [
    {
      label: '已选中 revision',
      detail: `revision #${revision.revision_id}`,
      done: true,
    },
    {
      label: '影响能力已识别',
      detail: `${revision.capability_names.length} 个能力`,
      done: revision.capability_names.length > 0,
    },
    {
      label: '授权状态已明确',
      detail: revision.license_valid ? '当前 revision 授权有效' : '当前 revision 授权受限',
      done: revision.license_valid,
    },
    {
      label: 'revision 已达可决策状态',
      detail: revision.status,
      done: ['active', 'completed', 'ready'].includes(revision.status),
    },
  ]
}

export function buildRevisionRiskItems(revision: RuntimeRevisionItem | null): EnterpriseRiskItem[] {
  if (!revision) return []
  return [
    {
      title: '授权风险',
      detail: revision.license_valid ? '当前 revision 授权有效' : '当前 revision 授权受限',
      tone: revision.license_valid ? 'good' : 'danger',
    },
    {
      title: '影响能力',
      detail: `${revision.capability_names.length} 个能力受影响`,
      tone: revision.capability_names.length > 0 ? 'warn' : 'neutral',
    },
    {
      title: '回滚关系',
      detail: revision.rollback_of_revision_id != null ? `回滚自 revision #${revision.rollback_of_revision_id}` : '当前不是回滚产生的 revision',
      tone: revision.rollback_of_revision_id != null ? 'warn' : 'neutral',
    },
  ]
}

export function buildDiagnosticsRiskItems(dashboard: DashboardState): EnterpriseRiskItem[] {
  return [
    {
      title: '排队超时',
      detail: `${dashboard.runtimeMetrics?.request_summary.queue_timeout_count ?? 0} 次`,
      tone: (dashboard.runtimeMetrics?.request_summary.queue_timeout_count ?? 0) > 0 ? 'danger' : 'good',
    },
    {
      title: '繁忙拒绝',
      detail: `${dashboard.runtimeMetrics?.request_summary.busy_reject_count ?? 0} 次`,
      tone: (dashboard.runtimeMetrics?.request_summary.busy_reject_count ?? 0) > 0 ? 'warn' : 'good',
    },
    {
      title: 'P95 峰值',
      detail: `${maxEndpointP95(dashboard.runtimeMetrics)} ms`,
      tone: maxEndpointP95(dashboard.runtimeMetrics) > 1500 ? 'warn' : 'good',
    },
  ]
}

export function buildStatusRiskItems(dashboard: DashboardState): EnterpriseRiskItem[] {
  return [
    {
      title: '资源池利用率',
      detail: dashboard.runtimeMetrics ? `${(dashboard.runtimeMetrics.pool_summary.utilization_ratio * 100).toFixed(1)}%` : '-',
      tone: (dashboard.runtimeMetrics?.pool_summary.utilization_ratio ?? 0) > 0.85 ? 'warn' : 'good',
    },
    {
      title: '运行 revision',
      detail: dashboard.health?.runtime_revision_id != null ? `#${dashboard.health.runtime_revision_id}` : '暂无活动 revision',
      tone: dashboard.health?.runtime_revision_id != null ? 'good' : 'danger',
    },
    {
      title: '授权态势',
      detail: dashboard.licenseStatus ? `${dashboard.licenseStatus.code} / ${dashboard.licenseStatus.result}` : '未知',
      tone: dashboard.licenseStatus?.valid ? 'good' : 'danger',
    },
  ]
}

export function buildAuditRiskItems(auditLogs: AuditLogItem[]): EnterpriseRiskItem[] {
  const reloadCount = auditLogs.filter((item) => item.action.includes('reload')).length
  const rollbackCount = auditLogs.filter((item) => item.action.includes('rollback')).length
  const inferCount = auditLogs.filter((item) => item.action.includes('infer')).length
  return [
    { title: 'reload 留痕', detail: `${reloadCount} 条`, tone: reloadCount > 0 ? 'warn' : 'neutral' },
    { title: 'rollback 留痕', detail: `${rollbackCount} 条`, tone: rollbackCount > 0 ? 'danger' : 'neutral' },
    { title: 'infer 留痕', detail: `${inferCount} 条`, tone: inferCount > 0 ? 'good' : 'neutral' },
  ]
}
