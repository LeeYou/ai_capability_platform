import { useEffect, useMemo, useState } from 'react'
import './App.css'

type PlatformTargetItem = {
  target_name: string
  os_name: string
  arch_name: string
  artifact_format: string
  toolchain_name: string
  supports_native_build: boolean
  supports_jni: boolean
}

type CatalogCapabilityItem = {
  capability_name: string
  display_name: string
  dataset_status: string
}

type CatalogModelItem = {
  capability_name: string
  model_version: string
  backend_type: string
  status: string
}

type LicenseIssueItem = {
  issue_record_id: number
  customer_code: string
  key_name: string
  status: string
  capability_scope: string[]
}

type BuildTaskItem = {
  task_id: number
  task_name: string
  capability_name: string
  model_version: string
  status: string
  requested_targets: string[]
}

type BuildTargetItem = {
  target_id: number
  target_name: string
  build_mode: string
  status: string
  checksum: string
}

type BuildArtifactItem = {
  artifact_id: number
  artifact_type: string
  relative_path: string
}

type CatalogResponse = {
  capabilities: CatalogCapabilityItem[]
  models: CatalogModelItem[]
  license_issues: LicenseIssueItem[]
  synced_at: string | null
}

type ListResponse<T> = {
  items: T[]
}

type DashboardState = {
  platforms: PlatformTargetItem[]
  catalog: CatalogResponse
  buildTasks: BuildTaskItem[]
  buildTargets: BuildTargetItem[]
  artifacts: BuildArtifactItem[]
}

const initialState: DashboardState = {
  platforms: [],
  catalog: {
    capabilities: [],
    models: [],
    license_issues: [],
    synced_at: null,
  },
  buildTasks: [],
  buildTargets: [],
  artifacts: [],
}

const roadmapItems = [
  '补充在线创建构建任务与参数编排表单',
  '扩展 Windows 真实交叉编译环境与 JNI 真正产物构建',
  '接入更多 ABI 模板、runtime 层和依赖说明生成',
  '与 ai-prod / SDK 模块联调交付物消费链路',
]

