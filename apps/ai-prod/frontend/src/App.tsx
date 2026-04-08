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
  max_batch_size: number
  queue_wait_timeout_ms: number
  max_pending_request_count: number
  revision_id: number | null
}

type LicenseStatus = {
  valid: boolean
  reason: string
  checked_at_cst: string
  customer_code: string | null
  capability_scope: string[]
  version_constraints: Record<string, string>
  runtime_revision_id: number | null
}

type RuntimeRevisionItem = {
  revision_id: number
  revision_token: string
  action: string
  status: string
  license_valid: boolean
  capability_names: string[]
  rollback_of_revision_id: number | null
}

type RuntimeOperationItem = {
  operation_id: number
  action: string
  status: string
  revision_id: number | null
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
  result: {
    summary: string
    digest: string
    score: number
    input_type: string
    payload_size: number
    instance_id: string
    queue_wait_ms: number
    queue_wait_timeout_ms: number
    max_pending_request_count: number
    fallback_applied: boolean
  }
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
}

const initialState: DashboardState = {
  health: null,
  capabilities: [],
  licenseStatus: null,
  runtimeMetrics: null,
  revisions: [],
  operations: [],
}

const tabs = ['overview', 'catalog', 'control', 'revision'] as const
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
      const [health, capabilities, licenseStatus, runtimeMetrics, revisions, operations] = await Promise.all([
        fetchJson<HealthResponse>(runtimeApiBaseUrl, `${runtimeApiPrefix}/health`),
        fetchJson<ListResponse<CapabilityItem>>(runtimeApiBaseUrl, `${runtimeApiPrefix}/capabilities`),
        fetchJson<LicenseStatus>(runtimeApiBaseUrl, `${runtimeApiPrefix}/license/status`),
        fetchJson<RuntimeMetrics>(runtimeApiBaseUrl, `${runtimeApiPrefix}/admin/metrics`),
        fetchJson<ListResponse<RuntimeRevisionItem>>(internalApiBaseUrl, `${internalApiPrefix}/admin/revisions`),
        fetchJson<ListResponse<RuntimeOperationItem>>(internalApiBaseUrl, `${internalApiPrefix}/admin/operations`),
      ])
      setDashboard({ health, capabilities: capabilities.items, licenseStatus, runtimeMetrics, revisions: revisions.items, operations: operations.items })
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

  const overviewCards = useMemo(
    () => [
      { title: '能力数量', value: dashboard.health?.capability_count ?? 0, description: '当前可对外提供推理能力数量。' },
      { title: '活动 revision', value: dashboard.health?.runtime_revision_id ?? 0, description: '当前运行态版本编号。' },
      { title: '累计请求', value: dashboard.runtimeMetrics?.request_summary.capability_total_requests ?? 0, description: '聚合能力请求总量。' },
      { title: '池利用率', value: `${Math.round((dashboard.runtimeMetrics?.pool_summary.utilization_ratio ?? 0) * 100)}%`, description: 'busy / total 槽位利用率。' },
    ],
    [dashboard],
  )

  async function handleInfer(): Promise<void> {
    if (!selectedCapability) {
      setActionMessage('请先选择能力。')
      return
    }
    try {
      setActionMessage('正在执行推理...')
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
      <header className="hero">
        <div className="hero-text">
          <p className="eyebrow">北京爱知之星科技股份有限公司（Agile Star）</p>
          <h1>ai-prod 专业运行控制台</h1>
          <p>围绕 capability 目录、运行指标、在线验收与 revision 切换统一呈现内部测试验收外壳。</p>
        </div>
        <div className="hero-panel">
          <div><span className="label">服务端口</span><strong>26004</strong></div>
          <div><span className="label">生产主链路</span><strong>C++ HTTP Runtime</strong></div>
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
            <h2>运行工作台</h2>
            <div className="toolbar">
              <div className="tab-list">
                {tabs.map((tab) => (
                  <button
                    key={tab}
                    className={`tab-button${activeTab === tab ? ' active' : ''}`}
                    onClick={() => setActiveTab(tab)}
                  >
                    {tab === 'overview' ? '概览' : tab === 'catalog' ? '能力目录' : tab === 'control' ? '在线控制' : '修订与操作'}
                  </button>
                ))}
              </div>
              <button className="action-button" onClick={() => void loadDashboard()}>刷新数据</button>
            </div>
          </div>
          {loading && <p className="info-text">正在加载 ai-prod 当前数据...</p>}
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
              <h3>License 状态</h3>
              <pre className="json-block">{JSON.stringify(dashboard.licenseStatus, null, 2)}</pre>
            </article>
            <article className="sub-panel">
              <h3>Endpoint 指标</h3>
              <pre className="json-block">{JSON.stringify(dashboard.runtimeMetrics?.endpoint_metrics ?? {}, null, 2)}</pre>
            </article>
          </section>
        )}

        {activeTab === 'catalog' && (
          <section className="panel split-layout">
            <article className="sub-panel">
              <h3>能力列表</h3>
              <div className="list-stack">
                {dashboard.capabilities.map((item) => (
                  <button
                    key={item.capability_name}
                    className={`list-item-button${selectedCapability === item.capability_name ? ' active' : ''}`}
                    onClick={() => setSelectedCapability(item.capability_name)}
                  >
                    <strong>{item.capability_name}</strong>
                    <span>{item.model_version}</span>
                    <span>{item.backend_type}</span>
                  </button>
                ))}
              </div>
            </article>
            <article className="sub-panel">
              <h3>能力详情</h3>
              <pre className="json-block">{JSON.stringify(selectedCapabilityDetail, null, 2)}</pre>
            </article>
          </section>
        )}

        {activeTab === 'control' && (
          <section className="panel split-layout">
            <article className="sub-panel">
              <div className="section-header">
                <h3>在线推理验收</h3>
                <div className="button-row">
                  <button onClick={() => void handleRuntimeAction('reload')}>执行 reload</button>
                  <button onClick={() => void handleRuntimeAction('rollback', selectedRevisionId ?? undefined)}>回滚到选中 revision</button>
                </div>
              </div>
              <div className="form-grid">
                <label>
                  能力
                  <select value={selectedCapability} onChange={(event) => setSelectedCapability(event.target.value)}>
                    <option value="">请选择能力</option>
                    {dashboard.capabilities.map((item) => <option key={item.capability_name} value={item.capability_name}>{item.capability_name}</option>)}
                  </select>
                </label>
                <label>
                  输入类型
                  <select value={inputType} onChange={(event) => setInputType(event.target.value as 'json' | 'image' | 'video' | 'pdf')}>
                    <option value="json">json</option>
                    <option value="image">image</option>
                    <option value="video">video</option>
                    <option value="pdf">pdf</option>
                  </select>
                </label>
                <label>
                  设备偏好
                  <select value={preferDevice} onChange={(event) => setPreferDevice(event.target.value as 'auto' | 'gpu' | 'cpu')}>
                    <option value="auto">auto</option>
                    <option value="gpu">gpu</option>
                    <option value="cpu">cpu</option>
                  </select>
                </label>
                <label className="full-width">Payload<textarea rows={8} value={payload} onChange={(event) => setPayload(event.target.value)} /></label>
              </div>
              <div className="button-row"><button className="action-button" onClick={() => void handleInfer()}>执行推理</button></div>
            </article>
            <article className="sub-panel">
              <h3>推理结果 / 指标摘要</h3>
              <pre className="json-block">{JSON.stringify({ inferResult, requestSummary: dashboard.runtimeMetrics?.request_summary ?? null }, null, 2)}</pre>
            </article>
          </section>
        )}

        {activeTab === 'revision' && (
          <section className="panel split-layout">
            <article className="sub-panel">
              <h3>Revision 列表</h3>
              <div className="list-stack">
                {dashboard.revisions.map((item) => (
                  <button
                    key={item.revision_id}
                    className={`list-item-button${selectedRevisionId === item.revision_id ? ' active' : ''}`}
                    onClick={() => setSelectedRevisionId(item.revision_id)}
                  >
                    <strong>#{item.revision_id}</strong>
                    <span>{item.action} / {item.status}</span>
                    <span>{item.capability_names.join(', ')}</span>
                  </button>
                ))}
              </div>
            </article>
            <article className="sub-panel">
              <h3>操作记录</h3>
              <div className="table-wrap">
                <table>
                  <thead><tr><th>ID</th><th>动作</th><th>状态</th><th>Revision</th></tr></thead>
                  <tbody>
                    {dashboard.operations.map((item) => (
                      <tr key={item.operation_id}>
                        <td>{item.operation_id}</td>
                        <td>{item.action}</td>
                        <td>{item.status}</td>
                        <td>{item.revision_id ?? '-'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </article>
          </section>
        )}
      </main>
    </div>
  )
}

export default App
