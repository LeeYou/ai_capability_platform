import { useEffect, useMemo, useState } from 'react'
import './App.css'
import '../../../frontend-common/src/r7Workspace.css'
import { WorkspaceShell } from '../../../frontend-common/src/workspaceShell.tsx'
import { buildR7Workspace } from '../../../frontend-common/src/r7Workspace.ts'
import { fetchListItems, requestJson } from '../../../frontend-common/src/http.ts'

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
  artifact_id: number | null
  capability_name: string
  model_version: string
  artifact_path: string
  manifest_path: string
  backend_type: string
  checksum: string
  status: string
}

type LicenseIssueItem = {
  issue_record_id: number
  customer_code: string
  key_name: string
  status: string
  capability_scope: string[]
  license_path: string
  issued_at_cst: string
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
  started_at?: string | null
  completed_at?: string | null
}

type BuildTargetItem = {
  target_id: number
  task_id: number
  target_name: string
  os_name: string
  arch_name: string
  artifact_format: string
  build_mode: string
  toolchain_name: string
  jni_enabled: boolean
  status: string
  output_dir: string
  binary_path: string
  header_dir: string
  manifest_path: string
  checksum: string
  log_path: string
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
const tabs = ['overview', 'wizard', 'tasks', 'package'] as const
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
  return requestJson<T>(apiBaseUrl, path, init)
}

async function fetchList<T>(path: string): Promise<T[]> {
  return fetchListItems<T>(apiBaseUrl, path)
}

