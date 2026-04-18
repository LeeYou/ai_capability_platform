import { useEffect, useMemo, useState } from 'react'
import './App.css'
import '../../../frontend-common/src/r7Workspace.css'
import { WorkspaceShell } from '../../../frontend-common/src/workspaceShell.tsx'
import { buildR7Workspace } from '../../../frontend-common/src/r7Workspace.ts'
import { fetchListItems, requestJson } from '../../../frontend-common/src/http.ts'

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
  issue_record_id: number
  checked_at_cst: string
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

type ValidationContract = {
  diagnostics_version: string
  fields: Record<string, unknown>
  code_catalog: Record<string, unknown>
}

type ValidationVectors = {
  diagnostics_version: string
  fingerprint_vectors: Array<Record<string, unknown>>
  version_constraint_vectors: Array<Record<string, unknown>>
  license_validation_vectors: Array<Record<string, unknown>>
}

type ApiListResponse<T> = { items: T[] }

type DashboardState = {
  customers: CustomerItem[]
  keyPairs: KeyPairItem[]
  policies: LicensePolicyItem[]
  issues: LicenseIssueItem[]
  toolReleases: LicenseToolReleaseItem[]
  auditLogs: AuditLogItem[]
  validationContract: ValidationContract | null
  validationVectors: ValidationVectors | null
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
const tabs = ['overview', 'issuance', 'risk', 'validation'] as const
type TabKey = (typeof tabs)[number]

const initialState: DashboardState = {
  customers: [],
  keyPairs: [],
  policies: [],
  issues: [],
  toolReleases: [],
  auditLogs: [],
  validationContract: null,
  validationVectors: null,
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
  start_at_cst: '2026-04-10T00:00:00+08:00',
  expire_at_cst: '2027-04-10T00:00:00+08:00',
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

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  return requestJson<T>(apiBaseUrl, path, init)
}

async function fetchList<T>(path: string): Promise<T[]> {
  return fetchListItems<T>(apiBaseUrl, path)
}

function statusTone(status: string): 'good' | 'warn' | 'danger' | 'neutral' {
  if (['active', 'issued', 'valid', 'ready', 'completed'].includes(status)) return 'good'
  if (['isolated', 'disabled', 'failed', 'expired'].includes(status)) return 'danger'
  if (['draft', 'pending', 'created'].includes(status)) return 'warn'
  return 'neutral'
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
  const [selectedKeyPairId, setSelectedKeyPairId] = useState<number | null>(null)
  const [selectedPolicyId, setSelectedPolicyId] = useState<number | null>(null)
  const [selectedIssueId, setSelectedIssueId] = useState<number | null>(null)
  const [issueDetail, setIssueDetail] = useState<LicenseIssueDetail | null>(null)
  const [validationForm, setValidationForm] = useState<ValidationFormState>(initialValidationForm)
  const [lastValidationResult, setLastValidationResult] = useState<ValidateLicenseResult | null>(null)

  async function loadDashboard(): Promise<void> {
    setLoading(true)
    setError(null)
    try {
      const [customers, keyPairs, policies, issues, toolReleases, auditLogs, validationContract, validationVectors] = await Promise.all([
        fetchList<CustomerItem>('/api/v1/customers'),
        fetchList<KeyPairItem>('/api/v1/key-pairs'),
        fetchList<LicensePolicyItem>('/api/v1/license-policies'),
        fetchList<LicenseIssueItem>('/api/v1/license-issues'),
        fetchList<LicenseToolReleaseItem>('/api/v1/tool-releases'),
        fetchList<AuditLogItem>('/api/v1/audit-logs?limit=8'),
        request<ValidationContract>('/api/v1/license-validation/contract'),
        request<ValidationVectors>('/api/v1/license-validation/vectors'),
      ])
      setDashboard({ customers, keyPairs, policies, issues, toolReleases, auditLogs, validationContract, validationVectors })
      setSelectedKeyPairId((current) => current ?? keyPairs[0]?.key_pair_id ?? null)
      setSelectedPolicyId((current) => current ?? policies[0]?.policy_id ?? null)
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
      return
    }
    void request<LicenseIssueDetail>(`/api/v1/license-issues/${selectedIssueId}`).then(setIssueDetail).catch(() => {
      setIssueDetail(null)
    })
  }, [selectedIssueId])

  const selectedKeyPair = dashboard.keyPairs.find((item) => item.key_pair_id === selectedKeyPairId) ?? null

  const overviewCards = useMemo(
    () => [
      { title: '客户数', value: dashboard.customers.length, description: '正在受理签发与交付服务的客户对象。' },
      { title: '有效密钥', value: dashboard.keyPairs.filter((item) => item.status === 'active').length, description: '当前可用于策略签发的密钥对。' },
      { title: '签发记录', value: dashboard.issues.length, description: '已完成签发并可供 builder 消费的 license 记录。' },
      { title: '工具版本', value: dashboard.toolReleases.length, description: 'license_tool 与诊断材料的发布归档。' },
    ],
    [dashboard],
  )

  const isolatedKeys = useMemo(
    () => dashboard.keyPairs.filter((item) => item.status === 'isolated'),
    [dashboard.keyPairs],
  )

  async function handleCreateCustomer(): Promise<void> {
    try {
      setActionMessage('正在创建客户...')
      await request('/api/v1/customers', {
        method: 'POST',
        body: JSON.stringify({
          customer_code: customerForm.customer_code,
          customer_name: customerForm.customer_name,
          contact_name: customerForm.contact_name || null,
          contact_email: customerForm.contact_email || null,
        }),
      })
      setCustomerForm(initialCustomerForm)
      setActionMessage('客户已创建')
      await loadDashboard()
    } catch (loadError) {
      setActionMessage(loadError instanceof Error ? loadError.message : '创建客户失败')
    }
  }

  async function handleCreateKeyPair(): Promise<void> {
    try {
      setActionMessage('正在创建密钥对...')
      await request('/api/v1/key-pairs', {
        method: 'POST',
        body: JSON.stringify({ key_name: keyName }),
      })
      setActionMessage('密钥对已创建')
      await loadDashboard()
    } catch (loadError) {
      setActionMessage(loadError instanceof Error ? loadError.message : '创建密钥失败')
    }
  }

  async function handleRotateKeyPair(): Promise<void> {
    if (selectedKeyPairId == null) return
    try {
      setActionMessage('正在轮转密钥对...')
      await request(`/api/v1/key-pairs/${selectedKeyPairId}/rotate`, {
        method: 'POST',
        body: JSON.stringify({ reason: rotateReason }),
      })
      setActionMessage('密钥轮转完成')
      await loadDashboard()
    } catch (loadError) {
      setActionMessage(loadError instanceof Error ? loadError.message : '轮转失败')
    }
  }

  async function handleIsolateKeyPair(): Promise<void> {
    if (selectedKeyPairId == null) return
    try {
      setActionMessage('正在隔离密钥对...')
      await request(`/api/v1/key-pairs/${selectedKeyPairId}/isolate`, {
        method: 'POST',
        body: JSON.stringify({ reason: isolateReason }),
      })
      setActionMessage('密钥已隔离')
      await loadDashboard()
    } catch (loadError) {
      setActionMessage(loadError instanceof Error ? loadError.message : '隔离失败')
    }
  }

  async function handleCreatePolicy(): Promise<void> {
    try {
      setActionMessage('正在创建授权策略...')
      const created = await request<LicensePolicyItem>('/api/v1/license-policies', {
        method: 'POST',
        body: JSON.stringify({
          policy_name: policyForm.policy_name,
          customer_id: Number(policyForm.customer_id),
          key_pair_id: Number(policyForm.key_pair_id),
          capability_scope: policyForm.capability_scope.split(',').map((item) => item.trim()).filter(Boolean),
          version_constraints: JSON.parse(policyForm.version_constraints),
          hardware_fingerprint: policyForm.hardware_fingerprint || null,
          operating_system: policyForm.operating_system,
          min_operating_system_version: policyForm.min_operating_system_version || null,
          system_architecture: policyForm.system_architecture || null,
          application_name: policyForm.application_name,
          start_at_cst: policyForm.start_at_cst,
          expire_at_cst: policyForm.expire_at_cst,
          notes: policyForm.notes || null,
        }),
      })
      setSelectedPolicyId(created.policy_id)
      setActionMessage(`授权策略 #${created.policy_id} 已创建`)
      await loadDashboard()
    } catch (loadError) {
      setActionMessage(loadError instanceof Error ? loadError.message : '创建策略失败')
    }
  }

  async function handleIssueLicense(): Promise<void> {
    if (selectedPolicyId == null) return
    try {
      setActionMessage('正在签发 license...')
      const created = await request<LicenseIssueDetail>('/api/v1/license-issues', {
        method: 'POST',
        body: JSON.stringify({ policy_id: selectedPolicyId }),
      })
      setSelectedIssueId(created.issue_record_id)
      setActionMessage(`签发记录 #${created.issue_record_id} 已生成`)
      await loadDashboard()
    } catch (loadError) {
      setActionMessage(loadError instanceof Error ? loadError.message : '签发失败')
    }
  }

  async function handleValidateIssue(): Promise<void> {
    if (selectedIssueId == null) return
    try {
      setActionMessage('正在执行授权校验...')
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
      setActionMessage(`校验完成：${result.code}`)
      await loadDashboard()
    } catch (loadError) {
      setActionMessage(loadError instanceof Error ? loadError.message : '校验失败')
    }
  }

  async function handleSyncToolRelease(): Promise<void> {
    try {
      setActionMessage('正在同步默认 license_tool...')
      await request('/api/v1/tool-releases/sync-default', { method: 'POST' })
      setActionMessage('默认工具版本已同步')
      await loadDashboard()
    } catch (loadError) {
      setActionMessage(loadError instanceof Error ? loadError.message : '同步工具失败')
    }
  }

  function issueExportUrl(issueRecordId: number, format: 'bin' | 'pubkey'): string {
    return `${apiBaseUrl}/api/v1/license-issues/${issueRecordId}/export?export_format=${format}`
  }

  function toolExportUrl(releaseId: number, format: 'archive' | 'manifest' | 'readme' | 'diagnostics' | 'vectors'): string {
    return `${apiBaseUrl}/api/v1/tool-releases/${releaseId}/export?export_format=${format}`
  }

  return (
    <WorkspaceShell moduleId="ai-license-mgr" title="ai-license-mgr" subtitle="统一授权工作台">
      <header className="hero">
        <div className="hero-text">
          <p className="eyebrow">北京爱知之星科技股份有限公司（Agile Star）</p>
          <h1>ai-license-mgr 授权签发工作台</h1>
          <p>
            将客户、密钥、策略、签发、校验、tool release 六类动作收口为连续工作流，
            让交付工程师可以在一个工作台内完成授权全链路作业并直接进入 ai-builder。
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
          <div><span className="label">服务端口</span><strong>26002</strong></div>
          <div><span className="label">当前重点</span><strong>签发向导 / 风险操作 / 校验工作台</strong></div>
          <div><span className="label">诊断版本</span><strong>{dashboard.validationContract?.diagnostics_version ?? '未加载'}</strong></div>
        </div>
      </header>

      <main className="content">
        <section className="panel">
          <div className="section-header">
            <div>
              <h2>首页概览</h2>
              <p>把客户、密钥风险、签发记录与下游动作放在同一个授权首页中统一决策。</p>
            </div>
            <span className="badge">L16-L19</span>
          </div>
          {loading && <p className="info-text">正在加载授权工作台数据...</p>}
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
              <h3>风险密钥与影响面</h3>
              {isolatedKeys.length === 0 ? (
                <div className="workspace-empty">当前没有已隔离密钥。</div>
              ) : (
                <div className="workspace-list">
                  {isolatedKeys.map((item) => (
                    <button
                      key={item.key_pair_id}
                      className={`workspace-list-item${selectedKeyPairId === item.key_pair_id ? ' active' : ''}`}
                      onClick={() => {
                        setSelectedKeyPairId(item.key_pair_id)
                        setActiveTab('risk')
                      }}
                      type="button"
                    >
                      <strong>{item.key_name}</strong>
                      <div className="workspace-meta-row">
                        <span>轮转版本 {item.rotation_version}</span>
                        <span className={`status-pill ${statusTone(item.status)}`}>{item.status}</span>
                      </div>
                    </button>
                  ))}
                </div>
              )}
            </article>
            <article className="workspace-summary-card">
              <h3>当前推荐动作</h3>
              <ul>
                <li>先在“连续签发工作台”完成客户、密钥、策略与签发闭环。</li>
                <li>再在“校验与工具工作台”验证平台字段、结果码与 tool bundle。</li>
                <li>最终把签发记录推进到 ai-builder 构建交付包。</li>
              </ul>
            </article>
          </div>
        </section>

        <section className="panel">
          <div className="toolbar">
            <div>
              <h2>授权工作台</h2>
              <p>围绕连续签发、风险操作与诊断校验组织企业级授权流程。</p>
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
                  {tab === 'issuance' && '连续签发'}
                  {tab === 'risk' && '风险操作'}
                  {tab === 'validation' && '校验与工具'}
                </button>
              ))}
            </div>
          </div>

          {activeTab === 'overview' && (
            <div className="workspace-panel-grid">
              <div className="workspace-stack">
                <article className="workspace-note-block">
                  <h3>最近签发记录</h3>
                  <div className="workspace-list">
                    {dashboard.issues.slice(0, 5).map((item) => (
                      <button
                        key={item.issue_record_id}
                        className={`workspace-list-item${selectedIssueId === item.issue_record_id ? ' active' : ''}`}
                        onClick={() => {
                          setSelectedIssueId(item.issue_record_id)
                          setActiveTab('validation')
                        }}
                        type="button"
                      >
                        <strong>签发 #{item.issue_record_id}</strong>
                        <div className="workspace-meta-row">
                          <span>{item.customer_code}</span>
                          <span>{item.application_name}</span>
                          <span className={`status-pill ${statusTone(item.status)}`}>{item.status}</span>
                        </div>
                      </button>
                    ))}
                  </div>
                </article>
              </div>
              <div className="workspace-stack">
                <article className="workspace-note-block">
                  <h3>最近审计留痕</h3>
                  <div className="workspace-table-wrap">
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

          {activeTab === 'issuance' && (
            <div className="workspace-panel-grid">
              <div className="workspace-stack">
                <article className="workspace-note-block">
                  <div className="section-header">
                    <h3>步骤 1：创建客户</h3>
                    <span className="badge badge-muted">L16</span>
                  </div>
                  <div className="workspace-form-grid">
                    <label className="workspace-field">
                      客户编码
                      <input value={customerForm.customer_code} onChange={(event) => setCustomerForm((current) => ({ ...current, customer_code: event.target.value }))} />
                    </label>
                    <label className="workspace-field">
                      客户名称
                      <input value={customerForm.customer_name} onChange={(event) => setCustomerForm((current) => ({ ...current, customer_name: event.target.value }))} />
                    </label>
                    <label className="workspace-field">
                      联系人
                      <input value={customerForm.contact_name} onChange={(event) => setCustomerForm((current) => ({ ...current, contact_name: event.target.value }))} />
                    </label>
                    <label className="workspace-field">
                      邮箱
                      <input value={customerForm.contact_email} onChange={(event) => setCustomerForm((current) => ({ ...current, contact_email: event.target.value }))} />
                    </label>
                  </div>
                  <div className="button-row">
                    <button onClick={() => void handleCreateCustomer()} type="button">创建客户</button>
                  </div>
                </article>

                <article className="workspace-note-block">
                  <div className="section-header">
                    <h3>步骤 2：创建密钥对</h3>
                    <span className="badge badge-muted">L16</span>
                  </div>
                  <div className="workspace-form-grid">
                    <label className="workspace-field full-span">
                      密钥名称
                      <input value={keyName} onChange={(event) => setKeyName(event.target.value)} />
                    </label>
                  </div>
                  <div className="button-row">
                    <button onClick={() => void handleCreateKeyPair()} type="button">创建密钥对</button>
                  </div>
                </article>
              </div>

              <div className="workspace-stack">
                <article className="workspace-note-block">
                  <div className="section-header">
                    <h3>步骤 3：创建策略</h3>
                    <span className="badge badge-muted">L16</span>
                  </div>
                  <div className="workspace-form-grid">
                    <label className="workspace-field">
                      策略名称
                      <input value={policyForm.policy_name} onChange={(event) => setPolicyForm((current) => ({ ...current, policy_name: event.target.value }))} />
                    </label>
                    <label className="workspace-field">
                      客户
                      <select value={policyForm.customer_id} onChange={(event) => setPolicyForm((current) => ({ ...current, customer_id: event.target.value }))}>
                        {dashboard.customers.map((item) => (
                          <option key={item.customer_id} value={String(item.customer_id)}>
                            {item.customer_code}
                          </option>
                        ))}
                      </select>
                    </label>
                    <label className="workspace-field">
                      密钥
                      <select value={policyForm.key_pair_id} onChange={(event) => setPolicyForm((current) => ({ ...current, key_pair_id: event.target.value }))}>
                        {dashboard.keyPairs.map((item) => (
                          <option key={item.key_pair_id} value={String(item.key_pair_id)}>
                            {item.key_name}
                          </option>
                        ))}
                      </select>
                    </label>
                    <label className="workspace-field">
                      操作系统
                      <select value={policyForm.operating_system} onChange={(event) => setPolicyForm((current) => ({ ...current, operating_system: event.target.value }))}>
                        <option value="linux">linux</option>
                        <option value="windows">windows</option>
                        <option value="android">android</option>
                        <option value="ios">ios</option>
                      </select>
                    </label>
                    <label className="workspace-field">
                      最低系统版本
                      <input value={policyForm.min_operating_system_version} onChange={(event) => setPolicyForm((current) => ({ ...current, min_operating_system_version: event.target.value }))} />
                    </label>
                    <label className="workspace-field">
                      系统架构
                      <input value={policyForm.system_architecture} onChange={(event) => setPolicyForm((current) => ({ ...current, system_architecture: event.target.value }))} />
                    </label>
                    <label className="workspace-field">
                      应用名
                      <input value={policyForm.application_name} onChange={(event) => setPolicyForm((current) => ({ ...current, application_name: event.target.value }))} />
                    </label>
                    <label className="workspace-field full-span">
                      能力范围（逗号分隔）
                      <input value={policyForm.capability_scope} onChange={(event) => setPolicyForm((current) => ({ ...current, capability_scope: event.target.value }))} />
                    </label>
                    <label className="workspace-field full-span">
                      版本约束 JSON
                      <textarea rows={5} value={policyForm.version_constraints} onChange={(event) => setPolicyForm((current) => ({ ...current, version_constraints: event.target.value }))} />
                    </label>
                  </div>
                  <div className="button-row">
                    <button onClick={() => void handleCreatePolicy()} type="button">创建策略</button>
                    <button onClick={() => void handleIssueLicense()} type="button">按当前策略签发</button>
                  </div>
                </article>
              </div>
            </div>
          )}

          {activeTab === 'risk' && (
            <div className="workspace-panel-grid">
              <div className="workspace-stack">
                <article className="workspace-note-block">
                  <div className="section-header">
                    <h3>高风险操作工作台</h3>
                    <span className="badge badge-muted">L17</span>
                  </div>
                  <div className="workspace-list">
                    {dashboard.keyPairs.map((item) => (
                      <button
                        key={item.key_pair_id}
                        className={`workspace-list-item${selectedKeyPairId === item.key_pair_id ? ' active' : ''}`}
                        onClick={() => setSelectedKeyPairId(item.key_pair_id)}
                        type="button"
                      >
                        <strong>{item.key_name}</strong>
                        <div className="workspace-meta-row">
                          <span>版本 {item.rotation_version}</span>
                          <span>{item.algorithm}</span>
                          <span className={`status-pill ${statusTone(item.status)}`}>{item.status}</span>
                        </div>
                      </button>
                    ))}
                  </div>
                </article>
              </div>
              <div className="workspace-stack">
                <article className="workspace-note-block">
                  <h3>影响面与确认说明</h3>
                  {!selectedKeyPair ? (
                    <div className="workspace-empty">请选择密钥对查看影响范围。</div>
                  ) : (
                    <>
                      <div className="workspace-kpi-grid">
                        <article className="workspace-kpi-card">
                          <span>关联策略</span>
                          <strong>{dashboard.policies.filter((item) => item.key_pair_id === selectedKeyPair.key_pair_id).length}</strong>
                        </article>
                        <article className="workspace-kpi-card">
                          <span>关联签发</span>
                          <strong>{dashboard.issues.filter((item) => item.key_pair_id === selectedKeyPair.key_pair_id).length}</strong>
                        </article>
                        <article className="workspace-kpi-card">
                          <span>当前状态</span>
                          <strong>{selectedKeyPair.status}</strong>
                        </article>
                      </div>
                      <div className="workspace-form-grid" style={{ marginTop: 16 }}>
                        <label className="workspace-field">
                          轮转说明
                          <input value={rotateReason} onChange={(event) => setRotateReason(event.target.value)} />
                        </label>
                        <label className="workspace-field">
                          隔离说明
                          <input value={isolateReason} onChange={(event) => setIsolateReason(event.target.value)} />
                        </label>
                      </div>
                      <div className="button-row">
                        <button onClick={() => void handleRotateKeyPair()} type="button">执行轮转</button>
                        <button onClick={() => void handleIsolateKeyPair()} type="button">执行隔离</button>
                      </div>
                    </>
                  )}
                </article>
              </div>
            </div>
          )}

          {activeTab === 'validation' && (
            <div className="workspace-panel-grid">
              <div className="workspace-stack">
                <article className="workspace-note-block">
                  <div className="section-header">
                    <h3>签发记录与校验</h3>
                    <span className="badge badge-muted">L18-L19</span>
                  </div>
                  <div className="workspace-list">
                    {dashboard.issues.map((item) => (
                      <button
                        key={item.issue_record_id}
                        className={`workspace-list-item${selectedIssueId === item.issue_record_id ? ' active' : ''}`}
                        onClick={() => setSelectedIssueId(item.issue_record_id)}
                        type="button"
                      >
                        <strong>签发 #{item.issue_record_id}</strong>
                        <div className="workspace-meta-row">
                          <span>{item.customer_code}</span>
                          <span>{item.application_name}</span>
                          <span className={`status-pill ${statusTone(item.status)}`}>{item.status}</span>
                        </div>
                      </button>
                    ))}
                  </div>
                  <div className="workspace-form-grid" style={{ marginTop: 16 }}>
                    <label className="workspace-field">
                      指纹
                      <input value={validationForm.hardware_fingerprint} onChange={(event) => setValidationForm((current) => ({ ...current, hardware_fingerprint: event.target.value }))} />
                    </label>
                    <label className="workspace-field">
                      能力
                      <input value={validationForm.capability_name} onChange={(event) => setValidationForm((current) => ({ ...current, capability_name: event.target.value }))} />
                    </label>
                    <label className="workspace-field">
                      产品版本
                      <input value={validationForm.product_version} onChange={(event) => setValidationForm((current) => ({ ...current, product_version: event.target.value }))} />
                    </label>
                    <label className="workspace-field">
                      OS
                      <input value={validationForm.operating_system} onChange={(event) => setValidationForm((current) => ({ ...current, operating_system: event.target.value }))} />
                    </label>
                    <label className="workspace-field">
                      OS 版本
                      <input value={validationForm.operating_system_version} onChange={(event) => setValidationForm((current) => ({ ...current, operating_system_version: event.target.value }))} />
                    </label>
                    <label className="workspace-field">
                      架构
                      <input value={validationForm.system_architecture} onChange={(event) => setValidationForm((current) => ({ ...current, system_architecture: event.target.value }))} />
                    </label>
                  </div>
                  <div className="button-row">
                    <button onClick={() => void handleValidateIssue()} type="button">执行校验</button>
                  </div>
                </article>

                <article className="workspace-note-block">
                  <div className="section-header">
                    <h3>tool release 与诊断材料</h3>
                    <span className="badge badge-muted">L18</span>
                  </div>
                  <div className="button-row">
                    <button onClick={() => void handleSyncToolRelease()} type="button">同步默认工具版本</button>
                  </div>
                  <div className="workspace-list" style={{ marginTop: 16 }}>
                    {dashboard.toolReleases.map((item) => (
                      <div key={item.release_id} className="workspace-list-item">
                        <strong>{item.tool_name} / {item.version}</strong>
                        <div className="workspace-meta-row">
                          <span className={`status-pill ${statusTone(item.status)}`}>{item.status}</span>
                          <a href={toolExportUrl(item.release_id, 'archive')}>归档</a>
                          <a href={toolExportUrl(item.release_id, 'diagnostics')}>诊断</a>
                          <a href={toolExportUrl(item.release_id, 'vectors')}>向量</a>
                        </div>
                      </div>
                    ))}
                  </div>
                </article>
              </div>

              <div className="workspace-stack">
                <article className="workspace-note-block">
                  <h3>校验详情与下游动作</h3>
                  {lastValidationResult && (
                    <div className="workspace-kpi-grid">
                      <article className="workspace-kpi-card">
                        <span>结果码</span>
                        <strong>{lastValidationResult.code}</strong>
                      </article>
                      <article className="workspace-kpi-card">
                        <span>阶段</span>
                        <strong>{lastValidationResult.stage}</strong>
                      </article>
                      <article className="workspace-kpi-card">
                        <span>结论</span>
                        <strong>{lastValidationResult.valid ? '通过' : '拒绝'}</strong>
                      </article>
                    </div>
                  )}
                  {issueDetail ? (
                    <>
                      <div className="workspace-action-row">
                        <a className="workspace-action-chip" href={issueExportUrl(issueDetail.issue_record_id, 'bin')}>导出 license.bin</a>
                        <a className="workspace-action-chip" href={issueExportUrl(issueDetail.issue_record_id, 'pubkey')}>导出 pubkey.pem</a>
                        {workspace.nextModule && (
                          <a className="workspace-action-chip" href={workspace.nextModule.url}>
                            推进到 {workspace.nextModule.shortTitle}
                          </a>
                        )}
                      </div>
                      <pre className="workspace-code-block">{JSON.stringify(issueDetail.payload, null, 2)}</pre>
                    </>
                  ) : (
                    <div className="workspace-empty">请选择签发记录查看详细载荷。</div>
                  )}
                </article>

                <article className="workspace-note-block">
                  <h3>诊断契约摘要</h3>
                  <div className="workspace-kpi-grid">
                    <article className="workspace-kpi-card">
                      <span>字段数</span>
                      <strong>{Object.keys(dashboard.validationContract?.fields ?? {}).length}</strong>
                    </article>
                    <article className="workspace-kpi-card">
                      <span>结果码数</span>
                      <strong>{Object.keys(dashboard.validationContract?.code_catalog ?? {}).length}</strong>
                    </article>
                    <article className="workspace-kpi-card">
                      <span>测试向量</span>
                      <strong>{dashboard.validationVectors?.license_validation_vectors.length ?? 0}</strong>
                    </article>
                  </div>
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
