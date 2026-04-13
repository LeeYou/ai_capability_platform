import type {
  AcceptanceTaskDetail,
  AcceptanceTaskItem,
  PerformanceBaselineItem,
  RemoteCapabilityItem,
  RemoteModelItem,
  TestCaseResultItem,
  TestReportDetail,
  TestReportItem,
  TestTaskDetail,
  TestTaskItem,
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

export type EnterpriseComparisonRow = {
  label: string
  current: string
  baseline: string
  same: boolean
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

export function formatRate(numerator: number, denominator: number): string {
  if (denominator <= 0) return '0%'
  return `${Math.round((numerator / denominator) * 100)}%`
}

export function averageDuration(cases: TestCaseResultItem[]): number {
  if (cases.length === 0) return 0
  return Math.round(cases.reduce((sum, item) => sum + item.duration_ms, 0) / cases.length)
}

export function stringifyComparableValue(value: unknown): string {
  if (typeof value === 'string') return value
  if (value == null) return '-'
  return JSON.stringify(value, null, 2)
}

/** Returns the first valid timestamp from the fallback list, or Number.NEGATIVE_INFINITY when none are valid. */
function getRecordTimestamp(...values: Array<string | null | undefined>): number {
  for (const value of values) {
    if (!value) continue
    const timestamp = new Date(value).getTime()
    if (!Number.isNaN(timestamp)) return timestamp
  }
  return Number.NEGATIVE_INFINITY
}

export function buildOverviewInsights(params: {
  models: RemoteModelItem[]
  capabilities: RemoteCapabilityItem[]
  tasks: TestTaskItem[]
  acceptanceTasks: AcceptanceTaskItem[]
  reports: TestReportItem[]
}): {
  overallScore: number
  stageCards: EnterpriseStageCard[]
  risks: EnterpriseRiskItem[]
  actions: string[]
} {
  const { models, capabilities, tasks, acceptanceTasks, reports } = params
  const readyModels = models.filter((item) => item.status === 'ready').length
  const completedTasks = tasks.filter((item) => item.status === 'completed').length
  const passedReports = reports.filter((item) => item.failed_cases === 0 && item.passed_cases > 0).length
  const passedAcceptance = acceptanceTasks.filter((item) => item.failed_cases === 0 && item.total_cases > 0).length
  const modelScore = models.length === 0 ? 0 : (readyModels / models.length) * 100
  const testScore = tasks.length === 0 ? 100 : (completedTasks / tasks.length) * 100
  const reportScore = reports.length === 0 ? 0 : (passedReports / reports.length) * 100
  const acceptanceScore = acceptanceTasks.length === 0 ? 100 : (passedAcceptance / acceptanceTasks.length) * 100
  const overallScore = clampScore(modelScore * 0.25 + testScore * 0.25 + reportScore * 0.25 + acceptanceScore * 0.25)
  const failedTasks = tasks.filter((item) => item.failed_cases > 0 || item.status === 'failed').length
  const waitingModels = models.filter((item) => item.status !== 'ready').length
  const pendingAcceptance = acceptanceTasks.filter((item) => item.status !== 'completed').length

  return {
    overallScore,
    stageCards: [
      {
        title: '能力就绪',
        count: capabilities.length,
        score: clampScore(modelScore),
        tone: scoreTone(modelScore),
        detail: `${readyModels}/${models.length || 0} 个模型版本处于 ready`,
      },
      {
        title: '测试执行',
        count: completedTasks,
        score: clampScore(testScore),
        tone: scoreTone(testScore),
        detail: `${completedTasks}/${tasks.length || 0} 个测试任务已完成`,
      },
      {
        title: '报告沉淀',
        count: passedReports,
        score: clampScore(reportScore),
        tone: scoreTone(reportScore),
        detail: `${passedReports}/${reports.length || 0} 个报告可下游推进`,
      },
      {
        title: '生产验收',
        count: passedAcceptance,
        score: clampScore(acceptanceScore),
        tone: scoreTone(acceptanceScore),
        detail: `${passedAcceptance}/${acceptanceTasks.length || 0} 个验收任务通过`,
      },
    ],
    risks: [
      {
        title: '待测模型积压',
        detail: waitingModels > 0 ? `${waitingModels} 个模型尚未 ready 或仍待测试流转` : '当前模型目录已具备测试入口',
        tone: waitingModels > 0 ? 'warn' : 'good',
      },
      {
        title: '失败任务积压',
        detail: failedTasks > 0 ? `${failedTasks} 个测试任务需要问题样本复盘` : '当前无失败测试任务积压',
        tone: failedTasks > 0 ? 'danger' : 'good',
      },
      {
        title: '验收待收口',
        detail: pendingAcceptance > 0 ? `${pendingAcceptance} 个生产验收任务尚未收口` : '生产验收任务均已收口',
        tone: pendingAcceptance > 0 ? 'warn' : 'good',
      },
    ],
    actions: [
      waitingModels > 0 ? '优先从能力选择区筛出待测模型，进入单测或批测。' : '继续维持模型目录同步，缩短模型入测滞后时间。',
      failedTasks > 0 ? '先回看失败样本与版本对比，再决定回流 ai-train 或继续复测。' : '将更多通过结果沉淀为报告，推动授权 / 构建。',
      pendingAcceptance > 0 ? '对关键版本补做 acceptance 与 pressure 基线校验。' : '把已通过结果推进到下游授权与构建模块。',
    ],
  }
}

export function buildSingleChecklist(task: TestTaskDetail | null, compareTask: TestTaskItem | null): EnterpriseChecklistItem[] {
  if (!task) return []
  return [
    {
      label: '已绑定待测模型',
      detail: `${task.capability_name} / ${task.model_version}`,
      done: Boolean(task.capability_name && task.model_version),
    },
    {
      label: '已产出单样本结果',
      detail: `${task.passed_cases + task.failed_cases}/${task.total_cases} 个用例已执行`,
      done: task.total_cases > 0,
    },
    {
      label: '结果可用于定位',
      detail: task.failed_cases > 0 ? `存在 ${task.failed_cases} 个失败用例` : '当前无失败用例',
      done: task.failed_cases === 0,
    },
    {
      label: '具备版本对比对象',
      detail: compareTask ? `可对比任务 #${compareTask.task_id}` : '当前无同能力历史任务可对比',
      done: compareTask != null,
    },
  ]
}

export function buildBatchChecklist(task: TestTaskDetail | null): EnterpriseChecklistItem[] {
  if (!task) return []
  return [
    {
      label: '批量任务已创建',
      detail: `任务 #${task.task_id} / ${task.capability_name}`,
      done: task.task_id > 0,
    },
    {
      label: '用例集已装载',
      detail: `${task.total_cases} 个批量用例`,
      done: task.total_cases > 0,
    },
    {
      label: '失败样本可复盘',
      detail: task.failed_cases > 0 ? `${task.failed_cases} 个失败样本待分析` : '当前无失败样本',
      done: task.failed_cases === 0,
    },
    {
      label: '报告可沉淀',
      detail: task.report_id ? `报告 #${task.report_id}` : '当前任务尚未生成报告',
      done: task.report_id != null,
    },
  ]
}

export function buildAcceptanceChecklist(task: AcceptanceTaskDetail | null): EnterpriseChecklistItem[] {
  if (!task) return []
  return [
    {
      label: '目标环境已声明',
      detail: task.target_base_url,
      done: Boolean(task.target_base_url),
    },
    {
      label: '验收脚本已执行',
      detail: `${task.passed_cases}/${task.total_cases} 个脚本通过`,
      done: task.total_cases > 0,
    },
    {
      label: '基线校验可用',
      detail: task.script_results.some((item) => item.baseline_comparison != null) ? '存在基线比对结果' : '暂无基线比对',
      done: task.script_results.some((item) => item.baseline_comparison != null),
    },
    {
      label: '验收结论可下游消费',
      detail: task.failed_cases === 0 ? '当前可进入报告与下游决策' : '需先处理失败项',
      done: task.failed_cases === 0,
    },
  ]
}

export function buildModelVersionComparison(current: TestTaskItem, baseline: TestTaskItem): EnterpriseComparisonRow[] {
  return [
    {
      label: '模型版本',
      current: current.model_version,
      baseline: baseline.model_version,
      same: current.model_version === baseline.model_version,
    },
    {
      label: '执行后端',
      current: current.execution_backend ?? current.requested_backend,
      baseline: baseline.execution_backend ?? baseline.requested_backend,
      same: (current.execution_backend ?? current.requested_backend) === (baseline.execution_backend ?? baseline.requested_backend),
    },
    {
      label: '通过率',
      current: formatRate(current.passed_cases, Math.max(1, current.total_cases)),
      baseline: formatRate(baseline.passed_cases, Math.max(1, baseline.total_cases)),
      same: current.passed_cases === baseline.passed_cases && current.total_cases === baseline.total_cases,
    },
    {
      label: '失败用例',
      current: String(current.failed_cases),
      baseline: String(baseline.failed_cases),
      same: current.failed_cases === baseline.failed_cases,
    },
    {
      label: '完成时间',
      current: current.completed_at ?? '-',
      baseline: baseline.completed_at ?? '-',
      same: current.completed_at === baseline.completed_at,
    },
  ]
}

export function buildCaseRiskItems(cases: TestCaseResultItem[]): EnterpriseRiskItem[] {
  const failed = cases.filter((item) => item.status !== 'passed').length
  const slow = cases.filter((item) => item.duration_ms > 1000).length
  const lowScore = cases.filter((item) => item.score < 0.8).length
  return [
    {
      title: '失败用例',
      detail: failed > 0 ? `${failed} 个用例未通过` : '当前无失败用例',
      tone: failed > 0 ? 'danger' : 'good',
    },
    {
      title: '慢样本',
      detail: slow > 0 ? `${slow} 个用例耗时超过 1000ms` : '当前无明显慢样本',
      tone: slow > 0 ? 'warn' : 'good',
    },
    {
      title: '低分样本',
      detail: lowScore > 0 ? `${lowScore} 个用例得分低于 0.8` : '当前无低分样本',
      tone: lowScore > 0 ? 'warn' : 'good',
    },
  ]
}

export function buildAcceptanceRiskItems(task: AcceptanceTaskDetail | null): EnterpriseRiskItem[] {
  if (!task) return []
  const baselineFailed = task.script_results.filter((item) => item.passed_baseline === false).length
  const scriptFailed = task.script_results.filter((item) => !item.passed).length
  return [
    {
      title: '脚本失败',
      detail: scriptFailed > 0 ? `${scriptFailed} 个验收脚本失败` : '所有验收脚本均通过',
      tone: scriptFailed > 0 ? 'danger' : 'good',
    },
    {
      title: '基线偏离',
      detail: baselineFailed > 0 ? `${baselineFailed} 个脚本未满足基线` : '当前无基线偏离',
      tone: baselineFailed > 0 ? 'warn' : 'good',
    },
    {
      title: '运行地址',
      detail: task.target_base_url,
      tone: 'neutral',
    },
  ]
}

export function buildBaselineSummary(items: PerformanceBaselineItem[]): EnterpriseRiskItem[] {
  const allCapability = items.filter((item) => item.capability_name === 'all').length
  const custom = items.length - allCapability
  const p95Configured = items.filter((item) => item.p95_max_ms != null).length
  return [
    {
      title: '平台级模板',
      detail: `${allCapability} 个 all 级默认基线`,
      tone: allCapability > 0 ? 'good' : 'warn',
    },
    {
      title: '能力级覆盖',
      detail: `${custom} 个能力有专属基线`,
      tone: custom > 0 ? 'good' : 'neutral',
    },
    {
      title: 'P95 已配置',
      detail: `${p95Configured} 个基线定义了 P95 阈值`,
      tone: p95Configured > 0 ? 'good' : 'warn',
    },
  ]
}

export function pickBestReport(reports: TestReportItem[]): TestReportItem | null {
  if (reports.length === 0) return null
  return [...reports].sort((left, right) => {
    const leftScore = left.failed_cases === 0 ? 1 : 0
    const rightScore = right.failed_cases === 0 ? 1 : 0
    if (leftScore !== rightScore) return rightScore - leftScore
    return getRecordTimestamp(right.exported_at) - getRecordTimestamp(left.exported_at)
  })[0]
}

export function buildReportActions(report: TestReportDetail | null): string[] {
  if (!report) return []
  if (report.failed_cases === 0) {
    return [
      '将通过报告推送到 ai-license-mgr，准备授权签发。',
      '同步把通过版本推入 ai-builder 交付构建链。',
      '对关键版本补做 ai-prod 运行态验收与版本切换确认。',
    ]
  }
  return [
    '根据证据链定位失败版本对应的训练任务与模型 manifest。',
    '将失败样本与原因回流至 ai-train 标注 / 训练侧。',
    '补做版本对比后再决定是复测还是终止推进。',
  ]
}
