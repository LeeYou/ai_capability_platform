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

  return (
    <div className="page-container">
      <section className="panel">
        <div className="section-header">
          <div>
            <h2>首页概览</h2>
            <p>优先回答：哪些模型待测、哪些任务异常、哪些结果可以进入下游。</p>
          </div>
          <span className="badge">TT15-TT19</span>
        </div>
        {loading && <p className="info-text">正在加载测试中枢数据...</p>}
        {error && <p className="error-text">数据加载失败：{error}</p>}
        {actionMessage && <p className="success-text">{actionMessage}</p>}
        <div className="button-row" style={{ marginBottom: 16 }}>
          <button className="action-button" onClick={() => void handleSyncCatalog()} type="button">
            同步 ai-train 模型目录
          </button>
        </div>
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
                      navigate('/single')
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
                      navigate(item.task_type === 'batch' ? '/batch' : '/single')
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
        <div className="workspace-panel-grid">
          <div className="workspace-stack">
            <article className="workspace-note-block">
              <h3>当前建议动作</h3>
              <ul>
                <li>先从"单测工作台"验证最新模型的单样本表现。</li>
                <li>再通过"批量测试"沉淀错误样本与指标分布。</li>
                <li>最后用"生产验收"固化公开 API 与压力基线结论。</li>
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
                    className="workspace-list-item"
                    onClick={() => {
                      navigate(item.task_type === 'batch' ? '/batch' : '/single')
                    }}
                    type="button"
                  >
                    <strong>任务 #{item.task_id} / {item.task_type}</strong>
                    <div className="workspace-meta-row">
                      <span>{item.capability_name}</span>
                      <span>{item.model_version}</span>
                      <span>{item.passed_cases}/{item.total_cases} 通过</span>
                      <span className={`status-pill ${statusTone(item.status)}`}>{item.status}</span>
                    </div>
                  </button>
                ))}
              </div>
            </article>
          </div>
        </div>
      </section>
    </div>
  )
}
