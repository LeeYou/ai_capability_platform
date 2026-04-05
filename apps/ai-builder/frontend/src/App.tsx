import { useEffect, useMemo, useState } from 'react'
import './App.css'
import '../../../frontend-common/src/r7Workspace.css'
import { buildR7Workspace } from '../../../frontend-common/src/r7Workspace.ts'

type PlatformTargetItem = {
  target_name: string
  os_name: string
  arch_name: string
  artifact_format: string
  toolchain_name: string
  supports_native_build: boolean
  supports_jni: boolean
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

type CatalogResponse = {
  capabilities: { capability_name: string; display_name: string; dataset_status: string }[]
  models: CatalogModelItem[]
  license_issues: LicenseIssueItem[]
  license_policies: { policy_id: number; policy_name: string; customer_code: string; status: string }[]
  synced_at: string | null
}

type BuildTaskItem = {
  task_id: number
  task_name: string
  capability_name: string
  model_version: string
  issue_record_id: number
  requested_targets: string[]
  jni_enabled: boolean
  status: string
  build_root_path: string
  log_path: string
  manifest_path?: string | null
  delivery_package_dir?: string | null
  delivery_package_archive_path?: string | null
}

type BuildTargetItem = {
  target_id: number
  task_id: number
  target_name: string
  build_mode: string
  status: string
  checksum: string
  binary_path: string
  download_archive_path: string
}

type BuildArtifactItem = {
  artifact_id: number
  task_id: number
  target_id: number
  artifact_type: string
  relative_path: string
  absolute_path: string
  checksum: string
}

type BuildTaskDetail = BuildTaskItem & {
  targets: BuildTargetItem[]
  artifacts: BuildArtifactItem[]
  manifest: {
    manifest_version: string
    manifest_path: string
    dependency_summary: Record<string, unknown>
    manifest: Record<string, unknown>
  } | null
}

type AuditLogItem = {
  happened_at_cst: string
  action: string
  entity_type: string
  entity_id: string
  detail: Record<string, unknown>
}

type ListResponse<T> = { items: T[] }

type DashboardState = {
  platforms: PlatformTargetItem[]
  catalog: CatalogResponse
  buildTasks: BuildTaskItem[]
  auditLogs: AuditLogItem[]
}

type BuildFormState = {
  task_name: string
  capability_name: string
  model_version: string
  issue_record_id: string
  requested_targets: string
  jni_enabled: boolean
}

const apiBaseUrl = import.meta.env.VITE_API_BASE_URL ?? ''
const workspace = buildR7Workspace(import.meta.env, 'ai-builder')

const tabs = ['overview', 'build', 'detail'] as const
type TabKey = (typeof tabs)[number]

const initialState: DashboardState = {
  platforms: [],
  catalog: {
    capabilities: [],
    models: [],
    license_issues: [],
    license_policies: [],
    synced_at: null,
  },
  buildTasks: [],
  auditLogs: [],
}

const initialBuildForm: BuildFormState = {
  task_name: '',
  capability_name: '',
  model_version: '',
  issue_record_id: '',
  requested_targets: '',
  jni_enabled: false,
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${apiBaseUrl}${path}`, {
    headers: {
      'Content-Type': 'application/json',
      ...(init?.headers ?? {}),
    },
    ...init,
  })
  if (!response.ok) {
    const message = await response.text()
    throw new Error(message || `请求失败：${path}`)
  }
  return (await response.json()) as T
}

async function fetchList<T>(path: string): Promise<T[]> {
  const payload = await request<ListResponse<T>>(path)
  return payload.items
}

function App() {
  const [activeTab, setActiveTab] = useState<TabKey>('overview')
  const [dashboard, setDashboard] = useState<DashboardState>(initialState)
  const [selectedTaskId, setSelectedTaskId] = useState<number | null>(null)
  const [selectedTaskDetail, setSelectedTaskDetail] = useState<BuildTaskDetail | null>(null)
  const [buildForm, setBuildForm] = useState<BuildFormState>(initialBuildForm)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [actionMessage, setActionMessage] = useState<string | null>(null)

  async function loadDashboard(): Promise<void> {
    setLoading(true)
    setError(null)
    try {
      const [platforms, catalog, buildTasks, auditLogs] = await Promise.all([
        fetchList<PlatformTargetItem>('/api/v1/platform-targets'),
        request<CatalogResponse>('/api/v1/catalog'),
        fetchList<BuildTaskItem>('/api/v1/build-tasks'),
        fetchList<AuditLogItem>('/api/v1/audit-logs?limit=8'),
      ])
      setDashboard({ platforms, catalog, buildTasks, auditLogs })
      const firstTask = buildTasks[0]
      setSelectedTaskId((current) => current ?? firstTask?.task_id ?? null)
      setBuildForm((current) => ({
        ...current,
        capability_name: current.capability_name || catalog.models[0]?.capability_name || '',
        model_version: current.model_version || catalog.models[0]?.model_version || '',
        issue_record_id: current.issue_record_id || String(catalog.license_issues[0]?.issue_record_id ?? ''),
      }))
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
    if (selectedTaskId == null) {
      setSelectedTaskDetail(null)
      return
    }
    void request<BuildTaskDetail>(`/api/v1/build-tasks/${selectedTaskId}`).then(setSelectedTaskDetail).catch(() => {
      setSelectedTaskDetail(null)
    })
  }, [selectedTaskId])

  const overviewCards = useMemo(
    () => [
      { title: '平台矩阵', value: dashboard.platforms.length, description: '统一管理 Linux / Windows / JNI 交付目标。' },
      { title: '模型目录', value: dashboard.catalog.models.length, description: '从 ai-train 同步可构建模型清单。' },
      { title: '授权记录', value: dashboard.catalog.license_issues.length, description: '从 ai-license-mgr 同步有效授权记录。' },
      { title: '构建任务', value: dashboard.buildTasks.length, description: '统一管理交付构建、归档与 delivery_package。' },
    ],
    [dashboard],
  )

  async function handleCreateBuildTask(): Promise<void> {
    const created = await request<BuildTaskDetail>('/api/v1/build-tasks', {
      method: 'POST',
      body: JSON.stringify({
        task_name: buildForm.task_name,
        capability_name: buildForm.capability_name,
        model_version: buildForm.model_version,
        issue_record_id: Number(buildForm.issue_record_id),
        requested_targets: buildForm.requested_targets
          .split(',')
          .map((item) => item.trim())
          .filter(Boolean),
        jni_enabled: buildForm.jni_enabled,
      }),
    })
    setSelectedTaskId(created.task_id)
    setActiveTab('detail')
    setActionMessage(`构建任务 #${created.task_id} 已创建`)
    await loadDashboard()
  }

  function fileUrl(path: string): string {
    return `${apiBaseUrl}${path}`
  }

  return (
    <div className="page">
      <header className="hero">
        <div className="hero-text">
          <p className="eyebrow">北京爱知之星科技股份有限公司（Agile Star）</p>
          <h1>ai-builder 专业交付构建台</h1>
          <p>围绕标准 delivery_package 组织能力目录、授权输入、构建任务、产物下载与交付摘要。</p>
        </div>
        <div className="hero-panel">
          <div><span className="label">服务端口</span><strong>26003</strong></div>
          <div><span className="label">标准目录</span><strong>delivery_package / libs / sdk_*</strong></div>
          <div><span className="label">当前阶段</span><strong>R7 专业化增强</strong></div>
        </div>
      </header>

      <main className="content">
        <section className="panel">
          <div className="section-header">
            <h2>跨模块联调导航</h2>
            <span className="badge badge-muted">R7 第二轮</span>
          </div>
          <div className="module-grid">
            {workspace.moduleLinks.map((item) => (
              <a
                key={item.id}
                className={`module-link-card${item.isCurrent ? ' active' : ''}`}
                href={item.url}
              >
                <div className="module-link-header">
                  <strong>{item.title}</strong>
                  <span className="module-tag">{item.isCurrent ? '当前模块' : '联调入口'}</span>
                </div>
                <p>{item.summary}</p>
              </a>
            ))}
          </div>
          <ul className="module-checklist">
            {workspace.reviewItems.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </section>
        <section className="panel">
          <div className="section-header">
            <h2>总体联调复审</h2>
            <span className="badge">R7 已完成</span>
          </div>
          <div className="review-grid">
            {workspace.reviewSummary.map((item) => (
              <article key={item.title} className="review-card">
                <div className="module-link-header">
                  <h3>{item.title}</h3>
                  <span className="review-status">{item.status}</span>
                </div>
                <p>{item.detail}</p>
              </article>
            ))}
          </div>
          <p className="module-note">
            当前模块定位：{workspace.currentModule.title} / {workspace.currentModule.summary}
          </p>
        </section>
        <section className="panel">
          <div className="section-header">
            <h2>构建工作台</h2>
            <div className="toolbar">
              <div className="tab-list">
                {tabs.map((tab) => (
                  <button
                    key={tab}
                    className={`tab-button${activeTab === tab ? ' active' : ''}`}
                    onClick={() => setActiveTab(tab)}
                  >
                    {tab === 'overview' ? '概览' : tab === 'build' ? '创建任务' : '任务详情'}
                  </button>
                ))}
              </div>
              <button className="action-button" onClick={() => void loadDashboard()}>刷新数据</button>
            </div>
          </div>
          {loading && <p className="info-text">正在加载 ai-builder 当前数据...</p>}
          {error && <p className="error-text">{error}</p>}
          {actionMessage && <p className="success-text">{actionMessage}</p>}
          <div className="card-grid">
            {overviewCards.map((card) => (
              <article key={card.title} className="card">
                <h3>{card.title}</h3>
                <strong>{card.value}</strong>
                <p>{card.description}</p>
              </article>
            ))}
          </div>
        </section>

        {activeTab === 'overview' && (
          <section className="panel split-layout">
            <article className="sub-panel">
              <h3>平台矩阵与目录同步</h3>
              <p className="meta-text">最近同步：{dashboard.catalog.synced_at ?? '未同步'}</p>
              <div className="table-wrap">
                <table>
                  <thead><tr><th>目标</th><th>工具链</th><th>JNI</th></tr></thead>
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
              </div>
            </article>
            <article className="sub-panel">
              <h3>授权与模型输入</h3>
              <div className="table-wrap">
                <table>
                  <thead><tr><th>能力</th><th>模型版本</th><th>授权记录</th></tr></thead>
                  <tbody>
                    {dashboard.catalog.models.map((item) => (
                      <tr key={`${item.capability_name}-${item.model_version}`}>
                        <td>{item.capability_name}</td>
                        <td>{item.model_version}</td>
                        <td>{dashboard.catalog.license_issues[0]?.issue_record_id ?? '-'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </article>
          </section>
        )}

        {activeTab === 'build' && (
          <section className="panel split-layout">
            <article className="sub-panel">
              <h3>创建构建任务</h3>
              <div className="form-grid">
                <label>任务名称<input value={buildForm.task_name} onChange={(event) => setBuildForm((current) => ({ ...current, task_name: event.target.value }))} /></label>
                <label>
                  能力
                  <select value={buildForm.capability_name} onChange={(event) => {
                    const capabilityName = event.target.value
                    const matchedModel = dashboard.catalog.models.find((item) => item.capability_name === capabilityName)
                    setBuildForm((current) => ({ ...current, capability_name: capabilityName, model_version: matchedModel?.model_version ?? current.model_version }))
                  }}>
                    <option value="">请选择能力</option>
                    {dashboard.catalog.capabilities.map((item) => <option key={item.capability_name} value={item.capability_name}>{item.display_name}</option>)}
                  </select>
                </label>
                <label>
                  模型版本
                  <select value={buildForm.model_version} onChange={(event) => setBuildForm((current) => ({ ...current, model_version: event.target.value }))}>
                    <option value="">请选择模型</option>
                    {dashboard.catalog.models
                      .filter((item) => !buildForm.capability_name || item.capability_name === buildForm.capability_name)
                      .map((item) => <option key={`${item.capability_name}-${item.model_version}`} value={item.model_version}>{item.capability_name} / {item.model_version}</option>)}
                  </select>
                </label>
                <label>
                  授权记录
                  <select value={buildForm.issue_record_id} onChange={(event) => setBuildForm((current) => ({ ...current, issue_record_id: event.target.value }))}>
                    <option value="">请选择授权</option>
                    {dashboard.catalog.license_issues.map((item) => <option key={item.issue_record_id} value={item.issue_record_id}>#{item.issue_record_id} / {item.customer_code}</option>)}
                  </select>
                </label>
                <label>目标平台<input value={buildForm.requested_targets} onChange={(event) => setBuildForm((current) => ({ ...current, requested_targets: event.target.value }))} placeholder="linux_x86_64,windows_x86_64" /></label>
                <label className="checkbox-row"><input type="checkbox" checked={buildForm.jni_enabled} onChange={(event) => setBuildForm((current) => ({ ...current, jni_enabled: event.target.checked }))} />启用 JNI</label>
              </div>
              <div className="button-row"><button className="action-button" onClick={() => void handleCreateBuildTask()}>创建任务</button></div>
            </article>

            <article className="sub-panel">
              <h3>最近构建任务</h3>
              <div className="list-stack">
                {dashboard.buildTasks.map((item) => (
                  <button
                    key={item.task_id}
                    className={`list-item-button${selectedTaskId === item.task_id ? ' active' : ''}`}
                    onClick={() => {
                      setSelectedTaskId(item.task_id)
                      setActiveTab('detail')
                    }}
                  >
                    <strong>{item.task_name}</strong>
                    <span>{item.capability_name} / {item.model_version}</span>
                    <span>{item.status}</span>
                  </button>
                ))}
              </div>
            </article>
          </section>
        )}

        {activeTab === 'detail' && (
          <section className="panel split-layout">
            <article className="sub-panel">
              <h3>任务列表</h3>
              <div className="list-stack">
                {dashboard.buildTasks.map((item) => (
                  <button
                    key={item.task_id}
                    className={`list-item-button${selectedTaskId === item.task_id ? ' active' : ''}`}
                    onClick={() => setSelectedTaskId(item.task_id)}
                  >
                    <strong>#{item.task_id} {item.task_name}</strong>
                    <span>{item.capability_name} / {item.model_version}</span>
                    <span>{item.status}</span>
                  </button>
                ))}
              </div>
              <h3 className="section-title">最近审计</h3>
              <ul>
                {dashboard.auditLogs.map((item) => (
                  <li key={`${item.entity_type}-${item.entity_id}-${item.happened_at_cst}`}>{item.happened_at_cst} / {item.action}</li>
                ))}
              </ul>
            </article>

            <article className="sub-panel">
              <h3>任务详情 / delivery_package</h3>
              {selectedTaskDetail == null ? (
                <p className="info-text">请选择构建任务。</p>
              ) : (
                <>
                  <div className="button-row">
                    {selectedTaskDetail.delivery_package_archive_path && (
                      <a className="action-link" href={fileUrl(`/api/v1/build-tasks/${selectedTaskDetail.task_id}/delivery-package/download`)}>
                        下载 delivery_package
                      </a>
                    )}
                  </div>
                  <pre className="json-block">
                    {JSON.stringify(
                      {
                        task_id: selectedTaskDetail.task_id,
                        status: selectedTaskDetail.status,
                        requested_targets: selectedTaskDetail.requested_targets,
                        build_root_path: selectedTaskDetail.build_root_path,
                        manifest_path: selectedTaskDetail.manifest_path,
                        delivery_package_dir: selectedTaskDetail.delivery_package_dir,
                      },
                      null,
                      2,
                    )}
                  </pre>
                  <h4>构建目标</h4>
                  <div className="table-wrap">
                    <table>
                      <thead><tr><th>目标</th><th>状态</th><th>下载</th></tr></thead>
                      <tbody>
                        {selectedTaskDetail.targets.map((item) => (
                          <tr key={item.target_id}>
                            <td>{item.target_name}</td>
                            <td>{item.status}</td>
                            <td><a className="action-link" href={fileUrl(`/api/v1/build-targets/${item.target_id}/download`)}>归档</a></td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                  <h4>交付摘要</h4>
                  <pre className="json-block">
                    {JSON.stringify(
                      {
                        manifest: selectedTaskDetail.manifest?.manifest ?? null,
                        dependency_summary: selectedTaskDetail.manifest?.dependency_summary ?? null,
                        artifacts: selectedTaskDetail.artifacts.map((item) => ({
                          artifact_type: item.artifact_type,
                          relative_path: item.relative_path,
                        })),
                      },
                      null,
                      2,
                    )}
                  </pre>
                </>
              )}
            </article>
          </section>
        )}
      </main>
    </div>
  )
}

export default App
