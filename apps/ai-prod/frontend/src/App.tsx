import { useEffect, useMemo, useState } from 'react'
import './App.css'
import '../../../frontend-common/src/r7Workspace.css'
import { buildR7Workspace } from '../../../frontend-common/src/r7Workspace.ts'

type CapabilityItem = {
  capability_name: string
  plugin_target: string
  model_version: string
  backend_type: string
  active_source: string
  device_mode: string
  pool_size: number
  revision_id: number | null
}

type LicenseStatus = {
  valid: boolean
  reason: string
  result: string
  code: string
  stage: string
  details: Record<string, unknown>
  diagnostics_version: string
  checked_at_cst: string
  customer_code: string | null
  capability_scope: string[]
  version_constraints: Record<string, unknown>
  hardware_fingerprint: string | null
  runtime_revision_id: number | null
}

type RuntimeRevisionItem = {
  revision_id: number
  revision_token: string
  action: string
  status: string
  license_valid: boolean
  capability_names: string[]
  source_summary: Record<string, unknown>
  detail: Record<string, unknown>
  rollback_of_revision_id: number | null
  created_at: string | null
}

type RuntimeOperationItem = {
  operation_id: number
  action: string
  status: string
  detail: Record<string, unknown>
  revision_id: number | null
  created_at: string | null
}

type InferResponse = {
  request_id: string
  capability_name: string
  model_version: string
  backend_type: string
  plugin_target: string
  device: string
  runtime_revision_id: number
  license_valid: boolean
  result: Record<string, unknown>
}

type AuditLogItem = {
  happened_at_cst: string
  action: string
  entity_type: string
  entity_id: string
  detail: Record<string, unknown>
}

type ListResponse<T> = { items: T[] }

type HealthResponse = {
  status: string
  runtime_revision_id: number | null
  capability_count: number
  license_valid: boolean
}

type RuntimeMetrics = {
  uptime_seconds: number
  active_request_count: number
  runtime_revision_id: number | null
  pool_summary: {
    capability_count: number
    total_pool_slots: number
    busy_pool_slots: number
    pending_request_count: number
    idle_pool_slots: number
    utilization_ratio: number
  }
  request_summary: {
    capability_total_requests: number
    capability_failed_requests: number
    queued_request_count: number
    avg_queue_wait_ms: number
    max_queue_wait_ms: number
    busy_reject_count: number
    queue_timeout_count: number
  }
  endpoint_metrics: Record<string, { total_requests: number; successful_requests: number; failed_requests: number; p95_latency_ms: number }>
}

type DashboardState = {
  health: HealthResponse | null
  capabilities: CapabilityItem[]
  licenseStatus: LicenseStatus | null
  runtimeMetrics: RuntimeMetrics | null
  revisions: RuntimeRevisionItem[]
  operations: RuntimeOperationItem[]
  auditLogs: AuditLogItem[]
}

const initialState: DashboardState = {
  health: null,
  capabilities: [],
  licenseStatus: null,
  runtimeMetrics: null,
  revisions: [],
  operations: [],
  auditLogs: [],
}

const tabs = ['overview', 'verify', 'control', 'diagnostics'] as const
type TabKey = (typeof tabs)[number]

const runtimeApiPrefix = '/api/v1'
const internalApiPrefix = '/internal'
const runtimeApiBaseUrl = import.meta.env.VITE_RUNTIME_API_BASE_URL ?? ''
const internalApiBaseUrl = import.meta.env.VITE_INTERNAL_API_BASE_URL ?? ''
const workspace = buildR7Workspace(import.meta.env, 'ai-prod')