async function fetchJson<T>(path: string): Promise<T> {
  const apiBaseUrl = import.meta.env.VITE_API_BASE_URL ?? ''
  const response = await fetch(`${apiBaseUrl}${path}`)
  if (!response.ok) {
    throw new Error(`请求失败：${path}`)
  }
  return (await response.json()) as T
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
        const [platforms, catalog, buildTasks, buildTargets, artifacts] = await Promise.all([
          fetchJson<ListResponse<PlatformTargetItem>>('/api/v1/platform-targets'),
          fetchJson<CatalogResponse>('/api/v1/catalog'),
          fetchJson<ListResponse<BuildTaskItem>>('/api/v1/build-tasks'),
          fetchJson<ListResponse<BuildTargetItem>>('/api/v1/build-targets'),
          fetchJson<ListResponse<BuildArtifactItem>>('/api/v1/artifacts'),
        ])
        if (!cancelled) {
          setDashboard({
            platforms: platforms.items,
            catalog,
            buildTasks: buildTasks.items,
            buildTargets: buildTargets.items,
            artifacts: artifacts.items,
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
        title: '平台矩阵',
        count: dashboard.platforms.length,
        description: '覆盖 Linux / Windows 与可选 JNI 的交付目标矩阵。',
      },
      {
        title: '能力目录',
        count: dashboard.catalog.capabilities.length,
        description: '从 ai-train 同步能力与模型信息，驱动推理库构建。',
      },
      {
        title: '授权记录',
        count: dashboard.catalog.license_issues.length,
        description: '从 ai-license-mgr 同步授权记录，控制交付打包范围。',
      },
      {
        title: '构建任务',
        count: dashboard.buildTasks.length,
        description: '跟踪任务、构建目标、校验摘要与交付归档。',
      },
    ],
    [dashboard],
  )

  return (
    <div className="page">
      <header className="hero">
        <div className="hero-text">
          <p className="eyebrow">北京爱知之星科技股份有限公司（Agile Star）</p>
          <h1>ai-builder 推理库构建台</h1>
          <p>
            面向多平台交付推理库的构建子系统，当前已具备能力/授权同步、平台矩阵、构建任务、标准 C ABI、
            Linux 原生构建、Windows/JNI 模板交付与产物归档能力。
          </p>
        </div>
        <div className="hero-panel">
          <div>
            <span className="label">服务端口</span>
            <strong>26003</strong>
          </div>
          <div>
            <span className="label">技术栈</span>
            <strong>FastAPI + React + C++ + CMake</strong>
          </div>
          <div>
            <span className="label">标准目录</span>
            <strong>/data/ai_capability_platform/libs</strong>
          </div>
        </div>
      </header>

      <main className="content">
        <section className="panel">
          <div className="section-header">
            <h2>当前概览</h2>
            <span className="badge">ai-builder 首轮实现中</span>
          </div>
          {loading && <p className="info-text">正在加载 ai-builder 当前数据...</p>}
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
            <h2>平台矩阵与外部目录</h2>
            <span className="badge badge-muted">
              最近同步：{dashboard.catalog.synced_at ?? '未同步'}
            </span>
          </div>
          <div className="table-grid">
            <article className="sub-panel">
              <h3>平台矩阵</h3>
              <table>
                <thead>
                  <tr>
                    <th>目标</th>
                    <th>工具链</th>
                    <th>JNI</th>
                  </tr>
                </thead>
                <tbody>
                  {dashboard.platforms.map((item) => (
                    <tr key={item.target_name}>
                      <td>{item.target_name}</td>
                      <td>{item.toolchain_name}</td>
                      <td>{item.supports_jni ? '支持' : '否'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </article>

            <article className="sub-panel">
              <h3>能力与模型</h3>
              <table>
                <thead>
                  <tr>
                    <th>能力</th>
                    <th>模型版本</th>
                    <th>状态</th>
                  </tr>
                </thead>
                <tbody>
                  {dashboard.catalog.models.map((item) => (
                    <tr key={`${item.capability_name}-${item.model_version}`}>
                      <td>{item.capability_name}</td>
                      <td>{item.model_version}</td>
                      <td>{item.status}</td>
                    </tr>
                  ))}
                  {dashboard.catalog.models.length === 0 && (
                    <tr>
                      <td colSpan={3}>暂无模型目录</td>
                    </tr>
                  )}
                </tbody>
              </table>
            </article>

            <article className="sub-panel">
              <h3>授权记录</h3>
              <table>
                <thead>
                  <tr>
                    <th>ID</th>
                    <th>客户</th>
                    <th>能力范围</th>
                  </tr>
                </thead>
                <tbody>
                  {dashboard.catalog.license_issues.map((item) => (
                    <tr key={item.issue_record_id}>
                      <td>{item.issue_record_id}</td>
                      <td>{item.customer_code}</td>
                      <td>{item.capability_scope.join(', ') || '全部'}</td>
                    </tr>
                  ))}
                  {dashboard.catalog.license_issues.length === 0 && (
                    <tr>
                      <td colSpan={3}>暂无授权记录</td>
                    </tr>
                  )}
                </tbody>
              </table>
            </article>
          </div>
        </section>

        <section className="panel">
          <div className="section-header">
            <h2>构建任务与产物</h2>
            <span className="badge badge-muted">真实查询接口</span>
          </div>
          <div className="table-grid">
            <article className="sub-panel">
              <h3>构建任务</h3>
              <table>
                <thead>
                  <tr>
                    <th>任务</th>
                    <th>能力</th>
                    <th>目标</th>
                  </tr>
                </thead>
                <tbody>
                  {dashboard.buildTasks.map((item) => (
                    <tr key={item.task_id}>
                      <td>{item.task_name}</td>
                      <td>{item.capability_name}</td>
                      <td>{item.requested_targets.join(', ')}</td>
                    </tr>
                  ))}
                  {dashboard.buildTasks.length === 0 && (
                    <tr>
                      <td colSpan={3}>暂无构建任务</td>
                    </tr>
                  )}
                </tbody>
              </table>
            </article>

            <article className="sub-panel">
              <h3>构建目标</h3>
              <table>
                <thead>
                  <tr>
                    <th>目标</th>
                    <th>模式</th>
                    <th>状态</th>
                  </tr>
                </thead>
                <tbody>
                  {dashboard.buildTargets.map((item) => (
                    <tr key={item.target_id}>
                      <td>{item.target_name}</td>
                      <td>{item.build_mode}</td>
                      <td>{item.status}</td>
                    </tr>
                  ))}
                  {dashboard.buildTargets.length === 0 && (
                    <tr>
                      <td colSpan={3}>暂无构建目标</td>
                    </tr>
                  )}
                </tbody>
              </table>
            </article>

            <article className="sub-panel">
              <h3>产物记录</h3>
              <table>
                <thead>
                  <tr>
                    <th>类型</th>
                    <th>路径</th>
                  </tr>
                </thead>
                <tbody>
                  {dashboard.artifacts.map((item) => (
                    <tr key={item.artifact_id}>
                      <td>{item.artifact_type}</td>
                      <td>{item.relative_path}</td>
                    </tr>
                  ))}
                  {dashboard.artifacts.length === 0 && (
                    <tr>
                      <td colSpan={2}>暂无产物记录</td>
                    </tr>
                  )}
                </tbody>
              </table>
            </article>
          </div>
        </section>

        <section className="panel split">
          <article className="sub-panel">
            <h2>实现说明</h2>
            <ul>
              <li>统一使用标准 C ABI 与头文件模板。</li>
              <li>Linux x86_64 采用原生 CMake 构建，其余平台先输出受控交付模板。</li>
              <li>构建参数固定化，避免任意命令拼接执行风险。</li>
              <li>产物包含 lib / include / license / manifest / archive 目录结构。</li>
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