function statusTone(status: string): 'good' | 'warn' | 'danger' | 'neutral' {
  if (['completed', 'ready', 'success', 'ok'].includes(status)) return 'good'
  if (['failed', 'error'].includes(status)) return 'danger'
  if (['running', 'pending', 'queued', 'created'].includes(status)) return 'warn'
  return 'neutral'
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
      setSelectedTaskId((current) => current ?? buildTasks[0]?.task_id ?? null)
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
      { title: '平台矩阵', value: dashboard.platforms.length, description: '统一管理 Linux / Windows / JNI / 多架构交付目标。' },
      { title: '可构建模型', value: dashboard.catalog.models.length, description: '从 ai-train 同步真实模型与 manifest。' },
      { title: '可用授权', value: dashboard.catalog.license_issues.length, description: '与 ai-license-mgr 对齐后的签发记录。' },
      { title: '构建队列', value: dashboard.buildTasks.length, description: '当前 delivery_package / SDK / 动态库构建任务总数。' },
    ],
    [dashboard],
  )

  const failedTasks = useMemo(
    () => dashboard.buildTasks.filter((item) => item.status === 'failed').slice(0, 4),
    [dashboard.buildTasks],
  )

  const readyModels = useMemo(
    () => dashboard.catalog.models.slice(0, 4),
    [dashboard.catalog.models],
  )

  async function handleCreateBuildTask(): Promise<void> {
    try {
      setActionMessage('正在创建构建任务...')
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
      setActiveTab('tasks')
      setActionMessage(`构建任务 #${created.task_id} 已创建`)
      await loadDashboard()
    } catch (loadError) {
      setActionMessage(loadError instanceof Error ? loadError.message : '创建构建任务失败')
    }
  }

  function taskDeliveryDownloadUrl(taskId: number): string {
    return `${apiBaseUrl}/api/v1/build-tasks/${taskId}/delivery-package/download`
  }

  function targetDownloadUrl(targetId: number): string {
    return `${apiBaseUrl}/api/v1/build-targets/${targetId}/download`
  }

  return (
    <WorkspaceShell moduleId="ai-builder" title="ai-builder" subtitle="统一交付工作台">
      <header className="hero">
        <div className="hero-text">
          <p className="eyebrow">北京爱知之星科技股份有限公司（Agile Star）</p>
          <h1>ai-builder 交付构建工作台</h1>
          <p>
            围绕“选择模型 → 绑定授权 → 选择平台 → 构建 delivery_package → 校验产物 → 推进生产验收”
            六个步骤组织交付工程作业，减少手工拼接目录与定位日志的成本。
          </p>
          <div className="workspace-action-row">
            {workspace.nextModule && (
              <a className="workspace-action-chip" href={workspace.nextModule.url}>
                去 {workspace.nextModule.shortTitle}
              </a>
            )}
          </div>
        </div>
        <div className="hero-panel">
          <div><span className="label">服务端口</span><strong>26003</strong></div>
          <div><span className="label">构建目标</span><strong>动态库 / SDK / delivery_package</strong></div>
          <div><span className="label">目录同步</span><strong>{dashboard.catalog.synced_at ?? '待同步'}</strong></div>
        </div>
      </header>

      <main className="content">
        <section className="panel">
          <div className="section-header">
            <div>
              <h2>首页概览</h2>
              <p>优先把模型、授权、平台矩阵与失败任务放到同一视图下统一决策。</p>
            </div>
            <span className="badge">B15-B18</span>
          </div>
          {loading && <p className="info-text">正在加载交付构建数据...</p>}
          {error && <p className="error-text">数据加载失败：{error}</p>}
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
          <div className="workspace-summary-grid">
            <article className="workspace-summary-card">
              <h3>优先构建模型</h3>
              {readyModels.length === 0 ? (
                <div className="workspace-empty">当前没有可构建模型，请先在 ai-train / ai-test 完成上游动作。</div>
              ) : (
                <div className="workspace-list">
                  {readyModels.map((item) => (
                    <button
                      key={`${item.capability_name}-${item.model_version}`}
                      className="workspace-list-item"
                      onClick={() => {
                        setBuildForm((current) => ({
                          ...current,
                          capability_name: item.capability_name,
                          model_version: item.model_version,
                          task_name: current.task_name || `${item.capability_name}-${item.model_version}-delivery`,
                        }))
                        setActiveTab('wizard')
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
              <h3>失败任务回看</h3>
              {failedTasks.length === 0 ? (
                <div className="workspace-empty">当前暂无失败构建任务。</div>
              ) : (
                <div className="workspace-list">
                  {failedTasks.map((item) => (
                    <button
                      key={item.task_id}
                      className={`workspace-list-item${selectedTaskId === item.task_id ? ' active' : ''}`}
                      onClick={() => {
                        setSelectedTaskId(item.task_id)
                        setActiveTab('tasks')
                      }}
                      type="button"
                    >
                      <strong>任务 #{item.task_id}</strong>
                      <div className="workspace-meta-row">
                        <span>{item.capability_name}</span>
                        <span>{item.model_version}</span>
                        <span className={`status-pill ${statusTone(item.status)}`}>{item.status}</span>
                      </div>
                    </button>
                  ))}
                </div>
              )}
            </article>
            <article className="workspace-summary-card">
              <h3>当前设计原则</h3>
              <ul>
                <li>构建任务创建要向导化，不再要求工程师手工理解所有平台参数。</li>
                <li>产物详情必须展示 provenance、校验结果与下载动作。</li>
                <li>构建完成后明确下一步动作：去 ai-prod 做生产验收。</li>
              </ul>
            </article>
          </div>
        </section>

        <section className="panel">
          <div className="toolbar">
            <div>
              <h2>交付工作台</h2>
              <p>从构建向导到 delivery_package 目录树再到验收联动的完整闭环。</p>
            </div>
            <div className="tab-list">
              {tabs.map((tab) => (
                <button
                  key={tab}
                  className={`tab-button${activeTab === tab ? ' active' : ''}`}
                  onClick={() => setActiveTab(tab)}
                  type="button"
                >
                  {tab === 'overview' && '总览'}
                  {tab === 'wizard' && '构建向导'}
                  {tab === 'tasks' && '任务工作台'}
                  {tab === 'package' && '交付包视图'}
                </button>
              ))}
            </div>
          </div>

          {activeTab === 'overview' && (
            <div className="workspace-panel-grid">
              <div className="workspace-stack">
                <article className="workspace-note-block">
                  <h3>平台矩阵</h3>
                  <div className="workspace-table-wrap">
                    <table className="workspace-table">
                      <thead>
                        <tr>
                          <th>目标</th>
                          <th>平台</th>
                          <th>格式</th>
                          <th>工具链</th>
                        </tr>
                      </thead>
                      <tbody>
                        {dashboard.platforms.map((item) => (
                          <tr key={item.target_name}>
                            <td>{item.target_name}</td>
                            <td>{item.os_name}/{item.arch_name}</td>
                            <td>{item.artifact_format}</td>
                            <td>{item.toolchain_name}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </article>
              </div>
              <div className="workspace-stack">
                <article className="workspace-note-block">
                  <h3>最近构建队列</h3>
                  <div className="workspace-list">
                    {dashboard.buildTasks.slice(0, 5).map((item) => (
                      <button
                        key={item.task_id}
                        className={`workspace-list-item${selectedTaskId === item.task_id ? ' active' : ''}`}
                        onClick={() => {
                          setSelectedTaskId(item.task_id)
                          setActiveTab('tasks')
                        }}
                        type="button"
                      >
                        <strong>任务 #{item.task_id}</strong>
                        <div className="workspace-meta-row">
                          <span>{item.capability_name}</span>
                          <span>{item.model_version}</span>
                          <span className={`status-pill ${statusTone(item.status)}`}>{item.status}</span>
                        </div>
                      </button>
                    ))}
                  </div>
                </article>
              </div>
            </div>
          )}

          {activeTab === 'wizard' && (
            <div className="workspace-panel-grid">
              <div className="workspace-stack">
                <article className="workspace-note-block">
                  <div className="section-header">
                    <h3>构建向导</h3>
                    <span className="badge badge-muted">B15</span>
                  </div>
                  <div className="workspace-form-grid">
                    <label className="workspace-field">
                      任务名称
                      <input value={buildForm.task_name} onChange={(event) => setBuildForm((current) => ({ ...current, task_name: event.target.value }))} />
                    </label>
                    <label className="workspace-field">
                      模型能力
                      <select value={buildForm.capability_name} onChange={(event) => setBuildForm((current) => ({ ...current, capability_name: event.target.value }))}>
                        {dashboard.catalog.models.map((item) => (
                          <option key={`${item.capability_name}-${item.model_version}`} value={item.capability_name}>
                            {item.capability_name}
                          </option>
                        ))}
                      </select>
                    </label>
                    <label className="workspace-field">
                      模型版本
                      <select value={buildForm.model_version} onChange={(event) => setBuildForm((current) => ({ ...current, model_version: event.target.value }))}>
                        {dashboard.catalog.models
                          .filter((item) => item.capability_name === buildForm.capability_name)
                          .map((item) => (
                            <option key={item.model_version} value={item.model_version}>
                              {item.model_version}
                            </option>
                          ))}
                      </select>
                    </label>
                    <label className="workspace-field">
                      授权记录
                      <select value={buildForm.issue_record_id} onChange={(event) => setBuildForm((current) => ({ ...current, issue_record_id: event.target.value }))}>
                        {dashboard.catalog.license_issues.map((item) => (
                          <option key={item.issue_record_id} value={String(item.issue_record_id)}>
                            #{item.issue_record_id} / {item.customer_code}
                          </option>
                        ))}
                      </select>
                    </label>
                    <label className="workspace-field full-span">
                      平台目标（逗号分隔）
                      <input value={buildForm.requested_targets} onChange={(event) => setBuildForm((current) => ({ ...current, requested_targets: event.target.value }))} placeholder="linux_x86_64, windows_x86_64" />
                    </label>
                    <label className="workspace-field">
                      JNI 交付
                      <select
                        value={buildForm.jni_enabled ? 'true' : 'false'}
                        onChange={(event) => setBuildForm((current) => ({ ...current, jni_enabled: event.target.value === 'true' }))}
                      >
                        <option value="false">关闭</option>
                        <option value="true">开启</option>
                      </select>
                    </label>
                  </div>
                  <div className="button-row">
                    <button onClick={() => void handleCreateBuildTask()} type="button">创建构建任务</button>
                  </div>
                </article>
              </div>
              <div className="workspace-stack">
                <article className="workspace-note-block">
                  <h3>交付预览</h3>
                  <div className="workspace-kpi-grid">
                    <article className="workspace-kpi-card">
                      <span>模型</span>
                      <strong>{buildForm.capability_name || '-'}</strong>
                    </article>
                    <article className="workspace-kpi-card">
                      <span>版本</span>
                      <strong>{buildForm.model_version || '-'}</strong>
                    </article>
                    <article className="workspace-kpi-card">
                      <span>授权</span>
                      <strong>{buildForm.issue_record_id || '-'}</strong>
                    </article>
                  </div>
                  <ul>
                    <li>输出动态库、头文件、示例工程与标准 delivery_package。</li>
                    <li>任务级 manifest 将记录 provenance、依赖摘要与校验链路。</li>
                    <li>构建完成后直接进入 ai-prod 运行验收。</li>
                  </ul>
                </article>
              </div>
            </div>
          )}

          {activeTab === 'tasks' && (
            <div className="workspace-panel-grid">
              <div className="workspace-stack">
                <article className="workspace-note-block">
                  <div className="section-header">
                    <h3>构建任务队列</h3>
                    <span className="badge badge-muted">B16</span>
                  </div>
                  <div className="workspace-list">
                    {dashboard.buildTasks.map((item) => (
                      <button
                        key={item.task_id}
                        className={`workspace-list-item${selectedTaskId === item.task_id ? ' active' : ''}`}
                        onClick={() => setSelectedTaskId(item.task_id)}
                        type="button"
                      >
                        <strong>任务 #{item.task_id} / {item.task_name}</strong>
                        <div className="workspace-meta-row">
                          <span>{item.capability_name}</span>
                          <span>{item.model_version}</span>
                          <span>{item.requested_targets.join(', ') || '未指定'}</span>
                          <span className={`status-pill ${statusTone(item.status)}`}>{item.status}</span>
                        </div>
                      </button>
                    ))}
                  </div>
                </article>
              </div>
              <div className="workspace-stack">
                <article className="workspace-note-block">
                  <div className="section-header">
                    <h3>阶段状态与实时日志</h3>
                    {selectedTaskDetail && <span className={`status-pill ${statusTone(selectedTaskDetail.status)}`}>{selectedTaskDetail.status}</span>}
                  </div>
                  {!selectedTaskDetail ? (
                    <div className="workspace-empty">请选择构建任务查看详细内容。</div>
                  ) : (
                    <>
                      <div className="workspace-kpi-grid">
                        <article className="workspace-kpi-card">
                          <span>目标数</span>
                          <strong>{selectedTaskDetail.targets.length}</strong>
                        </article>
                        <article className="workspace-kpi-card">
                          <span>产物数</span>
                          <strong>{selectedTaskDetail.artifacts.length}</strong>
                        </article>
                        <article className="workspace-kpi-card">
                          <span>JNI</span>
                          <strong>{selectedTaskDetail.jni_enabled ? '开启' : '关闭'}</strong>
                        </article>
                      </div>
                      <pre className="workspace-code-block">{selectedTaskDetail.log_path}</pre>
                      <div className="workspace-table-wrap">
                        <table className="workspace-table">
                          <thead>
                            <tr>
                              <th>目标</th>
                              <th>状态</th>
                              <th>输出</th>
                              <th>操作</th>
                            </tr>
                          </thead>
                          <tbody>
                            {selectedTaskDetail.targets.map((item) => (
                              <tr key={item.target_id}>
                                <td>{item.target_name}</td>
                                <td><span className={`status-pill ${statusTone(item.status)}`}>{item.status}</span></td>
                                <td>{item.binary_path}</td>
                                <td><a href={targetDownloadUrl(item.target_id)}>下载归档</a></td>
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

          {activeTab === 'package' && (
            <div className="workspace-panel-grid">
              <div className="workspace-stack">
                <article className="workspace-note-block">
                  <div className="section-header">
                    <h3>delivery_package 目录树</h3>
                    <span className="badge badge-muted">B17-B18</span>
                  </div>
                  {!selectedTaskDetail ? (
                    <div className="workspace-empty">请选择构建任务查看交付包。</div>
                  ) : (
                    <>
                      <div className="workspace-action-row">
                        {selectedTaskDetail.delivery_package_archive_path && (
                          <a className="workspace-action-chip" href={taskDeliveryDownloadUrl(selectedTaskDetail.task_id)}>
                            下载 delivery_package
                          </a>
                        )}
                        {workspace.nextModule && (
                          <a className="workspace-action-chip" href={workspace.nextModule.url}>
                            去 {workspace.nextModule.shortTitle}
                          </a>
                        )}
                      </div>
                      <div className="workspace-table-wrap">
                        <table className="workspace-table">
                          <thead>
                            <tr>
                              <th>类型</th>
                              <th>相对路径</th>
                              <th>校验</th>
                            </tr>
                          </thead>
                          <tbody>
                            {selectedTaskDetail.artifacts.map((item) => (
                              <tr key={item.artifact_id}>
                                <td>{item.artifact_type}</td>
                                <td>{item.relative_path}</td>
                                <td>{item.checksum.slice(0, 12)}...</td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    </>
                  )}
                </article>
              </div>
              <div className="workspace-stack">
                <article className="workspace-note-block">
                  <h3>manifest / provenance / 校验结果</h3>
                  {!selectedTaskDetail?.manifest ? (
                    <div className="workspace-empty">当前任务暂无 manifest 信息。</div>
                  ) : (
                    <pre className="workspace-code-block">{JSON.stringify(selectedTaskDetail.manifest.manifest, null, 2)}</pre>
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
