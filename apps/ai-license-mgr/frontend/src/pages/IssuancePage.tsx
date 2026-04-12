import { useEffect, useState } from 'react'
import { request, fetchList } from '../api'
import type {
  CustomerItem,
  KeyPairItem,
  LicensePolicyItem,
  LicenseIssueItem,
  LicenseIssueDetail,
  CustomerFormState,
  PolicyFormState,
  DashboardState,
} from '../types'

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

export default function IssuancePage() {
  const [dashboard, setDashboard] = useState<DashboardState>(initialState)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [actionMessage, setActionMessage] = useState<string | null>(null)
  const [customerForm, setCustomerForm] = useState<CustomerFormState>(initialCustomerForm)
  const [keyName, setKeyName] = useState('agile-star-key')
  const [policyForm, setPolicyForm] = useState<PolicyFormState>(initialPolicyForm)
  const [selectedPolicyId, setSelectedPolicyId] = useState<number | null>(null)

  async function loadDashboard(): Promise<void> {
    setLoading(true)
    setError(null)
    try {
      const [customers, keyPairs, policies, issues] = await Promise.all([
        fetchList<CustomerItem>('/api/v1/customers'),
        fetchList<KeyPairItem>('/api/v1/key-pairs'),
        fetchList<LicensePolicyItem>('/api/v1/license-policies'),
        fetchList<LicenseIssueItem>('/api/v1/license-issues'),
      ])
      setDashboard((current) => ({ ...current, customers, keyPairs, policies, issues }))
      setSelectedPolicyId((current) => current ?? policies[0]?.policy_id ?? null)
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
      setActionMessage(`签发记录 #${created.issue_record_id} 已生成`)
      await loadDashboard()
    } catch (loadError) {
      setActionMessage(loadError instanceof Error ? loadError.message : '签发失败')
    }
  }

  return (
    <div className="page-container">
      <section className="panel">
        <div className="section-header">
          <div>
            <h2>连续签发工作台</h2>
            <p>围绕连续签发组织企业级授权流程。</p>
          </div>
        </div>
        {loading && <p className="info-text">正在加载数据...</p>}
        {error && <p className="error-text">数据加载失败：{error}</p>}
        {actionMessage && <p className="success-text">{actionMessage}</p>}

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
      </section>
    </div>
  )
}