async function fetchJson<T>(baseUrl: string, path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${baseUrl}${path}`, {
    headers: {
      'Content-Type': 'application/json',
      ...(options?.headers ?? {}),
    },
    ...options,
  })
  if (!response.ok) {
    const message = await response.text()
    throw new Error(message || `请求失败：${path}`)
  }
  return (await response.json()) as T
}

function statusTone(status: string): 'good' | 'warn' | 'danger' | 'neutral' {
  if (['ok', 'completed', 'active', 'ready', 'success'].includes(status)) return 'good'
  if (['failed', 'error', 'denied', 'offline'].includes(status)) return 'danger'
  if (['running', 'pending', 'created'].includes(status)) return 'warn'
  return 'neutral'
}

function App() {
  const [dashboard, setDashboard] = useState<DashboardState>(initialState)
  const [activeTab, setActiveTab] = useState<TabKey>('overview')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [selectedCapability, setSelectedCapability] = useState('')
  const [selectedRevisionId, setSelectedRevisionId] = useState<number | null>(null)
  const [preferDevice, setPreferDevice] = useState<'auto' | 'gpu' | 'cpu'>('auto')
  const [payload, setPayload] = useState('{"image":"demo"}')
  const [inputType, setInputType] = useState<'json' | 'image' | 'video' | 'pdf'>('json')
  const [inferResult, setInferResult] = useState<InferResponse | null>(null)
  const [actionMessage, setActionMessage] = useState<string | null>(null)

  async function loadDashboard(): Promise<void> {
    try {
      setLoading(true)
      setError(null)
      const [health, capabilities, licenseStatus, runtimeMetrics, revisions, operations, auditLogs] = await Promise.all([
        fetchJson<HealthResponse>(runtimeApiBaseUrl, `${runtimeApiPrefix}/health`),
        fetchJson<ListResponse<CapabilityItem>>(runtimeApiBaseUrl, `${runtimeApiPrefix}/capabilities`),
        fetchJson<LicenseStatus>(runtimeApiBaseUrl, `${runtimeApiPrefix}/license/status`),
        fetchJson<RuntimeMetrics>(runtimeApiBaseUrl, `${runtimeApiPrefix}/admin/metrics`),
        fetchJson<ListResponse<RuntimeRevisionItem>>(internalApiBaseUrl, `${internalApiPrefix}/admin/revisions`),
        fetchJson<ListResponse<RuntimeOperationItem>>(internalApiBaseUrl, `${internalApiPrefix}/admin/operations`),
        fetchJson<ListResponse<AuditLogItem>>(internalApiBaseUrl, `${internalApiPrefix}/audit-logs?limit=8`),
      ])
      setDashboard({
        health,
        capabilities: capabilities.items,
        licenseStatus,
        runtimeMetrics,
        revisions: revisions.items,
        operations: operations.items,
        auditLogs: auditLogs.items,
      })
      setSelectedCapability((current) => current || capabilities.items[0]?.capability_name || '')
      setSelectedRevisionId((current) => current ?? revisions.items[0]?.revision_id ?? null)
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : '加载失败')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    void loadDashboard()
  }, [])

  const selectedCapabilityDetail = dashboard.capabilities.find((item) => item.capability_name === selectedCapability) ?? null
  const selectedRevision = dashboard.revisions.find((item) => item.revision_id === selectedRevisionId) ?? null

  const overviewCards = useMemo(
    () => [
      { title: '能力数量', value: dashboard.health?.capability_count ?? 0, description: '当前运行态可提供服务的能力数量。' },
      { title: '活动 revision', value: dashboard.health?.runtime_revision_id ?? 0, description: '当前线上启用的运行版本。' },
      { title: '累计请求', value: dashboard.runtimeMetrics?.request_summary.capability_total_requests ?? 0, description: '聚合能力请求总量。' },
      { title: '队列中请求', value: dashboard.runtimeMetrics?.request_summary.queued_request_count ?? 0, description: '当前排队中的运行请求。' },
    ],
    [dashboard],
  )

  async function handleInfer(): Promise<void> {
    if (!selectedCapability) {
      setActionMessage('请先选择能力。')
      return
    }
    try {
      setActionMessage('正在执行在线验证...')
      const result = await fetchJson<InferResponse>(runtimeApiBaseUrl, `${runtimeApiPrefix}/infer/${selectedCapability}`, {
        method: 'POST',
        body: JSON.stringify({
          input_type: inputType,
          payload,
          prefer_device: preferDevice,
          options: {},
        }),
      })
      setInferResult(result)
      setActionMessage(`推理完成，请求 ID：${result.request_id}`)
      await loadDashboard()
    } catch (loadError) {
      setActionMessage(loadError instanceof Error ? loadError.message : '推理失败')
    }
  }

  async function handleRuntimeAction(action: 'reload' | 'rollback', targetRevisionId?: number): Promise<void> {
    try {
      setActionMessage(`正在执行 ${action}...`)
      await fetchJson(runtimeApiBaseUrl, `${runtimeApiPrefix}/admin/reload`, {
        method: 'POST',
        body: JSON.stringify({
          action,
          target_revision_id: targetRevisionId,
        }),
      })
      setActionMessage(`${action} 已完成`)
      await loadDashboard()
    } catch (loadError) {
      setActionMessage(loadError instanceof Error ? loadError.message : `${action} 失败`)
    }
  }

  return (
    <div className="page">
      <div className="workspace-topbar">
        <div className="workspace-brand">
          <strong>Agile Star AI Capability Platform</strong>
          <span>统一运行控制台 / 当前模块：{workspace.currentModule.title}</span>
        </div>
        <nav className="workspace-nav">
          {workspace.moduleLinks.map((item) => (
            <a key={item.id} className={`workspace-nav-link${item.isCurrent ? ' active' : ''}`} href={item.url}>
              <strong>{item.shortTitle}</strong>
              <span>{item.stageLabel}</span>
            </a>
          ))}
        </nav>
      </div>

      <div className="workflow-strip">
        {workspace.workflowSteps.map((item) => (
          <a key={item.moduleId} className={`workflow-step${item.isCurrent ? ' active' : ''}`} href={item.url}>
            <span>步骤 {item.order}</span>
            <strong>{item.label}</strong>
            <span>{item.summary}</span>
          </a>
        ))}
      </div>

      <header className="hero">
        <div className="hero-text">
          <p className="eyebrow">北京爱知之星科技股份有限公司（Agile Star）</p>
          <h1>ai-prod 内部运行控制台</h1>
          <p>
            明确以研发、QA、交付与运维为对象，围绕“状态总览 → 在线验证 → 受控变更 → 诊断定位”
            组织内部运行页面，不再把 ai-prod 当作客户业务前台。
          </p>
        </div>
        <div className="hero-panel">
          <div><span className="label">服务端口</span><strong>26004</strong></div>
          <div><span className="label">主链路</span><strong>C++ HTTP + Runtime</strong></div>
          <div><span className="label">授权结果码</span><strong>{dashboard.licenseStatus?.code ?? '未加载'}</strong></div>
        </div>
      </header>

      <main className="content">
        <section className="panel">
          <div className="section-header">
            <div>
              <h2>首页概览</h2>
              <p>优先展示 revision、license、排队风险与异常能力，而不是纯信息堆叠。</p>
            </div>
            <span className="badge">P41-P44</span>
          </div>
          {loading && <p className="info-text">正在加载运行控制台...</p>}
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
              <h3>当前风险</h3>
              <ul>
                <li>License：{dashboard.licenseStatus?.valid ? '有效' : `受限 / ${dashboard.licenseStatus?.code ?? 'unknown'}`}</li>
                <li>队列超时：{dashboard.runtimeMetrics?.request_summary.queue_timeout_count ?? 0}</li>
                <li>繁忙拒绝：{dashboard.runtimeMetrics?.request_summary.busy_reject_count ?? 0}</li>
              </ul>
            </article>
            <article className="workspace-summary-card">
              <h3>最近变更</h3>
              <div className="workspace-list">
                {dashboard.operations.slice(0, 4).map((item) => (
                  <button
                    key={item.operation_id}
                    className={`workspace-list-item${selectedRevisionId === item.revision_id ? ' active' : ''}`}
                    onClick={() => setSelectedRevisionId(item.revision_id)}
                    type="button"
                  >
                    <strong>{item.action} / #{item.operation_id}</strong>
                    <div className="workspace-meta-row">
                      <span>{item.created_at ?? '-'}</span>
                      <span className={`status-pill ${statusTone(item.status)}`}>{item.status}</span>
                    </div>
                  </button>
                ))}
              </div>
            </article>
          </div>
        </section>

        <section className="panel">
          <div className="toolbar">
            <div>
              <h2>运行工作台</h2>
              <p>围绕在线验证、变更控制与诊断视图组织内部运行作业。</p>
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
                  {tab === 'verify' && '在线验证'}
                  {tab === 'control' && '版本控制'}
                  {tab === 'diagnostics' && '监控诊断'}
                </button>
              ))}
            </div>
          </div>

          {activeTab === 'overview' && (
            <div className="workspace-panel-grid">
              <div className="workspace-stack">
                <article className="workspace-note-block">
                  <h3>能力目录</h3>
                  <div className="workspace-table-wrap">
                    <table className="workspace-table">
                      <thead>
                        <tr>
                          <th>能力</th>
                          <th>版本</th>
                          <th>设备</th>
                          <th>revision</th>
                        </tr>
                      </thead>
                      <tbody>
                        {dashboard.capabilities.map((item) => (
                          <tr key={item.capability_name}>
                            <td>{item.capability_name}</td>
                            <td>{item.model_version}</td>
                            <td>{item.device_mode}</td>
                            <td>{item.revision_id ?? '-'}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </article>
              </div>
              <div className="workspace-stack">
                <article className="workspace-note-block">
                  <h3>License 状态</h3>
                  <div className="workspace-kpi-grid">
                    <article className="workspace-kpi-card">
                      <span>结果</span>
                      <strong>{dashboard.licenseStatus?.result ?? '-'}</strong>
                    </article>
                    <article className="workspace-kpi-card">
                      <span>结果码</span>
                      <strong>{dashboard.licenseStatus?.code ?? '-'}</strong>
                    </article>
                    <article className="workspace-kpi-card">
                      <span>阶段</span>
                      <strong>{dashboard.licenseStatus?.stage ?? '-'}</strong>
                    </article>
                  </div>
                </article>
              </div>
            </div>
          )}

          {activeTab === 'verify' && (
            <div className="workspace-panel-grid">
              <div className="workspace-stack">
                <article className="workspace-note-block">
                  <div className="section-header">
                    <h3>在线验证</h3>
                    <span className="badge badge-muted">P42</span>
                  </div>
                  <div className="workspace-form-grid">
                    <label className="workspace-field">
                      能力
                      <select value={selectedCapability} onChange={(event) => setSelectedCapability(event.target.value)}>
                        {dashboard.capabilities.map((item) => (
                          <option key={item.capability_name} value={item.capability_name}>
                            {item.capability_name}
                          </option>
                        ))}
                      </select>
                    </label>
                    <label className="workspace-field">
                      输入类型
                      <select value={inputType} onChange={(event) => setInputType(event.target.value as typeof inputType)}>
                        <option value="json">json</option>
                        <option value="image">image</option>
                        <option value="video">video</option>
                        <option value="pdf">pdf</option>
                      </select>
                    </label>
                    <label className="workspace-field">
                      设备偏好
                      <select value={preferDevice} onChange={(event) => setPreferDevice(event.target.value as typeof preferDevice)}>
                        <option value="auto">auto</option>
                        <option value="gpu">gpu</option>
                        <option value="cpu">cpu</option>
                      </select>
                    </label>
                    <label className="workspace-field full-span">
                      推理载荷
                      <textarea rows={6} value={payload} onChange={(event) => setPayload(event.target.value)} />
                    </label>
                  </div>
                  <div className="button-row">
                    <button onClick={() => void handleInfer()} type="button">执行在线验证</button>
                  </div>
                </article>
              </div>
              <div className="workspace-stack">
                <article className="workspace-note-block">
                  <h3>验证结果</h3>
                  {selectedCapabilityDetail && (
                    <div className="workspace-kpi-grid">
                      <article className="workspace-kpi-card">
                        <span>能力</span>
                        <strong>{selectedCapabilityDetail.capability_name}</strong>
                      </article>
                      <article className="workspace-kpi-card">
                        <span>当前 revision</span>
                        <strong>{selectedCapabilityDetail.revision_id ?? '-'}</strong>
                      </article>
                    </div>
                  )}
                  <pre className="workspace-code-block">{JSON.stringify(inferResult ?? {}, null, 2)}</pre>
                </article>
              </div>
            </div>
          )}

          {activeTab === 'control' && (
            <div className="workspace-panel-grid">
              <div className="workspace-stack">
                <article className="workspace-note-block">
                  <div className="section-header">
                    <h3>revision 列表</h3>
                    <span className="badge badge-muted">P43</span>
                  </div>
                  <div className="workspace-list">
                    {dashboard.revisions.map((item) => (
                      <button
                        key={item.revision_id}
                        className={`workspace-list-item${selectedRevisionId === item.revision_id ? ' active' : ''}`}
                        onClick={() => setSelectedRevisionId(item.revision_id)}
                        type="button"
                      >
                        <strong>revision #{item.revision_id}</strong>
                        <div className="workspace-meta-row">
                          <span>{item.action}</span>
                          <span>{item.capability_names.join(', ') || '无能力'}</span>
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
                    <h3>受控变更</h3>
                    {selectedRevision && <span className={`status-pill ${statusTone(selectedRevision.status)}`}>{selectedRevision.status}</span>}
                  </div>
                  {!selectedRevision ? (
                    <div className="workspace-empty">请选择 revision 查看影响范围。</div>
                  ) : (
                    <>
                      <div className="workspace-kpi-grid">
                        <article className="workspace-kpi-card">
                          <span>能力数</span>
                          <strong>{selectedRevision.capability_names.length}</strong>
                        </article>
                        <article className="workspace-kpi-card">
                          <span>license</span>
                          <strong>{selectedRevision.license_valid ? '有效' : '受限'}</strong>
                        </article>
                      </div>
                      <div className="workspace-action-row">
                        <button className="action-button" onClick={() => void handleRuntimeAction('reload')} type="button">执行 reload</button>
                        <button className="action-button" onClick={() => void handleRuntimeAction('rollback', selectedRevision.revision_id)} type="button">回滚到该 revision</button>
                      </div>
                      <pre className="workspace-code-block">{JSON.stringify(selectedRevision.detail, null, 2)}</pre>
                    </>
                  )}
                </article>
              </div>
            </div>
          )}

          {activeTab === 'diagnostics' && (
            <div className="workspace-panel-grid">
              <div className="workspace-stack">
                <article className="workspace-note-block">
                  <div className="section-header">
                    <h3>监控与诊断</h3>
                    <span className="badge badge-muted">P44</span>
                  </div>
                  <div className="workspace-kpi-grid">
                    <article className="workspace-kpi-card">
                      <span>池利用率</span>
                      <strong>{Math.round((dashboard.runtimeMetrics?.pool_summary.utilization_ratio ?? 0) * 100)}%</strong>
                    </article>
                    <article className="workspace-kpi-card">
                      <span>平均排队</span>
                      <strong>{dashboard.runtimeMetrics?.request_summary.avg_queue_wait_ms ?? 0} ms</strong>
                    </article>
                    <article className="workspace-kpi-card">
                      <span>P95 最大值</span>
                      <strong>{Math.max(...Object.values(dashboard.runtimeMetrics?.endpoint_metrics ?? {}).map((item) => item.p95_latency_ms), 0)} ms</strong>
                    </article>
                  </div>
                  <pre className="workspace-code-block">{JSON.stringify(dashboard.runtimeMetrics ?? {}, null, 2)}</pre>
                </article>
              </div>
              <div className="workspace-stack">
                <article className="workspace-note-block">
                  <h3>revision 诊断与审计</h3>
                  {selectedRevision && <pre className="workspace-code-block">{JSON.stringify(selectedRevision.source_summary, null, 2)}</pre>}
                  <div className="workspace-table-wrap" style={{ marginTop: 16 }}>
                    <table className="workspace-table">
                      <thead>
                        <tr>
                          <th>时间</th>
                          <th>动作</th>
                          <th>实体</th>
                        </tr>
                      </thead>
                      <tbody>
                        {dashboard.auditLogs.map((item) => (
                          <tr key={`${item.happened_at_cst}-${item.entity_id}`}>
                            <td>{item.happened_at_cst}</td>
                            <td>{item.action}</td>
                            <td>{item.entity_type} / {item.entity_id}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </article>
              </div>
            </div>
          )}
        </section>
      </main>
    </div>
  )
}

export default App
