import { useEffect, useMemo, useState } from 'react'
import './App.css'
import '../../../frontend-common/src/r7Workspace.css'
import { buildR7Workspace } from '../../../frontend-common/src/r7Workspace.ts'

type CustomerItem = {
  customer_id: number
  customer_code: string
  customer_name: string
  contact_name?: string | null
  contact_email?: string | null
  status: string
}

type KeyPairItem = {
  key_pair_id: number
  key_name: string
  algorithm: string
  public_key_path: string
  private_key_path: string
  status: string
  rotation_version: number
  predecessor_key_pair_id?: number | null
  status_changed_at_cst?: string | null
  status_reason?: string | null
}

type LicensePolicyItem = {
  policy_id: number
  policy_name: string
  customer_id: number
  customer_code: string
  key_pair_id: number
  key_name: string
  capability_scope: string[]
  version_constraints: Record<string, unknown>
  hardware_fingerprint?: string | null
  operating_system: string
  min_operating_system_version?: string | null
  system_architecture?: string | null
  application_name: string
  start_at_cst: string
  expire_at_cst: string
  status: string
  notes?: string | null
}

type LicenseIssueItem = {
  issue_record_id: number
  policy_id: number
  customer_id: number
  customer_code: string
  key_pair_id: number
  key_name: string
  status: string
  hardware_fingerprint?: string | null
  capability_scope: string[]
  version_constraints: Record<string, unknown>
  operating_system: string
  min_operating_system_version?: string | null
  system_architecture?: string | null
  application_name: string
  license_path: string
  public_key_export_path: string
  issued_at_cst: string
  last_validation_at?: string | null
  last_validation_result?: string | null
  last_validation_code?: string | null
  last_validation_details?: Record<string, unknown>
}

type LicenseIssueDetail = LicenseIssueItem & {
  payload: Record<string, unknown>
}

type ValidateLicenseResult = {
  valid: boolean
  reason: string
  result: string
  code: string
  stage: string
  details: Record<string, unknown>
  diagnostics_version: string
}

type LicenseToolReleaseItem = {
  release_id: number
  tool_name: string
  version: string
  status: string
  archive_path: string
  manifest_path: string
  readme_path: string
  checksum_sha256: string
}

type AuditLogItem = {
  happened_at_cst: string
  action: string
  entity_type: string
  entity_id: string
  detail: Record<string, unknown>
}

type ApiListResponse<T> = { items: T[] }

type DashboardState = {
  customers: CustomerItem[]
  keyPairs: KeyPairItem[]
  policies: LicensePolicyItem[]
  issues: LicenseIssueItem[]
  toolReleases: LicenseToolReleaseItem[]
  auditLogs: AuditLogItem[]
}

type CustomerFormState = {
  customer_code: string
  customer_name: string
  contact_name: string
  contact_email: string
}

type PolicyFormState = {
  policy_name: string
  customer_id: string
  key_pair_id: string
  capability_scope: string
  version_constraints: string
  hardware_fingerprint: string
  operating_system: string
  min_operating_system_version: string
  system_architecture: string
  application_name: string
  start_at_cst: string
  expire_at_cst: string
  notes: string
}

type ValidationFormState = {
  hardware_fingerprint: string
  capability_name: string
  product_version: string
  operating_system: string
  operating_system_version: string
  system_architecture: string
}

const apiBaseUrl = import.meta.env.VITE_API_BASE_URL ?? ''
const workspace = buildR7Workspace(import.meta.env, 'ai-license-mgr')


const initialState: DashboardState = {
  customers: [],
  keyPairs: [],
  policies: [],
  issues: [],
  toolReleases: [],
  auditLogs: [],
}

const initialCustomerForm: CustomerFormState = {
  customer_code: '',
  customer_name: '',
  contact_name: '',
  contact_email: '',
}

const initialPolicyForm: PolicyFormState = {
  policy_name: '',
  customer_id: '',
  key_pair_id: '',
  capability_scope: '',
  version_constraints: '{\n  "allowed_versions": []\n}',
  hardware_fingerprint: '',
  operating_system: 'linux',
  min_operating_system_version: '',
  system_architecture: '',
  application_name: 'ai-prod',
  start_at_cst: '2026-04-05T00:00:00+08:00',
  expire_at_cst: '2027-04-05T00:00:00+08:00',
  notes: '',
}

