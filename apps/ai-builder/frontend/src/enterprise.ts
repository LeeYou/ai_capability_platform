import type {
  AuditLogItem,
  BuildArtifactItem,
  BuildFormState,
  BuildTaskDetail,
  BuildTaskItem,
  CatalogModelItem,
  CatalogResponse,
  DashboardState,
  LicenseIssueItem,
  PlatformTargetItem,
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

export type ArtifactGroupItem = {
  artifactType: string
  count: number
  samplePaths: string[]
}

export function clampScore(value: number): number {
  return Math.max(0, Math.min(100, Math.round(value)))
}

export function scoreTone(score: number): EnterpriseTone {
  if (score >= 85) return 'good'
  if (score >= 60) return 'warn'
  return 'danger'
}

function getTimestamp(value?: string | null): number {
  if (!value) return Number.NEGATIVE_INFINITY
  const timestamp = new Date(value).getTime()
  return Number.isNaN(timestamp) ? Number.NEGATIVE_INFINITY : timestamp
}

export function buildOverviewInsights(dashboard: DashboardState): {
  overallScore: number
  stageCards: EnterpriseStageCard[]
  blockers: EnterpriseRiskItem[]
  actions: string[]
  latestCompletedTasks: BuildTaskItem[]
} {
  const completedTasks = dashboard.buildTasks.filter((item) => item.status === 'completed')
  const failedTasks = dashboard.buildTasks.filter((item) => item.status === 'failed')
  const readyModels = dashboard.catalog.models.filter((item) => item.status === 'ready')
  const readyLicenses = dashboard.catalog.license_issues.filter((item) => item.status === 'issued' || item.status === 'valid')
  const buildScore = dashboard.buildTasks.length === 0 ? 0 : (completedTasks.length / dashboard.buildTasks.length) * 100
  const modelScore = dashboard.catalog.models.length === 0 ? 0 : (readyModels.length / dashboard.catalog.models.length) * 100
  const licenseScore = dashboard.catalog.license_issues.length === 0 ? 0 : (readyLicenses.length / dashboard.catalog.license_issues.length) * 100
  const platformScore = dashboard.platforms.length === 0 ? 0 : 100
  const overallScore = clampScore(buildScore * 0.35 + modelScore * 0.25 + licenseScore * 0.2 + platformScore * 0.2)

  return {
    overallScore,
    stageCards: [
      {
        title: '模型可构建度',
        score: clampScore(modelScore),
        count: readyModels.length,
        detail: `${readyModels.length}/${dashboard.catalog.models.length || 0} 个模型 ready`,
        tone: scoreTone(modelScore),
      },
      {
        title: '授权就绪度',
        score: clampScore(licenseScore),
        count: readyLicenses.length,
        detail: `${readyLicenses.length}/${dashboard.catalog.license_issues.length || 0} 条授权可用`,
        tone: scoreTone(licenseScore),
      },
      {
        title: '构建闭环',
        score: clampScore(buildScore),
        count: completedTasks.length,
        detail: `${completedTasks.length}/${dashboard.buildTasks.length || 0} 个任务已完成`,
        tone: scoreTone(buildScore),
      },
      {
        title: '平台矩阵',
        score: clampScore(platformScore),
        count: dashboard.platforms.length,
        detail: `${dashboard.platforms.length} 个构建目标可选`,
        tone: scoreTone(platformScore),
      },
    ],
    blockers: [
      {
        title: '失败任务',
        detail: failedTasks.length > 0 ? `${failedTasks.length} 个失败任务待回看` : '当前没有失败任务',
        tone: failedTasks.length > 0 ? 'danger' : 'good',
      },
      {
        title: '待补授权',
        detail: readyLicenses.length === 0 ? '当前没有 ready license' : `可用授权 ${readyLicenses.length} 条`,
        tone: readyLicenses.length === 0 ? 'warn' : 'good',
      },
      {
        title: '模型准备',
        detail: readyModels.length === 0 ? '当前没有 ready 模型' : `可构建模型 ${readyModels.length} 个`,
        tone: readyModels.length === 0 ? 'warn' : 'good',
      },
    ],
    actions: [
      '先在构建向导确认模型、license、平台目标，再进入任务治理。',
      '优先处理失败任务与缺失授权，避免交付链路在 ai-prod 验收前中断。',
      '交付包确认后把 delivery_package、manifest 与验证结果推进到 ai-prod。',
    ],
    latestCompletedTasks: [...completedTasks].sort((left, right) => getTimestamp(right.completed_at) - getTimestamp(left.completed_at)).slice(0, 5),
  }
}

export function buildWizardChecklist(catalog: CatalogResponse, buildForm: BuildFormState, selectedModel: CatalogModelItem | null, selectedIssue: LicenseIssueItem | null, requestedTargets: PlatformTargetItem[]): EnterpriseChecklistItem[] {
  return [
    {
      label: '模型已选择',
      detail: selectedModel ? `${selectedModel.capability_name} / ${selectedModel.model_version}` : '尚未选择模型',
      done: selectedModel != null,
    },
    {
      label: '授权已选择',
      detail: selectedIssue ? `#${selectedIssue.issue_record_id} / ${selectedIssue.customer_code}` : '尚未选择授权',
      done: selectedIssue != null,
    },
    {
      label: '平台目标已声明',
      detail: requestedTargets.length > 0 ? requestedTargets.map((item) => item.target_name).join(', ') : '尚未选择平台目标',
      done: requestedTargets.length > 0,
    },
    {
      label: '目录数据已加载',
      detail: `${catalog.models.length} 个模型 / ${catalog.license_issues.length} 条授权`,
      done: catalog.models.length > 0 && catalog.license_issues.length > 0,
    },
    {
      label: '构建任务名称已确认',
      detail: buildForm.task_name || '尚未填写任务名',
      done: buildForm.task_name.trim().length > 0,
    },
  ]
}

export function buildTaskChecklist(task: BuildTaskDetail | null): EnterpriseChecklistItem[] {
  if (!task) return []
  return [
    {
      label: '目标已生成',
      detail: `${task.targets.length} 个平台目标`,
      done: task.targets.length > 0,
    },
    {
      label: '产物已归档',
      detail: `${task.artifacts.length} 个产物`,
      done: task.artifacts.length > 0,
    },
    {
      label: 'manifest 可追溯',
      detail: task.manifest ? task.manifest.manifest_path : '当前无 manifest',
      done: task.manifest != null,
    },
    {
      label: 'delivery_package 已产出',
      detail: task.delivery_package_archive_path ?? '当前无交付包归档',
      done: task.delivery_package_archive_path != null,
    },
    {
      label: '任务状态可决策',
      detail: task.status,
      done: ['completed', 'failed'].includes(task.status),
    },
  ]
}

export function buildTaskRiskItems(task: BuildTaskDetail | null): EnterpriseRiskItem[] {
  if (!task) return []
  const failedTargets = task.targets.filter((item) => item.status === 'failed')
  const readyTargets = task.targets.filter((item) => item.status === 'completed' || item.status === 'ready')
  return [
    {
      title: '目标执行',
      detail: `${readyTargets.length}/${task.targets.length} 个目标已成功`,
      tone: failedTargets.length > 0 ? 'warn' : 'good',
    },
    {
      title: '失败建议',
      detail: failedTargets.length > 0 ? `优先检查 ${failedTargets[0].target_name} / ${failedTargets[0].log_path}` : '当前无失败目标',
      tone: failedTargets.length > 0 ? 'danger' : 'good',
    },
    {
      title: '交付包状态',
      detail: task.delivery_package_archive_path ? '已生成 delivery_package' : '尚未生成 delivery_package',
      tone: task.delivery_package_archive_path ? 'good' : 'warn',
    },
  ]
}

export function buildAuditRiskItems(auditLogs: AuditLogItem[]): EnterpriseRiskItem[] {
  const createCount = auditLogs.filter((item) => item.action.includes('create')).length
  const failCount = auditLogs.filter((item) => item.action.includes('fail')).length
  const exportCount = auditLogs.filter((item) => item.action.includes('download') || item.action.includes('export')).length
  return [
    { title: '创建留痕', detail: `${createCount} 条`, tone: createCount > 0 ? 'good' : 'neutral' },
    { title: '失败留痕', detail: `${failCount} 条`, tone: failCount > 0 ? 'danger' : 'good' },
    { title: '导出留痕', detail: `${exportCount} 条`, tone: exportCount > 0 ? 'warn' : 'neutral' },
  ]
}

export function groupArtifacts(artifacts: BuildArtifactItem[]): ArtifactGroupItem[] {
  const grouped = new Map<string, ArtifactGroupItem>()
  for (const artifact of artifacts) {
    const current = grouped.get(artifact.artifact_type)
    if (current) {
      current.count += 1
      if (current.samplePaths.length < 3) current.samplePaths.push(artifact.relative_path)
      continue
    }
    grouped.set(artifact.artifact_type, {
      artifactType: artifact.artifact_type,
      count: 1,
      samplePaths: [artifact.relative_path],
    })
  }
  return [...grouped.values()].sort((left, right) => right.count - left.count)
}

export function summarizeTargets(targets: PlatformTargetItem[], selectedNames: string[]): PlatformTargetItem[] {
  const selectedSet = new Set(selectedNames)
  return targets.filter((item) => selectedSet.has(item.target_name))
}
