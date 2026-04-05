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
  available_template_types: string[]
}

type AcceptanceTaskItem = {
  acceptance_task_id: number
  task_id: number
  image_uri: string
  target_base_url: string
  capability_name: string | null
  status: string
  passed_cases: number
  failed_cases: number
}

type PerformanceBaselineItem = {
  baseline_id: number
  capability_name: string
  scenario_name: string
  p95_max_ms: number | null
  success_rate_min: number
}

type ApiListResponse<T> = {
  items: T[]
  synced_at?: string | null
}

type DashboardState = {
  models: RemoteModelItem[]
  tasks: TestTaskItem[]
  acceptanceTasks: AcceptanceTaskItem[]
  baselines: PerformanceBaselineItem[]
  reports: TestReportItem[]
  syncedAt: string | null
}

const initialState: DashboardState = {
  models: [],
  tasks: [],
  acceptanceTasks: [],
  baselines: [],
  reports: [],
  syncedAt: null,
}

const roadmapItems = [
  '单接口测试表单与测试样本上传能力',
  '批量测试编排、超时反馈与任务重试入口',
  '生产镜像验收任务与回归脚本编排',
  'C++ HTTP 主服务性能/稳定性验收阈值模板',
  '报告导出中心与交付验收视图',
  '与 ai-train、ai-prod 的跨模块联调验证',
]

const moduleLinks = [
  { id: 'ai-train', title: 'ai-train', url: import.meta.env.VITE_AI_TRAIN_URL ?? 'http://127.0.0.1:26000', summary: '标注协作、训练回显、模型 manifest' },
  { id: 'ai-test', title: 'ai-test', url: import.meta.env.VITE_AI_TEST_URL ?? 'http://127.0.0.1:26001', summary: '测试任务、验收基线、双视角报告' },
  { id: 'ai-license-mgr', title: 'ai-license-mgr', url: import.meta.env.VITE_AI_LICENSE_MGR_URL ?? 'http://127.0.0.1:26002', summary: '密钥轮转、策略签发、license_tool' },
  { id: 'ai-builder', title: 'ai-builder', url: import.meta.env.VITE_AI_BUILDER_URL ?? 'http://127.0.0.1:26003', summary: '构建任务、delivery_package、归档下载' },
  { id: 'ai-prod', title: 'ai-prod', url: import.meta.env.VITE_AI_PROD_URL ?? 'http://127.0.0.1:26004', summary: '能力目录、在线控制台、revision 诊断' },
] as const

const integrationReviewItems = [
  '统一核对五个模块入口是否可访问，并确认关键工作台能进入核心页面。',
  '统一核对模型、授权、构建、运行、验收链路的字段命名与状态表达。',
  '统一核对交付物、验收报告与运行诊断信息在跨模块联调中的跳转与留痕。',
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
        const [models, tasks, acceptanceTasks, baselines, reports] = await Promise.all([
          fetchList<RemoteModelItem>('/api/v1/remote-models'),
          fetchList<TestTaskItem>('/api/v1/test-tasks'),
          fetchList<AcceptanceTaskItem>('/api/v1/acceptance-tasks'),
          fetchList<PerformanceBaselineItem>('/api/v1/performance-baselines'),
          fetchList<TestReportItem>('/api/v1/test-reports'),
        ])
        if (!cancelled) {
          setDashboard({
            models: models.items,
            tasks: tasks.items,
            acceptanceTasks: acceptanceTasks.items,
            baselines: baselines.items,
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
        description: '支持研发验收 / 交付验收双视角的 HTML / JSON / PDF 报告生成与导出。',
      },
      {
        title: '验收任务',
        count: dashboard.acceptanceTasks.length,
        description: '面向 ai-prod 生产镜像的验收脚本编排与结果留痕。',
      },
      {
        title: '性能基线',
        count: dashboard.baselines.length,
        description: '面向 C++ HTTP 主服务的性能/稳定性验收阈值模板。',
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
            生产镜像验收、性能基线比对与测试报告导出基础能力。
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
            <h2>跨模块联调导航</h2>
            <span className="badge badge-muted">R7 第二轮</span>
          </div>
          <div className="module-grid">
            {moduleLinks.map((item) => (
              <a
                key={item.id}
                className={`module-link-card${item.id === 'ai-test' ? ' active' : ''}`}
                href={item.url}
              >
                <div className="module-link-header">
                  <strong>{item.title}</strong>
                  <span className="module-tag">{item.id === 'ai-test' ? '当前模块' : '联调入口'}</span>
                </div>
                <p>{item.summary}</p>
              </a>
            ))}
          </div>
          <ul className="module-checklist">
            {integrationReviewItems.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </section>
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
              <h3>验收任务</h3>
              <table>
                <thead>
                  <tr>
                    <th>镜像</th>
                    <th>状态</th>
                    <th>通过/失败</th>
                  </tr>
                </thead>
                <tbody>
                  {dashboard.acceptanceTasks.map((item) => (
                    <tr key={item.acceptance_task_id}>
                      <td>{item.image_uri}</td>
                      <td>{item.status}</td>
                      <td>
                        {item.passed_cases}/{item.failed_cases}
                      </td>
                    </tr>
                  ))}
                  {dashboard.acceptanceTasks.length === 0 && (
                    <tr>
                      <td colSpan={3}>暂无验收任务</td>
                    </tr>
                  )}
                </tbody>
              </table>
            </article>

            <article className="sub-panel">
              <h3>性能基线</h3>
              <table>
                <thead>
                  <tr>
                    <th>能力</th>
                    <th>场景</th>
                    <th>P95 阈值</th>
                  </tr>
                </thead>
                <tbody>
                  {dashboard.baselines.map((item) => (
                    <tr key={item.baseline_id}>
                      <td>{item.capability_name}</td>
                      <td>{item.scenario_name}</td>
                      <td>{item.p95_max_ms ?? '-'}</td>
                    </tr>
                  ))}
                  {dashboard.baselines.length === 0 && (
                    <tr>
                      <td colSpan={3}>暂无性能基线</td>
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
                    <th>模板</th>
                    <th>通过/失败</th>
                  </tr>
                </thead>
                <tbody>
                  {dashboard.reports.map((item) => (
                    <tr key={item.report_id}>
                      <td>#{item.report_id}</td>
                      <td>{item.capability_name}</td>
                      <td>{item.available_template_types.join(' / ')}</td>
                      <td>
                        {item.passed_cases}/{item.failed_cases}
                      </td>
                    </tr>
                  ))}
                  {dashboard.reports.length === 0 && (
                    <tr>
                      <td colSpan={4}>暂无测试报告</td>
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
              <li>C++ HTTP 主服务性能/稳定性验收基线</li>
              <li>研发验收 / 交付验收双视角报告模板</li>
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
