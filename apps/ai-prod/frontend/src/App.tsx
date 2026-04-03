import { useEffect, useMemo, useState } from 'react'
import './App.css'

type CapabilityItem = {
  capability_name: string
  plugin_target: string
  model_version: string
  backend_type: string
  active_source: string
  device_mode: string
  pool_size: number
  max_batch_size: number
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
    fallback_applied: boolean
  }
}

type ListResponse<T> = {
  items: T[]
}

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
    idle_pool_slots: number
    utilization_ratio: number
  }
  request_summary: {
    capability_total_requests: number
    capability_failed_requests: number
    busy_reject_count: number
  }
  endpoint_metrics: Record<
    string,
    {
      total_requests: number
      successful_requests: number
      failed_requests: number
      p95_latency_ms: number
    }
  >
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

const roadmapItems = [
  '接入真实 C++ runtime 桥接与更丰富的输入抽象',
  '补充活动版本指针与原子切换策略可视化',
  '扩展多实例池调度、限流与更细粒度并发控制',
  '与 ai-builder / SDK / 现场配置模板做交付联调',
]

const runtimeApiPrefix = '/api/v1'
const internalApiPrefix = '/internal'
const runtimeApiBaseUrl = import.meta.env.VITE_RUNTIME_API_BASE_URL ?? ''
const internalApiBaseUrl = import.meta.env.VITE_INTERNAL_API_BASE_URL ?? ''

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
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [selectedCapability, setSelectedCapability] = useState('')
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
      setDashboard({
        health,
        capabilities: capabilities.items,
        licenseStatus,
        runtimeMetrics,
        revisions: revisions.items,
        operations: operations.items,
      })
      if (!selectedCapability && capabilities.items.length > 0) {
        setSelectedCapability(capabilities.items[0].capability_name)
      }
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : '加载失败')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    void loadDashboard()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const overviewCards = useMemo(
    () => [
      {
        title: '能力数量',
        value: dashboard.health?.capability_count ?? 0,
        description: '当前 runtime 装载并可对外提供推理服务的能力数。',
      },
      {
        title: '当前 revision',
        value: dashboard.health?.runtime_revision_id ?? 0,
        description: '读写隔离下的活动 runtime 版本编号。',
      },
      {
        title: 'license 状态',
        value: dashboard.licenseStatus?.valid ? '通过' : '失败',
        description: dashboard.licenseStatus?.reason ?? '尚未检查',
      },
      {
        title: '操作记录',
        value: dashboard.operations.length,
        description: '跟踪 reload / rollback 与运行时关键操作。',
      },
      {
        title: '累计请求',
        value: dashboard.runtimeMetrics?.request_summary.capability_total_requests ?? 0,
        description: '按 capability 聚合的累计请求数。',
      },
      {
        title: '池利用率',
        value: `${Math.round((dashboard.runtimeMetrics?.pool_summary.utilization_ratio ?? 0) * 100)}%`,
        description: '当前实例池 busy / total 槽位利用率。',
      },
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
    } catch (inferError) {
      setActionMessage(inferError instanceof Error ? inferError.message : '推理失败')
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
    } catch (actionError) {
      setActionMessage(actionError instanceof Error ? actionError.message : `${action} 失败`)
    }
  }

  return (
    <div className="page">
      <header className="hero">
        <div className="hero-text">
          <p className="eyebrow">北京爱知之星科技股份有限公司（Agile Star）</p>
          <div className="title-row">
            <h1>ai-prod 内部测试验收外壳</h1>
            <span className="badge badge-warning">INTERNAL ONLY</span>
          </div>
          <p>
            当前页面仅供内部研发、联调与人工验收使用；生产主链路由 C++ HTTP 服务承载，本外壳负责聚合 runtime
            状态查询、版本切换入口与在线验收测试能力。
          </p>
        </div>
        <div className="hero-panel">
          <div>
            <span className="label">服务端口</span>
            <strong>26004</strong>
          </div>
          <div>
            <span className="label">外壳定位</span>
            <strong>Python / React 内部验收外壳</strong>
          </div>
          <div>
            <span className="label">生产主链路</span>
            <strong>C++ HTTP 服务（26004）</strong>
          </div>
        </div>
      </header>

      <main className="content">
        <section className="panel">
          <div className="section-header">
            <h2>运行概览</h2>
            <span className="badge">P12 内部验收外壳</span>
          </div>
          {loading && <p className="info-text">正在加载 ai-prod 当前数据...</p>}
          {error && <p className="error-text">数据加载失败：{error}</p>}
          {actionMessage && <p className="info-text">{actionMessage}</p>}
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

        <section className="panel">
          <div className="section-header">
            <h2>能力与授权状态</h2>
            <span className="badge badge-muted">真实查询接口</span>
          </div>
          <div className="table-grid">
            <article className="sub-panel">
              <h3>能力列表</h3>
              <table>
                <thead>
                  <tr>
                    <th>能力</th>
                    <th>模型版本</th>
                    <th>插件目标</th>
                    <th>max_batch_size</th>
                  </tr>
                </thead>
                <tbody>
                  {dashboard.capabilities.map((item) => (
                    <tr key={item.capability_name}>
                      <td>{item.capability_name}</td>
                      <td>{item.model_version}</td>
                      <td>{item.plugin_target}</td>
                      <td>{item.max_batch_size}</td>
                    </tr>
                  ))}
                  {dashboard.capabilities.length === 0 && (
                    <tr>
                      <td colSpan={4}>暂无已装载能力</td>
                    </tr>
                  )}
                </tbody>
              </table>
            </article>

            <article className="sub-panel">
              <h3>license 状态</h3>
              <p className={dashboard.licenseStatus?.valid ? 'success-text' : 'error-text'}>
                {dashboard.licenseStatus?.reason ?? '暂无数据'}
              </p>
              <ul>
                <li>客户编号：{dashboard.licenseStatus?.customer_code ?? '未知'}</li>
                <li>活动 revision：{dashboard.licenseStatus?.runtime_revision_id ?? '无'}</li>
                <li>能力范围：{dashboard.licenseStatus?.capability_scope.join(', ') || '全部'}</li>
                <li>检查时间：{dashboard.licenseStatus?.checked_at_cst ?? '未检查'}</li>
              </ul>
            </article>
          </div>
        </section>

        <section className="panel">
          <div className="section-header">
            <h2>运行时指标</h2>
            <span className="badge badge-muted">/api/v1/admin/metrics</span>
          </div>
          <div className="table-grid">
            <article className="sub-panel">
              <h3>总体指标</h3>
              <ul>
                <li>运行时长：{dashboard.runtimeMetrics?.uptime_seconds ?? 0}s</li>
                <li>活动请求：{dashboard.runtimeMetrics?.active_request_count ?? 0}</li>
                <li>当前 revision：{dashboard.runtimeMetrics?.runtime_revision_id ?? '无'}</li>
                <li>实例池总槽位：{dashboard.runtimeMetrics?.pool_summary.total_pool_slots ?? 0}</li>
                <li>繁忙槽位：{dashboard.runtimeMetrics?.pool_summary.busy_pool_slots ?? 0}</li>
                <li>失败请求：{dashboard.runtimeMetrics?.request_summary.capability_failed_requests ?? 0}</li>
                <li>繁忙拒绝：{dashboard.runtimeMetrics?.request_summary.busy_reject_count ?? 0}</li>
              </ul>
            </article>
            <article className="sub-panel">
              <h3>接口延迟摘要</h3>
              <table>
                <thead>
                  <tr>
                    <th>接口</th>
                    <th>请求数</th>
                    <th>失败数</th>
                    <th>P95 延迟</th>
                  </tr>
                </thead>
                <tbody>
                  {Object.entries(dashboard.runtimeMetrics?.endpoint_metrics ?? {}).map(([endpoint, metrics]) => (
                    <tr key={endpoint}>
                      <td>{endpoint}</td>
                      <td>{metrics.total_requests}</td>
                      <td>{metrics.failed_requests}</td>
                      <td>{metrics.p95_latency_ms} ms</td>
                    </tr>
                  ))}
                  {Object.keys(dashboard.runtimeMetrics?.endpoint_metrics ?? {}).length === 0 && (
                    <tr>
                      <td colSpan={4}>暂无运行时指标</td>
                    </tr>
                  )}
                </tbody>
              </table>
            </article>
          </div>
        </section>

        <section className="panel">
          <div className="section-header">
            <h2>reload / rollback</h2>
            <span className="badge badge-muted">内部验收切换入口</span>
          </div>
          <div className="table-grid">
            <article className="sub-panel">
              <h3>revision 列表</h3>
              <button className="action-button" onClick={() => void handleRuntimeAction('reload')}>
                立即 reload
              </button>
              <table>
                <thead>
                  <tr>
                    <th>ID</th>
                    <th>动作</th>
                    <th>能力数</th>
                    <th>操作</th>
                  </tr>
                </thead>
                <tbody>
                  {dashboard.revisions.map((item) => (
                    <tr key={item.revision_id}>
                      <td>{item.revision_id}</td>
                      <td>{item.action}</td>
                      <td>{item.capability_names.length}</td>
                      <td>
                        <button
                          className="link-button"
                          onClick={() => void handleRuntimeAction('rollback', item.revision_id)}
                        >
                          回滚到此版本
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </article>

            <article className="sub-panel">
              <h3>操作记录</h3>
              <table>
                <thead>
                  <tr>
                    <th>ID</th>
                    <th>动作</th>
                    <th>状态</th>
                  </tr>
                </thead>
                <tbody>
                  {dashboard.operations.map((item) => (
                    <tr key={item.operation_id}>
                      <td>{item.operation_id}</td>
                      <td>{item.action}</td>
                      <td>{item.status}</td>
                    </tr>
                  ))}
                  {dashboard.operations.length === 0 && (
                    <tr>
                      <td colSpan={3}>暂无操作记录</td>
                    </tr>
                  )}
                </tbody>
              </table>
            </article>
          </div>
        </section>

        <section className="panel split">
          <article className="sub-panel">
            <h2>内置测试页</h2>
            <p className="info-text">该页面仅用于内部验收，不作为客户生产调用入口。</p>
            <div className="form-grid">
              <label>
                <span>能力</span>
                <select value={selectedCapability} onChange={(event) => setSelectedCapability(event.target.value)}>
                  {dashboard.capabilities.map((item) => (
                    <option key={item.capability_name} value={item.capability_name}>
                      {item.capability_name}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                <span>输入类型</span>
                <select value={inputType} onChange={(event) => setInputType(event.target.value as 'json' | 'image' | 'video' | 'pdf')}>
                  <option value="json">json</option>
                  <option value="image">image</option>
                  <option value="video">video</option>
                  <option value="pdf">pdf</option>
                </select>
              </label>
              <label>
                <span>设备偏好</span>
                <select value={preferDevice} onChange={(event) => setPreferDevice(event.target.value as 'auto' | 'gpu' | 'cpu')}>
                  <option value="auto">auto</option>
                  <option value="gpu">gpu</option>
                  <option value="cpu">cpu</option>
                </select>
              </label>
              <label className="full-width">
                <span>请求载荷</span>
                <textarea value={payload} onChange={(event) => setPayload(event.target.value)} rows={8} />
              </label>
              <button className="action-button" onClick={() => void handleInfer()}>
                执行推理
              </button>
            </div>
          </article>

          <article className="sub-panel">
            <h2>推理结果</h2>
            {inferResult ? (
              <div className="result-block">
                <p>请求 ID：{inferResult.request_id}</p>
                <p>能力：{inferResult.capability_name}</p>
                <p>模型版本：{inferResult.model_version}</p>
                <p>设备：{inferResult.device}</p>
                <pre>{JSON.stringify(inferResult.result, null, 2)}</pre>
              </div>
            ) : (
              <p>尚未执行推理。</p>
            )}
          </article>
        </section>

        <section className="panel split">
          <article className="sub-panel">
            <h2>实现说明</h2>
            <ul>
              <li>宿主机挂载目录优先，镜像基线目录兜底。</li>
              <li>启动与推理时均执行 license 双层校验。</li>
              <li>运行时按 revision 管理活动能力集合，支持 reload/rollback。</li>
              <li>GPU 优先，GPU 不可用时自动回退 CPU。</li>
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
