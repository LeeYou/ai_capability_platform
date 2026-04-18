import { useEffect, useMemo, useState } from 'react'
import './App.css'
import '../../../frontend-common/src/r7Workspace.css'
import { WorkspaceShell } from '../../../frontend-common/src/workspaceShell.tsx'
import { buildR7Workspace } from '../../../frontend-common/src/r7Workspace.ts'
import { fetchListResponse, requestJson } from '../../../frontend-common/src/http.ts'
import { WorkspaceFeedback } from '../../../frontend-common/src/workspaceFeedback.tsx'

type RemoteCapabilityItem = {
  capability_name: string
  display_name: string
  dataset_path: string
  dataset_status: string
  source: string
}

type RemoteModelItem = {
  capability_name: string
  model_version: string
  artifact_path: string
  backend_type: string
  status: string
}

type TestCaseResultItem = {
  case_id: number
  case_name: string
  input_path: string
  input_type: string
  status: string
  expected_output: string | null
  actual_output: string | null
  duration_ms: number
  score: number
  provider: string | null
}

type TestTaskItem = {
  task_id: number
  task_type: string
  capability_name: string
  model_version: string
  requested_backend: string
  execution_backend: string | null
  execution_mode: string
  execution_risk: string | null
  timeout_seconds: number
  status: string
  total_cases: number
  passed_cases: number
  failed_cases: number
  error_message: string | null
  report_id: number | null
  started_at: string | null
  completed_at: string | null
}

type TestTaskDetail = TestTaskItem & {
  cases: TestCaseResultItem[]
  evidence_chain: Record<string, unknown> | null
}

type AcceptanceScriptResultItem = {
  case_name: string
  status: string
  duration_ms: number
  passed: boolean
  detail: Record<string, unknown>
  baseline_comparison: Record<string, unknown> | null
  passed_baseline: boolean | null
}

type AcceptanceTaskItem = {
  acceptance_task_id: number
  task_id: number
  image_uri: string
  target_base_url: string
  capability_name: string | null
  input_type: string
  prefer_device: string
  status: string
  total_cases: number
  passed_cases: number
  failed_cases: number
  report_id: number | null
  created_at: string | null
  started_at: string | null
  completed_at: string | null
}

type AcceptanceTaskDetail = AcceptanceTaskItem & {
  script_results: AcceptanceScriptResultItem[]
}

type PerformanceBaselineItem = {
  baseline_id: number
  capability_name: string
  scenario_name: string
  p95_max_ms: number | null
  success_rate_min: number
  description: string | null
}

type TestReportItem = {
  report_id: number
  task_id: number
  capability_name: string
  model_version: string
  status: string
  execution_mode: string
  execution_risk: string | null
  passed_cases: number
  failed_cases: number
  available_template_types: Array<'research' | 'delivery'>
  active_template_type: 'research' | 'delivery'
  json_report_path: string
  html_report_path: string
  pdf_report_path: string
  exported_at: string | null
}

type TestReportDetail = TestReportItem & {
  summary: Record<string, unknown>
}

type ApiListResponse<T> = {
  items: T[]
  synced_at?: string | null
}

type DashboardState = {
  models: RemoteModelItem[]
  capabilities: RemoteCapabilityItem[]
  tasks: TestTaskItem[]
  acceptanceTasks: AcceptanceTaskItem[]
  baselines: PerformanceBaselineItem[]
  reports: TestReportItem[]
  syncedAt: string | null
}

type SingleTestForm = {
  capability_name: string
  model_version: string
  requested_backend: 'auto' | 'gpu' | 'cpu'
  timeout_seconds: string
  case_name: string
  input_path: string
  expected_output: string
}

type BatchTestForm = {
  capability_name: string
  model_version: string
  requested_backend: 'auto' | 'gpu' | 'cpu'
  timeout_seconds: string
  cases_text: string
}

type AcceptanceForm = {
  image_uri: string
  target_base_url: string
  capability_name: string
  input_type: 'json' | 'image' | 'video' | 'pdf'
  infer_payload: string
  prefer_device: 'auto' | 'gpu' | 'cpu'
  acceptance_timeout_seconds: string
  run_admin_checks: boolean
  pressure_requests: string
  pressure_concurrency: string
  pressure_timeout_seconds: string
  pressure_min_success_rate: string
  pressure_max_p95_ms: string
}

type BaselineForm = {
  capability_name: string
  scenario_name: string
  p95_max_ms: string
  success_rate_min: string
  description: string
}

const apiBaseUrl = import.meta.env.VITE_API_BASE_URL ?? ''
const workspace = buildR7Workspace(import.meta.env, 'ai-test')
const tabs = ['overview', 'single', 'batch', 'acceptance', 'reports'] as const
type TabKey = (typeof tabs)[number]

const initialState: DashboardState = {
  models: [],
  capabilities: [],
  tasks: [],
  acceptanceTasks: [],
  baselines: [],
  reports: [],
  syncedAt: null,
}

const initialSingleForm: SingleTestForm = {
  capability_name: '',
  model_version: '',
  requested_backend: 'auto',
  timeout_seconds: '30',
  case_name: '单张样例验证',
  input_path: '/data/ai_capability_platform/datasets/demo/input.json',
  expected_output: '',
}

