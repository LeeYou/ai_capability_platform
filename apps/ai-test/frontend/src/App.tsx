import { useEffect, useMemo, useState } from 'react'
import './App.css'

type RemoteModelItem = {
  capability_name: string
  model_version: string
  backend_type: string
  status: string
}

type TestTaskItem = {
  task_id: number
  task_type: string
  capability_name: string
  model_version: string
  execution_backend: string | null
  status: string
  total_cases: number
  passed_cases: number
  failed_cases: number
}

type TestReportItem = {
  report_id: number
  task_id: number
  capability_name: string
  model_version: string
  status: string
  passed_cases: number
  failed_cases: number
}

type ApiListResponse<T> = {
  items: T[]
  synced_at?: string | null
}

type DashboardState = {
  models: RemoteModelItem[]
  tasks: TestTaskItem[]
  reports: TestReportItem[]
  syncedAt: string | null
}

const initialState: DashboardState = {
  models: [],
  tasks: [],
  reports: [],
  syncedAt: null,
}

const roadmapItems = [
  '单接口测试表单与测试样本上传能力',
  '批量测试编排、超时反馈与任务重试入口',
  '报告导出中心与交付验收视图',
  '与 ai-train、ai-prod 的跨模块联调验证',
]

async function fetchList<T>(path: string): Promise<ApiListResponse<T>> {
  const apiBaseUrl = import.meta.env.VITE_API_BASE_URL ?? ''
  const response = await fetch(`${apiBaseUrl}${path}`)
  if (!response.ok) {
    throw new Error(`请求失败：${path}`)
  }
  return (await response.json()) as ApiListResponse<T>
}

function App() {
  const [dashboard, setDashboard] = useState<DashboardState>(initialState)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false

    async function loadDashboard(): Promise<void> {
      try {
        setLoading(true)
        setError(null)
        const [models, tasks, reports] = await Promise.all([
          fetchList<RemoteModelItem>('/api/v1/remote-models'),
          fetchList<TestTaskItem>('/api/v1/test-tasks'),
          fetchList<TestReportItem>('/api/v1/test-reports'),
        ])
        if (!cancelled) {
          setDashboard({
            models: models.items,
            tasks: tasks.items,
            reports: reports.items,
            syncedAt: models.synced_at ?? null,
          })
        }
      } catch (loadError) {
        if (!cancelled) {
          setError(loadError instanceof Error ? loadError.message : '加载失败')
        }
      } finally {
        if (!cancelled) {
          setLoading(false)
        }
      }
    }

    void loadDashboard()

    return () => {
      cancelled = true
    }
  }, [])

  const overviewCards = useMemo(
    () => [
      {
        title: '远端模型目录',
        count: dashboard.models.length,
        description: '从 ai-train 拉取模型与能力信息，支持本地快照回退。',
      },
      {
        title: '测试任务',
        count: dashboard.tasks.length,
        description: '支持单接口测试、批量测试、超时控制与 GPU/CPU 回退。',
      },
      {
        title: '测试报告',
        count: dashboard.reports.length,
        description: '支持 HTML / JSON / PDF 报告生成与导出。',
      },
    ],
    [dashboard],
  )

  return (
    <div className="page">
      <header className="hero">
        <div className="hero-text">
          <p className="eyebrow">北京爱知之星科技股份有限公司（Agile Star）</p>
          <h1>ai-test 管理台</h1>
          <p>
            面向模型验收与批量测试场景的统一测试子系统，当前已具备模型目录同步、测试执行、
            结果持久化与测试报告导出基础能力。
          </p>
        </div>
        <div className="hero-panel">
          <div>
            <span className="label">服务端口</span>
            <strong>26001</strong>
          </div>
          <div>
            <span className="label">技术栈</span>
            <strong>FastAPI + React + Vite</strong>
          </div>
          <div>
            <span className="label">最近模型同步</span>
            <strong>{dashboard.syncedAt ?? '暂无同步记录'}</strong>
          </div>
        </div>
      </header>

      <main className="content">
        <section className="panel">
          <div className="section-header">
            <h2>当前概览</h2>
            <span className="badge">ai-test 首轮实现中</span>
          </div>
          {loading && <p className="info-text">正在加载 ai-test 当前数据...</p>}
          {error && <p className="error-text">数据加载失败：{error}</p>}
          <div className="card-grid">
            {overviewCards.map((card) => (
              <article key={card.title} className="card">
                <h3>{card.title}</h3>
                <strong>{card.count}</strong>
                <p>{card.description}</p>
              </article>
            ))}
          </div>
        </section>

        <section className="panel">
          <div className="section-header">
            <h2>实时数据看板</h2>
            <span className="badge badge-muted">接口驱动</span>
          </div>
          <div className="table-grid">
            <article className="sub-panel">
              <h3>远端模型</h3>
              <table>
                <thead>
                  <tr>
                    <th>能力</th>
                    <th>版本</th>
                    <th>后端</th>
                  </tr>
                </thead>
                <tbody>
                  {dashboard.models.map((item) => (
                    <tr key={`${item.capability_name}-${item.model_version}`}>
                      <td>{item.capability_name}</td>
                      <td>{item.model_version}</td>
                      <td>{item.backend_type}</td>
                    </tr>
                  ))}
                  {dashboard.models.length === 0 && (
                    <tr>
                      <td colSpan={3}>暂无模型目录</td>
                    </tr>
                  )}
                </tbody>
              </table>
            </article>

            <article className="sub-panel">
              <h3>测试任务</h3>
              <table>
                <thead>
                  <tr>
                    <th>任务</th>
                    <th>状态</th>
                    <th>通过/失败</th>
                  </tr>
                </thead>
                <tbody>
                  {dashboard.tasks.map((item) => (
                    <tr key={item.task_id}>
                      <td>{item.task_type}</td>
                      <td>{item.status}</td>
                      <td>
                        {item.passed_cases}/{item.failed_cases}
                      </td>
                    </tr>
                  ))}
                  {dashboard.tasks.length === 0 && (
                    <tr>
                      <td colSpan={3}>暂无测试任务</td>
                    </tr>
                  )}
                </tbody>
              </table>
            </article>

            <article className="sub-panel">
              <h3>测试报告</h3>
              <table>
                <thead>
                  <tr>
                    <th>报告</th>
                    <th>能力</th>
                    <th>通过/失败</th>
                  </tr>
                </thead>
                <tbody>
                  {dashboard.reports.map((item) => (
                    <tr key={item.report_id}>
                      <td>#{item.report_id}</td>
                      <td>{item.capability_name}</td>
                      <td>
                        {item.passed_cases}/{item.failed_cases}
                      </td>
                    </tr>
                  ))}
                  {dashboard.reports.length === 0 && (
                    <tr>
                      <td colSpan={3}>暂无测试报告</td>
                    </tr>
                  )}
                </tbody>
              </table>
            </article>
          </div>
        </section>

        <section className="panel split">
          <article className="sub-panel">
            <h2>本轮已落地能力</h2>
            <ul>
              <li>ai-train 模型目录同步与本地快照回退</li>
              <li>单接口测试与批量测试</li>
              <li>GPU 优先 / CPU 回退执行策略</li>
              <li>HTML / JSON / PDF 报告生成与导出</li>
            </ul>
          </article>
          <article className="sub-panel">
            <h2>后续增强方向</h2>
            <ul>
              {roadmapItems.map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ul>
          </article>
        </section>
      </main>
    </div>
  )
}

export default App
