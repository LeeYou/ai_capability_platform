import type {
  AnnotationSampleItem,
  AnnotationTaskItem,
  CapabilityItem,
  DatasetItem,
  ModelArtifactItem,
  TrainingTaskItem,
} from './types'

export type EnterpriseTone = 'good' | 'warn' | 'danger' | 'neutral'

export type EnterpriseChecklistItem = {
  label: string
  detail: string
  done: boolean
}

export type EnterpriseStageCard = {
  title: string
  count: number
  score: number
  tone: EnterpriseTone
  detail: string
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

export function hoursSince(value?: string | null): number | null {
  if (!value) return null
  const time = new Date(value).getTime()
  if (Number.isNaN(time)) return null
  return Math.max(0, (Date.now() - time) / 1000 / 60 / 60)
}

export function freshnessLabel(value?: string | null): string {
  const hours = hoursSince(value)
  if (hours == null) return '未知'
  if (hours <= 24) return '24h 内'
  if (hours <= 72) return '3 天内'
  if (hours <= 24 * 7) return '7 天内'
  return '超 7 天'
}

export function datasetGovernanceLabel(item: DatasetItem): string {
  if (item.dataset_status === 'missing') return '目录缺失'
  if ((item.file_count ?? 0) === 0) return '空数据集'
  if ((hoursSince(item.last_modified) ?? 0) > 24 * 30) return '长期未更新'
  return '正常'
}

export function buildOverviewInsights(params: {
  capabilities: CapabilityItem[]
  annotationTasks: AnnotationTaskItem[]
  trainingTasks: TrainingTaskItem[]
  modelArtifacts: ModelArtifactItem[]
}): {
  overallScore: number
  stageCards: EnterpriseStageCard[]
  risks: EnterpriseRiskItem[]
  actions: string[]
} {
  const { capabilities, annotationTasks, trainingTasks, modelArtifacts } = params
  const boundCapabilities = capabilities.filter((item) => item.dataset_status === 'ready').length
  const completedAnnotations = annotationTasks.filter((item) => item.status === 'completed').length
  const completedTrainings = trainingTasks.filter((item) => item.status === 'completed').length
  const readyModels = modelArtifacts.filter((item) => item.status === 'ready').length

  const capabilityScore = capabilities.length === 0 ? 0 : (boundCapabilities / capabilities.length) * 100
  const annotationScore = annotationTasks.length === 0 ? 100 : (completedAnnotations / annotationTasks.length) * 100
  const trainingScore = trainingTasks.length === 0 ? 100 : (completedTrainings / trainingTasks.length) * 100
  const modelScore = modelArtifacts.length === 0 ? 0 : (readyModels / modelArtifacts.length) * 100
  const overallScore = clampScore(capabilityScore * 0.25 + annotationScore * 0.25 + trainingScore * 0.25 + modelScore * 0.25)

  const failedTrainings = trainingTasks.filter((item) => item.status === 'failed').length
  const missingDatasets = capabilities.filter((item) => item.dataset_status === 'missing').length
  const pendingAnnotations = annotationTasks.filter((item) => item.status !== 'completed').length

  return {
    overallScore,
    stageCards: [
      {
        title: '数据准入',
        count: boundCapabilities,
        score: clampScore(capabilityScore),
        tone: scoreTone(capabilityScore),
        detail: `${boundCapabilities}/${capabilities.length || 0} 个能力具备 ready 数据集`,
      },
      {
        title: '标注交付',
        count: completedAnnotations,
        score: clampScore(annotationScore),
        tone: scoreTone(annotationScore),
        detail: `${completedAnnotations}/${annotationTasks.length || 0} 个标注任务已完成`,
      },
      {
        title: '训练产出',
        count: completedTrainings,
        score: clampScore(trainingScore),
        tone: scoreTone(trainingScore),
        detail: `${completedTrainings}/${trainingTasks.length || 0} 个训练任务已完成`,
      },
      {
        title: '模型就绪',
        count: readyModels,
        score: clampScore(modelScore),
        tone: scoreTone(modelScore),
        detail: `${readyModels}/${modelArtifacts.length || 0} 个模型版本处于 ready`,
      },
    ],
    risks: [
      {
        title: '数据集异常',
        detail: missingDatasets > 0 ? `${missingDatasets} 个能力的数据集目录缺失` : '所有已接入能力的数据集目录可访问',
        tone: missingDatasets > 0 ? 'danger' : 'good',
      },
      {
        title: '训练失败积压',
        detail: failedTrainings > 0 ? `${failedTrainings} 个训练任务需要人工复盘或重试` : '当前无失败训练任务积压',
        tone: failedTrainings > 0 ? 'warn' : 'good',
      },
      {
        title: '标注待交付',
        detail: pendingAnnotations > 0 ? `${pendingAnnotations} 个标注任务尚未闭环` : '标注任务已全部闭环',
        tone: pendingAnnotations > 0 ? 'warn' : 'good',
      },
    ],
    actions: [
      missingDatasets > 0 ? '优先修复 missing 数据集绑定，恢复训练入口可用性。' : '维持数据目录健康巡检，避免路径漂移。',
      failedTrainings > 0 ? '对失败训练任务补充复盘结论，并触发重试或回退。' : '维持训练成功率，关注资源利用率与执行时长波动。',
      readyModels === 0 ? '补充至少一个 ready 模型版本，支撑后续 ai-test / ai-builder 交付链路。' : '将 ready 模型批量送测，推进验收与打包流程。',
    ],
  }
}

export function buildAnnotationChecklist(task: AnnotationTaskItem | null): EnterpriseChecklistItem[] {
  if (!task) return []
  const sampleItems = task.sample_items ?? []
  const submittedCount = sampleItems.filter((item) => item.status === 'submitted').length
  const staleSamples = sampleItems.filter((item) => (hoursSince(item.updated_at) ?? 0) > 24 * 3).length
  return [
    {
      label: '能力与数据集已绑定',
      detail: task.dataset_path ? `当前数据集：${task.dataset_path}` : '未获取到数据集路径',
      done: Boolean(task.dataset_path),
    },
    {
      label: '标注 Schema 已下发',
      detail: task.annotation_schema ? '当前任务已具备 schema 驱动编辑能力' : '缺少 schema',
      done: Boolean(task.annotation_schema && Object.keys(task.annotation_schema).length > 0),
    },
    {
      label: '样本提交覆盖率',
      detail: `${submittedCount}/${task.sample_total} 个样本进入 submitted 状态`,
      done: submittedCount === task.sample_total && task.sample_total > 0,
    },
    {
      label: '长期未更新样本',
      detail: staleSamples > 0 ? `${staleSamples} 个样本超过 3 天未更新` : '无长期滞留样本',
      done: staleSamples === 0,
    },
  ]
}

export function buildTrainingChecklist(task: TrainingTaskItem | null): EnterpriseChecklistItem[] {
  if (!task) return []
  return [
    {
      label: '工作区已生成',
      detail: task.workspace_path ?? '未生成工作区',
      done: Boolean(task.workspace_path),
    },
    {
      label: '训练输入已适配',
      detail: task.training_input_path ?? '未生成 training_input.json',
      done: Boolean(task.training_input_path),
    },
    {
      label: '模板脚手架已生成',
      detail: task.template_bundle_path ?? '未生成 template_bundle.json',
      done: Boolean(task.template_bundle_path),
    },
    {
      label: '日志链路已建立',
      detail: task.log_path ?? '未记录日志文件',
      done: Boolean(task.log_path),
    },
    {
      label: '模型导出可交付',
      detail: task.export_dir ?? '未生成 exported_model',
      done: task.status === 'completed' && Boolean(task.export_dir),
    },
  ]
}

export function buildModelChecklist(model: ModelArtifactItem | null): EnterpriseChecklistItem[] {
  if (!model) return []
  return [
    {
      label: 'Manifest 已生成',
      detail: model.manifest_path,
      done: Boolean(model.manifest_path),
    },
    {
      label: '运行时契约完整',
      detail: model.runtime_contract ? 'runtime_contract 已生成' : '缺少运行时契约',
      done: Boolean(model.runtime_contract && Object.keys(model.runtime_contract).length > 0),
    },
    {
      label: '交付元数据完整',
      detail: model.delivery_metadata ? 'delivery_metadata 已生成' : '缺少交付元数据',
      done: Boolean(model.delivery_metadata && Object.keys(model.delivery_metadata).length > 0),
    },
    {
      label: '产物状态可送测',
      detail: `当前状态：${model.status}`,
      done: model.status === 'ready',
    },
  ]
}

export function buildCapabilityChecklist(capability: CapabilityItem | null): EnterpriseChecklistItem[] {
  if (!capability) return []
  return [
    {
      label: '数据集已接入',
      detail: capability.dataset_path || '未绑定数据集',
      done: capability.dataset_status === 'ready',
    },
    {
      label: '标注 Schema 已配置',
      detail: capability.annotation_schema ? '支持 schema 驱动任务' : '缺少 annotation_schema',
      done: Boolean(capability.annotation_schema && Object.keys(capability.annotation_schema).length > 0),
    },
    {
      label: '模板契约已配置',
      detail: capability.template_bundle ? '训练/测试/推理模板齐备' : '缺少 template_bundle',
      done: Boolean(capability.template_bundle && Object.keys(capability.template_bundle).length > 0),
    },
  ]
}

export function buildDatasetRiskItems(datasets: DatasetItem[]): EnterpriseRiskItem[] {
  const missing = datasets.filter((item) => item.dataset_status === 'missing')
  const empty = datasets.filter((item) => (item.file_count ?? 0) === 0)
  const stale = datasets.filter((item) => (hoursSince(item.last_modified) ?? 0) > 24 * 30)
  return [
    {
      title: '缺失目录',
      detail: missing.length > 0 ? `${missing.length} 个数据集目录不可用` : '无缺失目录',
      tone: missing.length > 0 ? 'danger' : 'good',
    },
    {
      title: '空数据集',
      detail: empty.length > 0 ? `${empty.length} 个绑定目录无文件` : '所有数据集均包含文件',
      tone: empty.length > 0 ? 'warn' : 'good',
    },
    {
      title: '长期未更新',
      detail: stale.length > 0 ? `${stale.length} 个数据集超过 30 天未更新` : '数据新鲜度正常',
      tone: stale.length > 0 ? 'warn' : 'good',
    },
  ]
}

export function buildSampleOpsSummary(sampleItems: AnnotationSampleItem[]): EnterpriseRiskItem[] {
  const pending = sampleItems.filter((item) => item.status === 'pending').length
  const labeled = sampleItems.filter((item) => item.status === 'labeled').length
  const submitted = sampleItems.filter((item) => item.status === 'submitted').length
  const stale = sampleItems.filter((item) => (hoursSince(item.updated_at) ?? 0) > 24 * 3).length
  return [
    {
      title: '待标注样本',
      detail: `${pending} 个样本仍处于 pending`,
      tone: pending > 0 ? 'warn' : 'good',
    },
    {
      title: '待复核样本',
      detail: `${labeled} 个样本已保存但未提交`,
      tone: labeled > 0 ? 'warn' : 'good',
    },
    {
      title: '已提交样本',
      detail: `${submitted} 个样本已进入 submitted`,
      tone: submitted > 0 ? 'good' : 'neutral',
    },
    {
      title: '长期滞留样本',
      detail: stale > 0 ? `${stale} 个样本超 3 天未更新` : '无长期滞留样本',
      tone: stale > 0 ? 'danger' : 'good',
    },
  ]
}