const initialBatchForm: BatchTestForm = {
  capability_name: '',
  model_version: '',
  requested_backend: 'auto',
  timeout_seconds: '45',
  cases_text:
    'case-01|/data/ai_capability_platform/datasets/demo/case-01.json|\ncase-02|/data/ai_capability_platform/datasets/demo/case-02.json|',
}

const initialAcceptanceForm: AcceptanceForm = {
  image_uri: 'agilestar/ai-prod:latest',
  target_base_url: 'http://127.0.0.1:26004',
  capability_name: '',
  input_type: 'json',
  infer_payload: '{"image":"demo"}',
  prefer_device: 'auto',
  acceptance_timeout_seconds: '20',
  run_admin_checks: true,
  pressure_requests: '32',
  pressure_concurrency: '8',
  pressure_timeout_seconds: '10',
  pressure_min_success_rate: '1',
  pressure_max_p95_ms: '5000',
}

const initialBaselineForm: BaselineForm = {
  capability_name: 'all',
  scenario_name: 'delivery-default',
  p95_max_ms: '5000',
  success_rate_min: '1',
  description: '交付验收默认基线',
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  return requestJson<T>(apiBaseUrl, path, init)
}

async function fetchList<T>(path: string): Promise<ApiListResponse<T>> {
  return fetchListResponse<T>(apiBaseUrl, path)
}

function statusTone(status: string): 'good' | 'warn' | 'danger' | 'neutral' {
  if (['passed', 'completed', 'ready', 'success', 'ok'].includes(status)) return 'good'
  if (['failed', 'error', 'rejected'].includes(status)) return 'danger'
  if (['running', 'pending', 'queued', 'created'].includes(status)) return 'warn'
  return 'neutral'
}