const initialValidationForm: ValidationFormState = {
  hardware_fingerprint: '',
  capability_name: '',
  product_version: '',
  operating_system: 'linux',
  operating_system_version: '',
  system_architecture: '',
}

const tabs = ['overview', 'customer', 'policy', 'issue', 'tool'] as const
type TabKey = (typeof tabs)[number]

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
  const payload = await request<ApiListResponse<T>>(path)
  return payload.items
}

function App() {
  const [dashboard, setDashboard] = useState<DashboardState>(initialState)
  const [activeTab, setActiveTab] = useState<TabKey>('overview')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [actionMessage, setActionMessage] = useState<string | null>(null)
  const [customerForm, setCustomerForm] = useState<CustomerFormState>(initialCustomerForm)
  const [keyName, setKeyName] = useState('agile-star-key')
  const [rotateReason, setRotateReason] = useState('例行轮转')
  const [isolateReason, setIsolateReason] = useState('风险隔离')
  const [policyForm, setPolicyForm] = useState<PolicyFormState>(initialPolicyForm)
  const [selectedIssueId, setSelectedIssueId] = useState<number | null>(null)
  const [issueDetail, setIssueDetail] = useState<LicenseIssueDetail | null>(null)
  const [validationForm, setValidationForm] = useState<ValidationFormState>(initialValidationForm)
  const [lastValidationResult, setLastValidationResult] = useState<ValidateLicenseResult | null>(null)

  async function loadDashboard(): Promise<void> {
    setLoading(true)
    setError(null)
    try {
      const [customers, keyPairs, policies, issues, toolReleases, auditLogs] = await Promise.all([
        fetchList<CustomerItem>('/api/v1/customers'),
        fetchList<KeyPairItem>('/api/v1/key-pairs'),
        fetchList<LicensePolicyItem>('/api/v1/license-policies'),
        fetchList<LicenseIssueItem>('/api/v1/license-issues'),
        fetchList<LicenseToolReleaseItem>('/api/v1/tool-releases'),
        fetchList<AuditLogItem>('/api/v1/audit-logs?limit=8'),
      ])
      setDashboard({ customers, keyPairs, policies, issues, toolReleases, auditLogs })
      setSelectedIssueId((current) => current ?? issues[0]?.issue_record_id ?? null)
      setPolicyForm((current) => ({
        ...current,
        customer_id: current.customer_id || String(customers[0]?.customer_id ?? ''),
        key_pair_id: current.key_pair_id || String(keyPairs[0]?.key_pair_id ?? ''),
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
    if (selectedIssueId == null) {
      setIssueDetail(null)
      setLastValidationResult(null)
      return
    }
    void request<LicenseIssueDetail>(`/api/v1/license-issues/${selectedIssueId}`).then(setIssueDetail).catch(() => {
      setIssueDetail(null)
    })
  }, [selectedIssueId])

  const overviewCards = useMemo(
    () => [
      { title: '客户', value: dashboard.customers.length, description: '支持客户主数据与联系人信息管理。' },
      { title: '密钥对', value: dashboard.keyPairs.length, description: '支持创建、轮转、隔离与前序链路追踪。' },
      { title: '授权策略', value: dashboard.policies.length, description: '支持能力范围、版本约束与指纹规则。' },
      { title: '签发记录', value: dashboard.issues.length, description: '支持签发、校验、导出与运行态复核。' },
    ],
    [dashboard],
  )

  async function handleCreateCustomer(): Promise<void> {
    await request<CustomerItem>('/api/v1/customers', {
      method: 'POST',
      body: JSON.stringify(customerForm),
    })
    setCustomerForm(initialCustomerForm)
    setActionMessage('客户已创建')
    await loadDashboard()
  }

  async function handleCreateKeyPair(): Promise<void> {
    await request<KeyPairItem>('/api/v1/key-pairs', {
      method: 'POST',
      body: JSON.stringify({ key_name: keyName }),
    })
    setActionMessage('密钥对已创建')
    await loadDashboard()
  }

  async function handleRotateKeyPair(keyPairId: number): Promise<void> {
    await request(`/api/v1/key-pairs/${keyPairId}/rotate`, {
      method: 'POST',
      body: JSON.stringify({ reason: rotateReason }),
    })
    setActionMessage(`密钥 #${keyPairId} 已轮转`)
    await loadDashboard()
  }

  async function handleIsolateKeyPair(keyPairId: number): Promise<void> {
    await request(`/api/v1/key-pairs/${keyPairId}/isolate`, {
      method: 'POST',
      body: JSON.stringify({ reason: isolateReason }),
    })
    setActionMessage(`密钥 #${keyPairId} 已隔离`)
    await loadDashboard()
  }

  async function handleCreatePolicy(): Promise<void> {
    await request<LicensePolicyItem>('/api/v1/license-policies', {
      method: 'POST',
      body: JSON.stringify({
        ...policyForm,
        customer_id: Number(policyForm.customer_id),
        key_pair_id: Number(policyForm.key_pair_id),
        capability_scope: policyForm.capability_scope
          .split(',')
          .map((item) => item.trim())
          .filter(Boolean),
        version_constraints: JSON.parse(policyForm.version_constraints),
        hardware_fingerprint: policyForm.hardware_fingerprint || null,
        operating_system: policyForm.operating_system,
        min_operating_system_version: policyForm.min_operating_system_version || null,
        system_architecture: policyForm.system_architecture || null,
        application_name: policyForm.application_name,
        notes: policyForm.notes || null,
      }),
    })
    setActionMessage('授权策略已创建')
    await loadDashboard()
  }

  async function handleIssueLicense(policyId: number): Promise<void> {
    const created = await request<LicenseIssueDetail>('/api/v1/license-issues', {
      method: 'POST',
      body: JSON.stringify({ policy_id: policyId }),
    })
    setSelectedIssueId(created.issue_record_id)
    setActionMessage(`策略 #${policyId} 已完成签发`)
    await loadDashboard()
  }

  async function handleValidateIssue(): Promise<void> {
    if (selectedIssueId == null) {
      return
    }
    const result = await request<ValidateLicenseResult>(`/api/v1/license-issues/${selectedIssueId}/validate`, {
      method: 'POST',
      body: JSON.stringify({
        hardware_fingerprint: validationForm.hardware_fingerprint || null,
        capability_name: validationForm.capability_name || null,
        product_version: validationForm.product_version || null,
        operating_system: validationForm.operating_system || null,
        operating_system_version: validationForm.operating_system_version || null,
        system_architecture: validationForm.system_architecture || null,
      }),
    })
    setLastValidationResult(result)
    setActionMessage(`校验结果：${result.valid ? '通过' : '失败'} / ${result.code}`)
    await loadDashboard()
  }

  async function handleSyncToolRelease(): Promise<void> {
    await request<LicenseToolReleaseItem>('/api/v1/tool-releases/sync-default', { method: 'POST' })
    setActionMessage('默认 license_tool 发布已同步')
    await loadDashboard()
  }

  function exportUrl(path: string): string {
    return `${apiBaseUrl}${path}`
  }

  return (
    <div className="page">
      <header className="hero">
        <div className="hero-text">
          <p className="eyebrow">北京爱知之星科技股份有限公司（Agile Star）</p>
          <h1>ai-license-mgr 专业授权台</h1>
          <p>统一收口授权金标准测试向量、稳定诊断字段、签发校验与工具发布，支撑 ai-prod / SDK / license_tool 一致性联调。</p>
        </div>
        <div className="hero-panel">
          <div><span className="label">服务端口</span><strong>26002</strong></div>
          <div><span className="label">关键物料</span><strong>license.bin / pubkey.pem / license_tool</strong></div>
          <div><span className="label">当前阶段</span><strong>L11 / L12 / L13 执行中</strong></div>
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
            <h2>工作台</h2>
            <div className="toolbar">
              <div className="tab-list">
                {tabs.map((tab) => (
                  <button
                    key={tab}
                    className={`tab-button${activeTab === tab ? ' active' : ''}`}
                    onClick={() => setActiveTab(tab)}
                  >
                    {tab === 'overview' ? '概览' : tab === 'customer' ? '客户与密钥' : tab === 'policy' ? '策略与签发' : tab === 'issue' ? '签发详情' : '工具发布'}
                  </button>
                ))}
              </div>
              <button className="action-button" onClick={() => void loadDashboard()}>刷新数据</button>
            </div>
          </div>
          {loading && <p className="info-text">正在加载 ai-license-mgr 当前数据...</p>}
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
              <h3>最近审计日志</h3>
              <ul>
                {dashboard.auditLogs.map((item) => (
                  <li key={`${item.entity_type}-${item.entity_id}-${item.happened_at_cst}`}>
                    {item.happened_at_cst} / {item.action} / {item.entity_type} #{item.entity_id}
                  </li>
                ))}
                {dashboard.auditLogs.length === 0 && <li>暂无审计记录</li>}
              </ul>
            </article>
            <article className="sub-panel">
              <h3>联调就绪项</h3>
              <ul>
                <li>已支持私钥轮转、隔离与策略迁移。</li>
                <li>已支持签发记录稳定 code / stage / details 校验输出。</li>
                <li>已支持默认 license_tool 发布同步、诊断契约与测试向量导出。</li>
              </ul>
            </article>
          </section>
        )}

        {activeTab === 'customer' && (
          <section className="panel split-layout">
            <article className="sub-panel">
              <h3>创建客户</h3>
              <div className="form-grid">
                <label>客户编码<input value={customerForm.customer_code} onChange={(event) => setCustomerForm((current) => ({ ...current, customer_code: event.target.value }))} /></label>
                <label>客户名称<input value={customerForm.customer_name} onChange={(event) => setCustomerForm((current) => ({ ...current, customer_name: event.target.value }))} /></label>
                <label>联系人<input value={customerForm.contact_name} onChange={(event) => setCustomerForm((current) => ({ ...current, contact_name: event.target.value }))} /></label>
                <label>联系邮箱<input value={customerForm.contact_email} onChange={(event) => setCustomerForm((current) => ({ ...current, contact_email: event.target.value }))} /></label>
              </div>
              <div className="button-row"><button className="action-button" onClick={() => void handleCreateCustomer()}>创建客户</button></div>

              <h3 className="section-title">创建密钥对</h3>
              <div className="form-grid">
                <label>密钥名称<input value={keyName} onChange={(event) => setKeyName(event.target.value)} /></label>
                <label>轮转原因<input value={rotateReason} onChange={(event) => setRotateReason(event.target.value)} /></label>
                <label>隔离原因<input value={isolateReason} onChange={(event) => setIsolateReason(event.target.value)} /></label>
              </div>
              <div className="button-row"><button className="action-button" onClick={() => void handleCreateKeyPair()}>创建密钥对</button></div>
            </article>

            <article className="sub-panel">
              <h3>客户列表</h3>
              <div className="table-wrap">
                <table>
                  <thead><tr><th>编码</th><th>名称</th><th>状态</th></tr></thead>
                  <tbody>
                    {dashboard.customers.map((item) => (
                      <tr key={item.customer_id}><td>{item.customer_code}</td><td>{item.customer_name}</td><td>{item.status}</td></tr>
                    ))}
                  </tbody>
                </table>
              </div>

              <h3 className="section-title">密钥列表</h3>
              <div className="table-wrap">
                <table>
                  <thead><tr><th>名称</th><th>状态</th><th>轮转</th><th>操作</th></tr></thead>
                  <tbody>
                    {dashboard.keyPairs.map((item) => (
                      <tr key={item.key_pair_id}>
                        <td>{item.key_name}</td>
                        <td>{item.status}</td>
                        <td>v{item.rotation_version}</td>
                        <td>
                          <div className="button-row compact">
                            <button onClick={() => void handleRotateKeyPair(item.key_pair_id)}>轮转</button>
                            <button onClick={() => void handleIsolateKeyPair(item.key_pair_id)}>隔离</button>
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </article>
          </section>
        )}

        {activeTab === 'policy' && (
          <section className="panel split-layout">
            <article className="sub-panel">
              <h3>创建授权策略</h3>
              <div className="form-grid">
                <label>策略名称<input value={policyForm.policy_name} onChange={(event) => setPolicyForm((current) => ({ ...current, policy_name: event.target.value }))} /></label>
                <label>
                  客户
                  <select value={policyForm.customer_id} onChange={(event) => setPolicyForm((current) => ({ ...current, customer_id: event.target.value }))}>
                    <option value="">请选择客户</option>
                    {dashboard.customers.map((item) => <option key={item.customer_id} value={item.customer_id}>{item.customer_code}</option>)}
                  </select>
                </label>
                <label>
                  密钥
                  <select value={policyForm.key_pair_id} onChange={(event) => setPolicyForm((current) => ({ ...current, key_pair_id: event.target.value }))}>
                    <option value="">请选择密钥</option>
                    {dashboard.keyPairs.map((item) => <option key={item.key_pair_id} value={item.key_pair_id}>{item.key_name}</option>)}
                  </select>
                </label>
                <label>能力范围<input value={policyForm.capability_scope} onChange={(event) => setPolicyForm((current) => ({ ...current, capability_scope: event.target.value }))} placeholder="capability_a,capability_b" /></label>
                <label>硬件指纹<input value={policyForm.hardware_fingerprint} onChange={(event) => setPolicyForm((current) => ({ ...current, hardware_fingerprint: event.target.value }))} /></label>
                <label>
                  操作系统
                  <select value={policyForm.operating_system} onChange={(event) => setPolicyForm((current) => ({ ...current, operating_system: event.target.value }))}>
                    <option value="windows">windows</option>
                    <option value="linux">linux</option>
                    <option value="android">android</option>
                    <option value="ios">ios</option>
                  </select>
                </label>
                <label>最低系统版本<input value={policyForm.min_operating_system_version} onChange={(event) => setPolicyForm((current) => ({ ...current, min_operating_system_version: event.target.value }))} placeholder="可选，例如 13.0.0" /></label>
                <label>系统架构<input value={policyForm.system_architecture} onChange={(event) => setPolicyForm((current) => ({ ...current, system_architecture: event.target.value }))} placeholder="可选，例如 x86_64 / arm64" /></label>
                <label>应用名称<input value={policyForm.application_name} onChange={(event) => setPolicyForm((current) => ({ ...current, application_name: event.target.value }))} /></label>
                <label>开始时间<input value={policyForm.start_at_cst} onChange={(event) => setPolicyForm((current) => ({ ...current, start_at_cst: event.target.value }))} /></label>
                <label>结束时间<input value={policyForm.expire_at_cst} onChange={(event) => setPolicyForm((current) => ({ ...current, expire_at_cst: event.target.value }))} /></label>
                <label className="full-width">版本约束<textarea rows={5} value={policyForm.version_constraints} onChange={(event) => setPolicyForm((current) => ({ ...current, version_constraints: event.target.value }))} /></label>
                <label className="full-width">备注<textarea rows={3} value={policyForm.notes} onChange={(event) => setPolicyForm((current) => ({ ...current, notes: event.target.value }))} /></label>
              </div>
              <div className="button-row"><button className="action-button" onClick={() => void handleCreatePolicy()}>创建策略</button></div>
            </article>

            <article className="sub-panel">
              <h3>策略列表与签发</h3>
              <div className="table-wrap">
                <table>
                  <thead><tr><th>策略</th><th>客户</th><th>密钥</th><th>操作</th></tr></thead>
                  <tbody>
                    {dashboard.policies.map((item) => (
                      <tr key={item.policy_id}>
                        <td>{item.policy_name}</td>
                        <td>{item.customer_code}</td>
                        <td>{item.key_name}</td>
                        <td><button onClick={() => void handleIssueLicense(item.policy_id)}>签发</button></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </article>
          </section>
        )}

        {activeTab === 'issue' && (
          <section className="panel split-layout">
            <article className="sub-panel">
              <h3>签发记录</h3>
              <div className="list-stack">
                {dashboard.issues.map((item) => (
                  <button
                    key={item.issue_record_id}
                    className={`list-item-button${selectedIssueId === item.issue_record_id ? ' active' : ''}`}
                    onClick={() => setSelectedIssueId(item.issue_record_id)}
                  >
                    <strong>#{item.issue_record_id}</strong>
                    <span>{item.customer_code}</span>
                    <span>{item.last_validation_code ?? item.status}</span>
                  </button>
                ))}
              </div>
            </article>

            <article className="sub-panel">
              <div className="section-header">
                <h3>签发详情 / 校验 / 导出</h3>
                {selectedIssueId != null && (
                  <div className="button-row compact">
                    <a className="action-link" href={exportUrl(`/api/v1/license-issues/${selectedIssueId}/export?export_format=bin`)}>导出 license</a>
                    <a className="action-link" href={exportUrl(`/api/v1/license-issues/${selectedIssueId}/export?export_format=pubkey`)}>导出公钥</a>
                  </div>
                )}
              </div>
              {issueDetail == null ? (
                <p className="info-text">请选择签发记录。</p>
              ) : (
                <>
                  <pre className="json-block">{JSON.stringify(issueDetail.payload, null, 2)}</pre>
                  <pre className="json-block">
                    {JSON.stringify(
                      {
                        operating_system: issueDetail.operating_system,
                        min_operating_system_version: issueDetail.min_operating_system_version,
                        system_architecture: issueDetail.system_architecture,
                        application_name: issueDetail.application_name,
                        last_validation_result: issueDetail.last_validation_result,
                        last_validation_code: issueDetail.last_validation_code,
                        last_validation_details: issueDetail.last_validation_details ?? {},
                        latest_validation_response: lastValidationResult ?? undefined,
                      },
                      null,
                      2,
                    )}
                  </pre>
                  <div className="form-grid">
                    <label>硬件指纹<input value={validationForm.hardware_fingerprint} onChange={(event) => setValidationForm((current) => ({ ...current, hardware_fingerprint: event.target.value }))} /></label>
                    <label>能力<input value={validationForm.capability_name} onChange={(event) => setValidationForm((current) => ({ ...current, capability_name: event.target.value }))} /></label>
                    <label>产品版本<input value={validationForm.product_version} onChange={(event) => setValidationForm((current) => ({ ...current, product_version: event.target.value }))} /></label>
                    <label>
                      操作系统
                      <select value={validationForm.operating_system} onChange={(event) => setValidationForm((current) => ({ ...current, operating_system: event.target.value }))}>
                        <option value="">自动/不传</option>
                        <option value="windows">windows</option>
                        <option value="linux">linux</option>
                        <option value="android">android</option>
                        <option value="ios">ios</option>
                      </select>
                    </label>
                    <label>系统版本<input value={validationForm.operating_system_version} onChange={(event) => setValidationForm((current) => ({ ...current, operating_system_version: event.target.value }))} placeholder="例如 5.15.0 / 13.0.0" /></label>
                    <label>系统架构<input value={validationForm.system_architecture} onChange={(event) => setValidationForm((current) => ({ ...current, system_architecture: event.target.value }))} placeholder="例如 x86_64 / arm64" /></label>
                  </div>
                  <div className="button-row"><button className="action-button" onClick={() => void handleValidateIssue()}>执行校验</button></div>
                </>
              )}
            </article>
          </section>
        )}

        {activeTab === 'tool' && (
          <section className="panel split-layout">
            <article className="sub-panel">
              <div className="section-header">
                <h3>license_tool 发布</h3>
                <button className="action-button" onClick={() => void handleSyncToolRelease()}>同步默认发布</button>
              </div>
              <div className="table-wrap">
                <table>
                  <thead><tr><th>版本</th><th>状态</th><th>导出</th></tr></thead>
                  <tbody>
                    {dashboard.toolReleases.map((item) => (
                      <tr key={item.release_id}>
                        <td>{item.version}</td>
                        <td>{item.status}</td>
                        <td>
                          <div className="button-row compact">
                            <a className="action-link" href={exportUrl(`/api/v1/tool-releases/${item.release_id}/export?export_format=archive`)}>归档</a>
                            <a className="action-link" href={exportUrl(`/api/v1/tool-releases/${item.release_id}/export?export_format=manifest`)}>manifest</a>
                            <a className="action-link" href={exportUrl(`/api/v1/tool-releases/${item.release_id}/export?export_format=readme`)}>README</a>
                            <a className="action-link" href={exportUrl(`/api/v1/tool-releases/${item.release_id}/export?export_format=diagnostics`)}>diagnostics</a>
                            <a className="action-link" href={exportUrl(`/api/v1/tool-releases/${item.release_id}/export?export_format=vectors`)}>vectors</a>
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </article>
            <article className="sub-panel">
              <h3>本轮专业化增强</h3>
              <ul>
                <li>将客户台、策略台、签发台与工具发布整合为页签式工作台。</li>
                <li>提供轮转、隔离、签发、稳定诊断校验与导出直达操作。</li>
                <li>为跨模块联调保留统一的审计、诊断契约与测试向量导出入口。</li>
              </ul>
            </article>
          </section>
        )}
      </main>
    </div>
  )
}

export default App
