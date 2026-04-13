import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import type {
  RemoteModelItem,
  RemoteCapabilityItem,
  TestTaskItem,
  AcceptanceTaskItem,
  PerformanceBaselineItem,
  TestReportItem,
} from '../types'
import { fetchList, request, statusTone } from '../api'
import { buildOverviewInsights, pickBestReport } from '../enterprise'

type DashboardState = {
  models: RemoteModelItem[]
  capabilities: RemoteCapabilityItem[]
  tasks: TestTaskItem[]
  acceptanceTasks: AcceptanceTaskItem[]
  baselines: PerformanceBaselineItem[]
  reports: TestReportItem[]
  syncedAt: string | null
}

const initialState: DashboardState = {
  models: [],
  capabilities: [],
  tasks: [],
  acceptanceTasks: [],
  baselines: [],
  reports: [],
  syncedAt: null,
}

export function OverviewPage() {
  const navigate = useNavigate()
  const [dashboard, setDashboard] = useState<DashboardState>(initialState)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [actionMessage, setActionMessage] = useState<string | null>(null)
  const [capabilityQuery, setCapabilityQuery] = useState('')
  const [taskTypeFilter, setTaskTypeFilter] = useState('all')

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
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : '加载失败')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    void loadDashboard()
  }, [])

  const overviewInsights = useMemo(
    () => buildOverviewInsights(dashboard),
    [dashboard],
  )
  const bestReport = useMemo(() => pickBestReport(dashboard.reports), [dashboard.reports])
  const filteredCapabilities = useMemo(
    () =>
      dashboard.capabilities.filter((item) => {
        const matchQuery =
          capabilityQuery.trim() === '' ||
          item.capability_name.toLowerCase().includes(capabilityQuery.trim().toLowerCase()) ||
          item.display_name.toLowerCase().includes(capabilityQuery.trim().toLowerCase())
        const matchTaskType = taskTypeFilter === 'all' || item.task_type === taskTypeFilter
        return matchQuery && matchTaskType
      }),
    [capabilityQuery, dashboard.capabilities, taskTypeFilter],
  )
  const recommendedModels = dashboard.models.slice(0, 6)
  const riskyTasks = dashboard.tasks.filter((item) => item.failed_cases > 0 || item.status === 'failed').slice(0, 4)
  const runningAcceptance = dashboard.acceptanceTasks.filter((item) => item.status === 'running').slice(0, 3)

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

  const taskTypeOptions = Array.from(new Set(dashboard.capabilities.map((item) => item.task_type).filter(Boolean)))

  return (
    <div className="page-container">
      <section className="panel">
        <div className="section-header">
          <div>
            <h2>测试中枢首页</h2>
            <p>先完成参考工程中的“能力选择一级页”收口，再把首页升级为测试、验收、报告的统一调度入口。</p>
          </div>
          <span className="badge">TT20-TT24</span>
        </div>
        {loading && <p className="info-text">正在加载测试中枢数据...</p>}
        {error && <p className="error-text">数据加载失败：{error}</p>}
        {actionMessage && <p className="success-text">{actionMessage}</p>}
        <div className="enterprise-hero-grid">
          <article className="enterprise-score-card">
            <span>测试体系就绪度</span>
            <strong>{overviewInsights.overallScore}</strong>
            <p>综合模型入测、任务执行、报告沉淀与生产验收四段链路得出。</p>
          </article>
          <article className="enterprise-note-card">
            <strong>同步与值守</strong>
            <p>最近同步时间：{dashboard.syncedAt ?? '尚未同步'}。</p>
            <div className="workspace-action-row">
              <button className="action-button" onClick={() => void handleSyncCatalog()} type="button">同步 ai-train 模型目录</button>
              <button className="action-button" onClick={() => navigate('/single')} type="button">进入单测</button>
              <button className="action-button" onClick={() => navigate('/batch')} type="button">进入批测</button>
            </div>
          </article>
        </div>
        <div className="enterprise-stage-grid">
          {overviewInsights.stageCards.map((item) => (
            <article key={item.title} className={`enterprise-stage-card tone-${item.tone}`}>
              <span>{item.title}</span>
              <strong>{item.score}</strong>
              <p>{item.detail}</p>
              <small>当前对象：{item.count}</small>
            </article>
          ))}
        </div>
      </section>

      <section className="panel">
        <div className="section-header">
          <div>
            <h3>能力选择</h3>
            <p>参考工程的一层能力入口，先从能力和版本找到测试切入点。</p>
          </div>
        </div>
        <div className="workspace-form-grid">
          <label className="workspace-field">
            搜索能力
            <input
              value={capabilityQuery}
              onChange={(event) => setCapabilityQuery(event.target.value)}
              placeholder="按能力名或显示名搜索"
            />
          </label>
          <label className="workspace-field">
            任务类型
            <select value={taskTypeFilter} onChange={(event) => setTaskTypeFilter(event.target.value)}>
              <option value="all">全部</option>
              {taskTypeOptions.map((item) => (
                <option key={item} value={item ?? ''}>{item}</option>
              ))}
            </select>
          </label>
        </div>
        <div className="capability-card-grid">
          {filteredCapabilities.length === 0 && <div className="workspace-empty">暂无符合筛选条件的能力。</div>}
          {filteredCapabilities.map((capability) => {
            const model = dashboard.models.find((item) => item.capability_name === capability.capability_name)
            const lastTask = dashboard.tasks.find((item) => item.capability_name === capability.capability_name)
            return (
              <article key={capability.capability_name} className="capability-card">
                <div className="section-header">
                  <div>
                    <h3>{capability.display_name}</h3>
                    <p>{capability.capability_name}</p>
                  </div>
                  <span className={`status-pill ${statusTone(model?.status ?? capability.dataset_status)}`}>{model?.status ?? capability.dataset_status}</span>
                </div>
                <div className="workspace-meta-column">
                  <span>任务类型：{capability.task_type ?? 'unknown'}</span>
                  <span>当前模型：{model?.model_version ?? '暂无模型'}</span>
                  <span>最后测试：{lastTask?.completed_at ?? '尚无测试记录'}</span>
                  <span>来源数据集：{capability.dataset_path}</span>
                </div>
                <div className="workspace-action-row">
                  <button className="action-button" onClick={() => navigate('/single')} type="button">单样本测试</button>
                  <button className="action-button" onClick={() => navigate('/batch')} type="button">批量测试</button>
                  <button className="action-button" onClick={() => navigate('/reports')} type="button">查看报告</button>
                </div>
              </article>
            )
          })}
        </div>
      </section>

      <section className="panel">
        <div className="workspace-summary-grid">
          <article className="workspace-summary-card">
            <h3>待优先测试模型</h3>
            <div className="workspace-list">
              {recommendedModels.map((item) => (
                <button key={`${item.capability_name}-${item.model_version}`} className="workspace-list-item" onClick={() => navigate('/single')} type="button">
                  <strong>{item.capability_name}</strong>
                  <div className="workspace-meta-row">
                    <span>{item.model_version}</span>
                    <span>{item.backend_type}</span>
                    <span className={`status-pill ${statusTone(item.status)}`}>{item.status}</span>
                  </div>
                </button>
              ))}
            </div>
          </article>
          <article className="workspace-summary-card">
            <h3>问题任务值守</h3>
            {riskyTasks.length === 0 ? (
              <div className="workspace-empty">当前无失败任务，测试队列状态良好。</div>
            ) : (
              <div className="workspace-list">
                {riskyTasks.map((item) => (
                  <button key={item.task_id} className="workspace-list-item" onClick={() => navigate(item.task_type === 'batch' ? '/batch' : '/single')} type="button">
                    <strong>任务 #{item.task_id}</strong>
                    <div className="workspace-meta-row">
                      <span>{item.capability_name}</span>
                      <span>{item.failed_cases} 个失败</span>
                      <span className={`status-pill ${statusTone(item.status)}`}>{item.status}</span>
                    </div>
                  </button>
                ))}
              </div>
            )}
          </article>
          <article className="workspace-summary-card">
            <h3>生产验收关注项</h3>
            {runningAcceptance.length === 0 ? (
              <div className="workspace-empty">当前无运行中的生产验收任务。</div>
            ) : (
              <div className="workspace-list">
                {runningAcceptance.map((item) => (
                  <button key={item.acceptance_task_id} className="workspace-list-item" onClick={() => navigate('/acceptance')} type="button">
                    <strong>验收 #{item.acceptance_task_id}</strong>
                    <div className="workspace-meta-row">
                      <span>{item.image_uri}</span>
                      <span>{item.target_base_url}</span>
                      <span className={`status-pill ${statusTone(item.status)}`}>{item.status}</span>
                    </div>
                  </button>
                ))}
              </div>
            )}
          </article>
        </div>
      </section>

      <section className="panel">
        <div className="enterprise-two-column">
          <div className="enterprise-stack">
            {overviewInsights.risks.map((item) => (
              <article key={item.title} className={`enterprise-note-card tone-${item.tone}`}>
                <strong>{item.title}</strong>
                <p>{item.detail}</p>
              </article>
            ))}
          </div>
          <article className="enterprise-note-card">
            <strong>下一步推荐动作</strong>
            <ul className="enterprise-list">
              {overviewInsights.actions.map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ul>
            {bestReport && (
              <div className="enterprise-inline-card tone-good" style={{ marginTop: 12 }}>
                <strong>当前最佳报告候选</strong>
                <p>{bestReport.capability_name} / {bestReport.model_version} · {bestReport.failed_cases === 0 ? '可下游推进' : '需复核'}</p>
              </div>
            )}
          </article>
        </div>
      </section>
    </div>
  )
}