function parseBatchCases(raw: string): Array<{ case_name: string; input_path: string; expected_output?: string }> {
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

function App() {
  const [activeTab, setActiveTab] = useState<TabKey>('overview')
  const [dashboard, setDashboard] = useState<DashboardState>(initialState)
  const [selectedTaskId, setSelectedTaskId] = useState<number | null>(null)
  const [selectedAcceptanceId, setSelectedAcceptanceId] = useState<number | null>(null)
  const [selectedReportId, setSelectedReportId] = useState<number | null>(null)
  const [reportTemplateType, setReportTemplateType] = useState<'research' | 'delivery'>('research')
  const [selectedTask, setSelectedTask] = useState<TestTaskDetail | null>(null)
  const [selectedAcceptance, setSelectedAcceptance] = useState<AcceptanceTaskDetail | null>(null)
  const [selectedReport, setSelectedReport] = useState<TestReportDetail | null>(null)
  const [singleForm, setSingleForm] = useState<SingleTestForm>(initialSingleForm)
  const [batchForm, setBatchForm] = useState<BatchTestForm>(initialBatchForm)
  const [acceptanceForm, setAcceptanceForm] = useState<AcceptanceForm>(initialAcceptanceForm)
  const [baselineForm, setBaselineForm] = useState<BaselineForm>(initialBaselineForm)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [actionMessage, setActionMessage] = useState<string | null>(null)

  async function loadDashboard(): Promise<void> {
    setLoading(true)
    setError(null)
    try {
      const [models, capabilities, tasks, acceptanceTasks, baselines, reports] = await Promise.all([
        fetchList<RemoteModelItem>('/api/v1/remote-models'),
        fetchList<RemoteCapabilityItem>('/api/v1/remote-capabilities'),
        fetchList<TestTaskItem>('/api/v1/test-tasks'),
        fetchList<AcceptanceTaskItem>('/api/v1/acceptance-tasks'),
        fetchList<PerformanceBaselineItem>('/api/v1/performance-baselines'),
        fetchList<TestReportItem>('/api/v1/test-reports'),
      ])
      setDashboard({
        models: models.items,
        capabilities: capabilities.items,
        tasks: tasks.items,
        acceptanceTasks: acceptanceTasks.items,
        baselines: baselines.items,
        reports: reports.items,
        syncedAt: models.synced_at ?? capabilities.synced_at ?? null,
      })
      setSelectedTaskId((current) => current ?? tasks.items[0]?.task_id ?? null)
      setSelectedAcceptanceId((current) => current ?? acceptanceTasks.items[0]?.acceptance_task_id ?? null)
      setSelectedReportId((current) => current ?? reports.items[0]?.report_id ?? null)
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : '加载失败')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    void loadDashboard()
  }, [])

  useEffect(() => {
    const firstModel = dashboard.models[0]
    if (!firstModel) return
    setSingleForm((current) => ({
      ...current,
      capability_name: current.capability_name || firstModel.capability_name,
      model_version: current.model_version || firstModel.model_version,
    }))
    setBatchForm((current) => ({
      ...current,
      capability_name: current.capability_name || firstModel.capability_name,
      model_version: current.model_version || firstModel.model_version,
    }))
    setAcceptanceForm((current) => ({
      ...current,
      capability_name: current.capability_name || firstModel.capability_name,
    }))
    setBaselineForm((current) => ({
      ...current,
      capability_name: current.capability_name || firstModel.capability_name,
    }))
  }, [dashboard.models])

  useEffect(() => {
    if (selectedTaskId == null) {
      setSelectedTask(null)
      return
    }
    void request<TestTaskDetail>(`/api/v1/test-tasks/${selectedTaskId}`).then(setSelectedTask).catch(() => {
      setSelectedTask(null)
    })
  }, [selectedTaskId])

  useEffect(() => {
    if (selectedAcceptanceId == null) {
      setSelectedAcceptance(null)
      return
    }
    void request<AcceptanceTaskDetail>(`/api/v1/acceptance-tasks/${selectedAcceptanceId}`)
      .then(setSelectedAcceptance)
      .catch(() => {
        setSelectedAcceptance(null)
      })
  }, [selectedAcceptanceId])

  useEffect(() => {
    if (selectedReportId == null) {
      setSelectedReport(null)
      return
    }
    void request<TestReportDetail>(`/api/v1/test-reports/${selectedReportId}?template_type=${reportTemplateType}`)
      .then(setSelectedReport)
      .catch(() => {
        setSelectedReport(null)
      })
  }, [selectedReportId, reportTemplateType])

  const overviewCards = useMemo(
    () => [
      { title: '待测模型', value: dashboard.models.length, description: '从 ai-train 拉取后待进入单测 / 批测 / 验收决策的模型。' },
      { title: '运行中测试', value: dashboard.tasks.filter((item) => item.status === 'running').length, description: '正在执行的单测与批量测试任务。' },
      { title: '失败任务', value: dashboard.tasks.filter((item) => item.failed_cases > 0 || item.status === 'failed').length, description: '优先定位错误样本与失败原因的任务。' },
      { title: '可下游推进', value: dashboard.reports.filter((item) => item.failed_cases === 0 && item.passed_cases > 0).length, description: '已具备进入授权 / 构建阶段条件的测试结果。' },
    ],
    [dashboard],
  )

  const recommendedModels = useMemo(
    () => dashboard.models.slice(0, 4),
    [dashboard.models],
  )

  const riskyTasks = useMemo(
    () => dashboard.tasks.filter((item) => item.failed_cases > 0 || item.status === 'failed').slice(0, 4),
    [dashboard.tasks],
  )

  const nextActionTitle = workspace.nextModule ? `去 ${workspace.nextModule.shortTitle}` : '完成全流程闭环'

  async function handleSyncCatalog(): Promise<void> {
    try {
      setActionMessage('正在同步 ai-train 模型目录...')
      await request('/api/v1/remote-model-catalog/sync', { method: 'POST' })
      setActionMessage('模型目录同步完成')
      await loadDashboard()
    } catch (loadError) {
      setActionMessage(loadError instanceof Error ? loadError.message : '目录同步失败')
    }
  }

  async function handleCreateSingleTest(): Promise<void> {
    try {
      setActionMessage('正在创建单测任务...')
      const created = await request<TestTaskDetail>('/api/v1/single-tests', {
        method: 'POST',
        body: JSON.stringify({
          capability_name: singleForm.capability_name,
          model_version: singleForm.model_version,
          requested_backend: singleForm.requested_backend,
          timeout_seconds: Number(singleForm.timeout_seconds),
          case: {
            case_name: singleForm.case_name,
            input_path: singleForm.input_path,
            expected_output: singleForm.expected_output || undefined,
          },
        }),
      })
      setSelectedTaskId(created.task_id)
      setActiveTab('single')
      setActionMessage(`单测任务 #${created.task_id} 已创建`)
      await loadDashboard()
    } catch (loadError) {
      setActionMessage(loadError instanceof Error ? loadError.message : '创建单测失败')
    }
  }

  async function handleCreateBatchTest(): Promise<void> {
    try {
      setActionMessage('正在创建批量测试任务...')
      const created = await request<TestTaskDetail>('/api/v1/batch-tests', {
        method: 'POST',
        body: JSON.stringify({
          capability_name: batchForm.capability_name,
          model_version: batchForm.model_version,
          requested_backend: batchForm.requested_backend,
          timeout_seconds: Number(batchForm.timeout_seconds),
          cases: parseBatchCases(batchForm.cases_text),
        }),
      })
      setSelectedTaskId(created.task_id)
      setActiveTab('batch')
      setActionMessage(`批量测试任务 #${created.task_id} 已创建`)
      await loadDashboard()
    } catch (loadError) {
      setActionMessage(loadError instanceof Error ? loadError.message : '创建批量测试失败')
    }
  }

  async function handleCreateAcceptanceTask(): Promise<void> {
    try {
      setActionMessage('正在创建生产验收任务...')
      const created = await request<AcceptanceTaskDetail>('/api/v1/acceptance-tasks', {
        method: 'POST',
        body: JSON.stringify({
          image_uri: acceptanceForm.image_uri,
          target_base_url: acceptanceForm.target_base_url,
          capability_name: acceptanceForm.capability_name || null,
          input_type: acceptanceForm.input_type,
          infer_payload: acceptanceForm.infer_payload,
          prefer_device: acceptanceForm.prefer_device,
          acceptance_timeout_seconds: Number(acceptanceForm.acceptance_timeout_seconds),
          run_admin_checks: acceptanceForm.run_admin_checks,
          pressure_requests: Number(acceptanceForm.pressure_requests),
          pressure_concurrency: Number(acceptanceForm.pressure_concurrency),
          pressure_timeout_seconds: Number(acceptanceForm.pressure_timeout_seconds),
          pressure_min_success_rate: Number(acceptanceForm.pressure_min_success_rate),
          pressure_max_p95_ms: Number(acceptanceForm.pressure_max_p95_ms),
        }),
      })
      setSelectedAcceptanceId(created.acceptance_task_id)
      setActiveTab('acceptance')
      setActionMessage(`验收任务 #${created.acceptance_task_id} 已创建`)
      await loadDashboard()
    } catch (loadError) {
      setActionMessage(loadError instanceof Error ? loadError.message : '创建验收任务失败')
    }
  }

  async function handleSaveBaseline(): Promise<void> {
    try {
      setActionMessage('正在保存性能基线...')
      await request<PerformanceBaselineItem>('/api/v1/performance-baselines', {
        method: 'POST',
        body: JSON.stringify({
          capability_name: baselineForm.capability_name,
          scenario_name: baselineForm.scenario_name,
          p95_max_ms: Number(baselineForm.p95_max_ms),
          success_rate_min: Number(baselineForm.success_rate_min),
          description: baselineForm.description,
        }),
      })
      setActionMessage('性能基线已更新')
      await loadDashboard()
    } catch (loadError) {
      setActionMessage(loadError instanceof Error ? loadError.message : '保存基线失败')
    }
  }

  function reportExportUrl(reportId: number, format: 'json' | 'html' | 'pdf'): string {
    return `${apiBaseUrl}/api/v1/test-reports/${reportId}/export?export_format=${format}&template_type=${reportTemplateType}`
  }

  return (
    <WorkspaceShell moduleId="ai-test" title="ai-test" subtitle="统一研发工作台">
      <header className="hero">
        <div className="hero-text">
          <p className="eyebrow">北京爱知之星科技股份有限公司（Agile Star）</p>
          <h1>ai-test 测试评估工作台</h1>
          <p>
            将当前真实能力重构为“单测 → 批测 → 生产验收 → 报告决策”的测试中枢。目标不是继续堆图表，
            而是帮助研发、测试、交付人员快速完成评估、定位问题、生成证据链并推动下游授权 / 构建。
          </p>
          <div className="workspace-action-row">
            <button className="action-button" onClick={() => void handleSyncCatalog()} type="button">
              同步 ai-train 模型目录
            </button>
            {workspace.nextModule && (
              <a className="workspace-action-chip" href={workspace.nextModule.url}>
                {nextActionTitle}
              </a>
            )}
          </div>
        </div>
        <div className="hero-panel">
          <div>
            <span className="label">服务端口</span>
            <strong>26001</strong>
          </div>
          <div>
            <span className="label">最近模型同步</span>
            <strong>{dashboard.syncedAt ?? '暂无同步记录'}</strong>
          </div>
          <div>
            <span className="label">核心定位</span>
            <strong>单测 / 批测 / 验收 / 报告一体化</strong>
          </div>
        </div>
      </header>

      <main className="content">
        <section className="panel">
          <div className="section-header">
            <div>
              <h2>首页概览</h2>
              <p>优先回答：哪些模型待测、哪些任务异常、哪些结果可以进入下游。</p>
            </div>
            <span className="badge">TT15-TT19</span>
          </div>
          <WorkspaceFeedback
            loading={loading}
            loadingMessage="正在加载测试中枢数据..."
            error={error}
            actionMessage={actionMessage}
          />
          <div className="card-grid">
            {overviewCards.map((card) => (
              <article key={card.title} className="card">
                <h3>{card.title}</h3>
                <strong>{card.value}</strong>
                <p>{card.description}</p>
              </article>
            ))}
          </div>
          <div className="workspace-summary-grid">
            <article className="workspace-summary-card">
              <h3>待优先测试模型</h3>
              {recommendedModels.length === 0 ? (
                <div className="workspace-empty">当前暂无可测试模型，请先在 ai-train 产出模型。</div>
              ) : (
                <div className="workspace-list">
                  {recommendedModels.map((item) => (
                    <button
                      key={`${item.capability_name}-${item.model_version}`}
                      className="workspace-list-item"
                      onClick={() => {
                        setSingleForm((current) => ({
                          ...current,
                          capability_name: item.capability_name,
                          model_version: item.model_version,
                        }))
                        setActiveTab('single')
                      }}
                      type="button"
                    >
                      <strong>{item.capability_name}</strong>
                      <div className="workspace-meta-row">
                        <span>{item.model_version}</span>
                        <span>{item.backend_type}</span>
                        <span className={`status-pill ${statusTone(item.status)}`}>{item.status}</span>
                      </div>
                    </button>
                  ))}
                </div>
              )}
            </article>
            <article className="workspace-summary-card">
              <h3>需优先定位的问题任务</h3>
              {riskyTasks.length === 0 ? (
                <div className="workspace-empty">当前无失败任务，测试队列状态良好。</div>
              ) : (
                <div className="workspace-list">
                  {riskyTasks.map((item) => (
                    <button
                      key={item.task_id}
                      className="workspace-list-item"
                      onClick={() => {
                        setSelectedTaskId(item.task_id)
                        setActiveTab(item.task_type === 'batch' ? 'batch' : 'single')
                      }}
                      type="button"
                    >
                      <strong>任务 #{item.task_id} / {item.capability_name}</strong>
                      <div className="workspace-meta-row">
                        <span>{item.model_version}</span>
                        <span>{item.failed_cases} 个失败用例</span>
                        <span className={`status-pill ${statusTone(item.status)}`}>{item.status}</span>
                      </div>
                    </button>
                  ))}
                </div>
              )}
            </article>
            <article className="workspace-summary-card">
              <h3>跨模块下一步</h3>
              <ul>
                <li>测试通过模型直接进入授权签发与交付构建，不再手工记录 ID。</li>
                <li>问题样本应回流至 ai-train 标注 / 训练侧修正数据与模型。</li>
                <li>生产验收通过后，再进入 ai-prod 运行验证与版本切换确认。</li>
              </ul>
            </article>
          </div>
        </section>

        <section className="panel">
          <div className="toolbar">
            <div>
              <h2>测试工作台</h2>
              <p>围绕单测、批测、生产验收与报告中心组织连续作业。</p>
            </div>
            <div className="tab-list">
              {tabs.map((tab) => (
                <button
                  key={tab}
                  className={`tab-button${activeTab === tab ? ' active' : ''}`}
                  onClick={() => setActiveTab(tab)}
                  type="button"
                >
                  {tab === 'overview' && '中枢视图'}
                  {tab === 'single' && '单测工作台'}
                  {tab === 'batch' && '批量测试'}
                  {tab === 'acceptance' && '生产验收'}
                  {tab === 'reports' && '报告中心'}
                </button>
              ))}
            </div>
          </div>

          {activeTab === 'overview' && (
            <div className="workspace-panel-grid">
              <div className="workspace-stack">
                <article className="workspace-note-block">
                  <h3>当前建议动作</h3>
                  <ul>
                    <li>先从“单测工作台”验证最新模型的单样本表现。</li>
                    <li>再通过“批量测试”沉淀错误样本与指标分布。</li>
                    <li>最后用“生产验收”固化公开 API 与压力基线结论。</li>
                  </ul>
                </article>
                <article className="workspace-note-block">
                  <h3>模型目录与能力清单</h3>
                  <div className="workspace-table-wrap">
                    <table className="workspace-table">
                      <thead>
                        <tr>
                          <th>能力</th>
                          <th>版本</th>
                          <th>状态</th>
                        </tr>
                      </thead>
                      <tbody>
                        {dashboard.models.slice(0, 6).map((item) => (
                          <tr key={`${item.capability_name}-${item.model_version}`}>
                            <td>{item.capability_name}</td>
                            <td>{item.model_version}</td>
                            <td><span className={`status-pill ${statusTone(item.status)}`}>{item.status}</span></td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </article>
              </div>
              <div className="workspace-stack">
                <article className="workspace-note-block">
                  <h3>最近测试队列</h3>
                  <div className="workspace-list">
                    {dashboard.tasks.slice(0, 5).map((item) => (
                      <button
                        key={item.task_id}
                        className={`workspace-list-item${selectedTaskId === item.task_id ? ' active' : ''}`}
                        onClick={() => {
                          setSelectedTaskId(item.task_id)
                          setActiveTab(item.task_type === 'batch' ? 'batch' : 'single')
                        }}
                        type="button"
                      >
                        <strong>任务 #{item.task_id} / {item.task_type}</strong>
                        <div className="workspace-meta-row">
                          <span>{item.capability_name}</span>
                          <span>{item.model_version}</span>
                          <span>{item.execution_mode}</span>
                          <span>{item.passed_cases}/{item.total_cases} 通过</span>
                          <span className={`status-pill ${statusTone(item.status)}`}>{item.status}</span>
                        </div>
                      </button>
                    ))}
                  </div>
                </article>
              </div>
            </div>
          )}

          {activeTab === 'single' && (
            <div className="workspace-panel-grid">
              <div className="workspace-stack">
                <article className="workspace-note-block">
                  <div className="section-header">
                    <h3>创建单测</h3>
                    <span className="badge badge-muted">TT15</span>
                  </div>
                  <div className="workspace-form-grid">
                    <label className="workspace-field">
                      能力
                      <select
                        value={singleForm.capability_name}
                        onChange={(event) => setSingleForm((current) => ({ ...current, capability_name: event.target.value }))}
                      >
                        {dashboard.models.map((item) => (
                          <option key={`${item.capability_name}-${item.model_version}`} value={item.capability_name}>
                            {item.capability_name}
                          </option>
                        ))}
                      </select>
                    </label>
                    <label className="workspace-field">
                      模型版本
                      <select
                        value={singleForm.model_version}
                        onChange={(event) => setSingleForm((current) => ({ ...current, model_version: event.target.value }))}
                      >
                        {dashboard.models
                          .filter((item) => item.capability_name === singleForm.capability_name)
                          .map((item) => (
                            <option key={item.model_version} value={item.model_version}>
                              {item.model_version}
                            </option>
                          ))}
                      </select>
                    </label>
                    <label className="workspace-field">
                      执行后端
                      <select
                        value={singleForm.requested_backend}
                        onChange={(event) =>
                          setSingleForm((current) => ({
                            ...current,
                            requested_backend: event.target.value as SingleTestForm['requested_backend'],
                          }))
                        }
                      >
                        <option value="auto">auto</option>
                        <option value="gpu">gpu</option>
                        <option value="cpu">cpu</option>
                      </select>
                    </label>
                    <label className="workspace-field">
                      超时时间
                      <input
                        value={singleForm.timeout_seconds}
                        onChange={(event) => setSingleForm((current) => ({ ...current, timeout_seconds: event.target.value }))}
                      />
                    </label>
                    <label className="workspace-field full-span">
                      用例名称
                      <input value={singleForm.case_name} onChange={(event) => setSingleForm((current) => ({ ...current, case_name: event.target.value }))} />
                    </label>
                    <label className="workspace-field full-span">
                      输入路径
                      <input value={singleForm.input_path} onChange={(event) => setSingleForm((current) => ({ ...current, input_path: event.target.value }))} />
                    </label>
                    <label className="workspace-field full-span">
                      期望输出
                      <textarea
                        rows={4}
                        value={singleForm.expected_output}
                        onChange={(event) => setSingleForm((current) => ({ ...current, expected_output: event.target.value }))}
                      />
                    </label>
                  </div>
                  <div className="button-row">
                    <button onClick={() => void handleCreateSingleTest()} type="button">发起单测</button>
                  </div>
                </article>
              </div>
              <div className="workspace-stack">
                <article className="workspace-note-block">
                  <div className="section-header">
                    <h3>单测结果对比</h3>
                    {selectedTask && <span className={`status-pill ${statusTone(selectedTask.status)}`}>{selectedTask.status}</span>}
                  </div>
                  {!selectedTask ? (
                    <div className="workspace-empty">请选择测试任务查看单测详情。</div>
                  ) : (
                    <>
                      <div className="workspace-kpi-grid">
                        <article className="workspace-kpi-card">
                          <span>通过</span>
                          <strong>{selectedTask.passed_cases}</strong>
                        </article>
                        <article className="workspace-kpi-card">
                          <span>失败</span>
                          <strong>{selectedTask.failed_cases}</strong>
                        </article>
                        <article className="workspace-kpi-card">
                          <span>实际后端</span>
                          <strong>{selectedTask.execution_backend ?? '-'}</strong>
                        </article>
                        <article className="workspace-kpi-card">
                          <span>执行模式</span>
                          <strong>{selectedTask.execution_mode}</strong>
                        </article>
                      </div>
                      {selectedTask.execution_risk && <div className="workspace-empty">风险提示：{selectedTask.execution_risk}</div>}
                      <div className="workspace-table-wrap">
                        <table className="workspace-table">
                          <thead>
                            <tr>
                              <th>用例</th>
                              <th>结果</th>
                              <th>耗时</th>
                              <th>期望 / 实际</th>
                            </tr>
                          </thead>
                          <tbody>
                            {selectedTask.cases.map((item) => (
                              <tr key={item.case_id}>
                                <td>{item.case_name}</td>
                                <td><span className={`status-pill ${statusTone(item.status)}`}>{item.status}</span></td>
                                <td>{item.duration_ms} ms</td>
                                <td>{item.expected_output ?? '-'} / {item.actual_output ?? '-'}</td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    </>
                  )}
                </article>
              </div>
            </div>
          )}

          {activeTab === 'batch' && (
            <div className="workspace-panel-grid">
              <div className="workspace-stack">
                <article className="workspace-note-block">
                  <div className="section-header">
                    <h3>批量测试向导</h3>
                    <span className="badge badge-muted">TT16</span>
                  </div>
                  <div className="workspace-form-grid">
                    <label className="workspace-field">
                      能力
                      <select
                        value={batchForm.capability_name}
                        onChange={(event) => setBatchForm((current) => ({ ...current, capability_name: event.target.value }))}
                      >
                        {dashboard.models.map((item) => (
                          <option key={`${item.capability_name}-${item.model_version}`} value={item.capability_name}>
                            {item.capability_name}
                          </option>
                        ))}
                      </select>
                    </label>
                    <label className="workspace-field">
                      模型版本
                      <select
                        value={batchForm.model_version}
                        onChange={(event) => setBatchForm((current) => ({ ...current, model_version: event.target.value }))}
                      >
                        {dashboard.models
                          .filter((item) => item.capability_name === batchForm.capability_name)
                          .map((item) => (
                            <option key={item.model_version} value={item.model_version}>
                              {item.model_version}
                            </option>
                          ))}
                      </select>
                    </label>
                    <label className="workspace-field">
                      后端
                      <select
                        value={batchForm.requested_backend}
                        onChange={(event) =>
                          setBatchForm((current) => ({
                            ...current,
                            requested_backend: event.target.value as BatchTestForm['requested_backend'],
                          }))
                        }
                      >
                        <option value="auto">auto</option>
                        <option value="gpu">gpu</option>
                        <option value="cpu">cpu</option>
                      </select>
                    </label>
                    <label className="workspace-field">
                      超时时间
                      <input value={batchForm.timeout_seconds} onChange={(event) => setBatchForm((current) => ({ ...current, timeout_seconds: event.target.value }))} />
                    </label>
                    <label className="workspace-field full-span">
                      用例清单（每行：名称|输入路径|期望输出）
                      <textarea
                        rows={8}
                        value={batchForm.cases_text}
                        onChange={(event) => setBatchForm((current) => ({ ...current, cases_text: event.target.value }))}
                      />
                    </label>
                  </div>
                  <div className="button-row">
                    <button onClick={() => void handleCreateBatchTest()} type="button">创建批量测试</button>
                  </div>
                </article>
                <article className="workspace-note-block">
                  <div className="section-header">
                    <h3>验收基线模板</h3>
                    <span className="badge badge-muted">TT17</span>
                  </div>
                  <div className="workspace-form-grid">
                    <label className="workspace-field">
                      能力
                      <input value={baselineForm.capability_name} onChange={(event) => setBaselineForm((current) => ({ ...current, capability_name: event.target.value }))} />
                    </label>
                    <label className="workspace-field">
                      场景
                      <input value={baselineForm.scenario_name} onChange={(event) => setBaselineForm((current) => ({ ...current, scenario_name: event.target.value }))} />
                    </label>
                    <label className="workspace-field">
                      P95 阈值
                      <input value={baselineForm.p95_max_ms} onChange={(event) => setBaselineForm((current) => ({ ...current, p95_max_ms: event.target.value }))} />
                    </label>
                    <label className="workspace-field">
                      最小成功率
                      <input value={baselineForm.success_rate_min} onChange={(event) => setBaselineForm((current) => ({ ...current, success_rate_min: event.target.value }))} />
                    </label>
                    <label className="workspace-field full-span">
                      说明
                      <textarea rows={3} value={baselineForm.description} onChange={(event) => setBaselineForm((current) => ({ ...current, description: event.target.value }))} />
                    </label>
                  </div>
                  <div className="button-row">
                    <button onClick={() => void handleSaveBaseline()} type="button">保存基线</button>
                  </div>
                </article>
              </div>
              <div className="workspace-stack">
                <article className="workspace-note-block">
                  <h3>批量任务与问题样本</h3>
                  <div className="workspace-list">
                    {dashboard.tasks.map((item) => (
                      <button
                        key={item.task_id}
                        className={`workspace-list-item${selectedTaskId === item.task_id ? ' active' : ''}`}
                        onClick={() => setSelectedTaskId(item.task_id)}
                        type="button"
                      >
                        <strong>任务 #{item.task_id} / {item.task_type}</strong>
                        <div className="workspace-meta-row">
                          <span>{item.capability_name}</span>
                          <span>{item.execution_mode}</span>
                          <span>{item.passed_cases}/{item.total_cases} 通过</span>
                          <span className={`status-pill ${statusTone(item.status)}`}>{item.status}</span>
                        </div>
                      </button>
                    ))}
                  </div>
                  {selectedTask && (
                    <div className="workspace-table-wrap" style={{ marginTop: 16 }}>
                      <table className="workspace-table">
                        <thead>
                          <tr>
                            <th>失败样本</th>
                            <th>输入</th>
                            <th>耗时</th>
                          </tr>
                        </thead>
                        <tbody>
                          {selectedTask.cases
                            .filter((item) => item.status !== 'passed')
                            .map((item) => (
                              <tr key={item.case_id}>
                                <td>{item.case_name}</td>
                                <td>{item.input_path}</td>
                                <td>{item.duration_ms} ms</td>
                              </tr>
                            ))}
                        </tbody>
                      </table>
                    </div>
                  )}
                </article>
              </div>
            </div>
          )}

          {activeTab === 'acceptance' && (
            <div className="workspace-panel-grid">
              <div className="workspace-stack">
                <article className="workspace-note-block">
                  <div className="section-header">
                    <h3>生产验收任务</h3>
                    <span className="badge badge-muted">TT17</span>
                  </div>
                  <div className="workspace-form-grid">
                    <label className="workspace-field">
                      镜像
                      <input value={acceptanceForm.image_uri} onChange={(event) => setAcceptanceForm((current) => ({ ...current, image_uri: event.target.value }))} />
                    </label>
                    <label className="workspace-field">
                      目标地址
                      <input value={acceptanceForm.target_base_url} onChange={(event) => setAcceptanceForm((current) => ({ ...current, target_base_url: event.target.value }))} />
                    </label>
                    <label className="workspace-field">
                      能力
                      <input value={acceptanceForm.capability_name} onChange={(event) => setAcceptanceForm((current) => ({ ...current, capability_name: event.target.value }))} />
                    </label>
                    <label className="workspace-field">
                      输入类型
                      <select
                        value={acceptanceForm.input_type}
                        onChange={(event) =>
                          setAcceptanceForm((current) => ({
                            ...current,
                            input_type: event.target.value as AcceptanceForm['input_type'],
                          }))
                        }
                      >
                        <option value="json">json</option>
                        <option value="image">image</option>
                        <option value="video">video</option>
                        <option value="pdf">pdf</option>
                      </select>
                    </label>
                    <label className="workspace-field full-span">
                      推理载荷
                      <textarea rows={4} value={acceptanceForm.infer_payload} onChange={(event) => setAcceptanceForm((current) => ({ ...current, infer_payload: event.target.value }))} />
                    </label>
                  </div>
                  <div className="button-row">
                    <button onClick={() => void handleCreateAcceptanceTask()} type="button">发起生产验收</button>
                  </div>
                </article>
              </div>
              <div className="workspace-stack">
                <article className="workspace-note-block">
                  <h3>验收脚本结果</h3>
                  <div className="workspace-list">
                    {dashboard.acceptanceTasks.map((item) => (
                      <button
                        key={item.acceptance_task_id}
                        className={`workspace-list-item${selectedAcceptanceId === item.acceptance_task_id ? ' active' : ''}`}
                        onClick={() => setSelectedAcceptanceId(item.acceptance_task_id)}
                        type="button"
                      >
                        <strong>验收 #{item.acceptance_task_id}</strong>
                        <div className="workspace-meta-row">
                          <span>{item.image_uri}</span>
                          <span>{item.passed_cases}/{item.total_cases} 通过</span>
                          <span className={`status-pill ${statusTone(item.status)}`}>{item.status}</span>
                        </div>
                      </button>
                    ))}
                  </div>
                  {selectedAcceptance && (
                    <div className="workspace-table-wrap" style={{ marginTop: 16 }}>
                      <table className="workspace-table">
                        <thead>
                          <tr>
                            <th>脚本</th>
                            <th>结果</th>
                            <th>耗时</th>
                            <th>基线</th>
                          </tr>
                        </thead>
                        <tbody>
                          {selectedAcceptance.script_results.map((item) => (
                            <tr key={item.case_name}>
                              <td>{item.case_name}</td>
                              <td><span className={`status-pill ${item.passed ? 'good' : 'danger'}`}>{item.status}</span></td>
                              <td>{item.duration_ms} ms</td>
                              <td>{item.passed_baseline == null ? '-' : item.passed_baseline ? '通过' : '失败'}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}
                </article>
              </div>
            </div>
          )}

          {activeTab === 'reports' && (
            <div className="workspace-panel-grid">
              <div className="workspace-stack">
                <article className="workspace-note-block">
                  <div className="section-header">
                    <h3>报告中心</h3>
                    <span className="badge badge-muted">TT18-TT19</span>
                  </div>
                  <div className="button-row">
                    <button type="button" onClick={() => setReportTemplateType('research')}>研发视角</button>
                    <button type="button" onClick={() => setReportTemplateType('delivery')}>交付视角</button>
                  </div>
                  <div className="workspace-list" style={{ marginTop: 16 }}>
                    {dashboard.reports.map((item) => (
                      <button
                        key={item.report_id}
                        className={`workspace-list-item${selectedReportId === item.report_id ? ' active' : ''}`}
                        onClick={() => setSelectedReportId(item.report_id)}
                        type="button"
                      >
                        <strong>报告 #{item.report_id} / {item.capability_name}</strong>
                        <div className="workspace-meta-row">
                          <span>{item.model_version}</span>
                          <span>{item.execution_mode}</span>
                          <span>{item.passed_cases}/{item.passed_cases + item.failed_cases} 通过</span>
                          <span className={`status-pill ${item.failed_cases === 0 ? 'good' : 'warn'}`}>
                            {item.failed_cases === 0 ? '可推进' : '需复核'}
                          </span>
                        </div>
                      </button>
                    ))}
                  </div>
                </article>
              </div>
              <div className="workspace-stack">
                <article className="workspace-note-block">
                  <div className="section-header">
                    <h3>报告摘要与证据链</h3>
                    {selectedReport && (
                      <span className={`status-pill ${selectedReport.failed_cases === 0 ? 'good' : 'warn'}`}>
                        {selectedReport.failed_cases === 0 ? '推送下游' : '问题回流'}
                      </span>
                    )}
                  </div>
                  {!selectedReport ? (
                    <div className="workspace-empty">请选择报告查看摘要。</div>
                  ) : (
                    <>
                      <div className="workspace-kpi-grid">
                        <article className="workspace-kpi-card">
                          <span>通过用例</span>
                          <strong>{selectedReport.passed_cases}</strong>
                        </article>
                        <article className="workspace-kpi-card">
                          <span>失败用例</span>
                          <strong>{selectedReport.failed_cases}</strong>
                        </article>
                        <article className="workspace-kpi-card">
                          <span>当前视角</span>
                          <strong>{reportTemplateType}</strong>
                        </article>
                        <article className="workspace-kpi-card">
                          <span>执行模式</span>
                          <strong>{selectedReport.execution_mode}</strong>
                        </article>
                      </div>
                      {selectedReport.execution_risk && <div className="workspace-empty">风险提示：{selectedReport.execution_risk}</div>}
                      <pre className="workspace-code-block">{JSON.stringify(selectedReport.summary, null, 2)}</pre>
                      <div className="workspace-action-row">
                        <a className="workspace-action-chip" href={reportExportUrl(selectedReport.report_id, 'json')}>导出 JSON</a>
                        <a className="workspace-action-chip" href={reportExportUrl(selectedReport.report_id, 'html')}>导出 HTML</a>
                        <a className="workspace-action-chip" href={reportExportUrl(selectedReport.report_id, 'pdf')}>导出 PDF</a>
                        {workspace.nextModule && selectedReport.failed_cases === 0 && (
                          <a className="workspace-action-chip" href={workspace.nextModule.url}>
                            推送到 {workspace.nextModule.shortTitle}
                          </a>
                        )}
                      </div>
                    </>
                  )}
                </article>
              </div>
            </div>
          )}
        </section>
      </main>
    </WorkspaceShell>
  )
}

export default App
