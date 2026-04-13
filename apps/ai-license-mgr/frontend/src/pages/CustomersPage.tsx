import { useEffect, useMemo, useState } from 'react'
import { request, fetchList, statusTone } from '../api'
import type { CustomerItem, CustomerFormState, LicenseIssueItem, LicensePolicyItem } from '../types'
import { buildCustomerPortfolio, clampScore, scoreTone } from '../enterprise'

const initialForm: CustomerFormState = {
  customer_code: '',
  customer_name: '',
  contact_name: '',
  contact_email: '',
}

export default function CustomersPage() {
  const [customers, setCustomers] = useState<CustomerItem[]>([])
  const [policies, setPolicies] = useState<LicensePolicyItem[]>([])
  const [issues, setIssues] = useState<LicenseIssueItem[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [form, setForm] = useState<CustomerFormState>(initialForm)
  const [actionMessage, setActionMessage] = useState<string | null>(null)
  const [query, setQuery] = useState('')

  async function loadData(): Promise<void> {
    setLoading(true)
    setError(null)
    try {
      const [customerItems, policyItems, issueItems] = await Promise.all([
        fetchList<CustomerItem>('/api/v1/customers'),
        fetchList<LicensePolicyItem>('/api/v1/license-policies'),
        fetchList<LicenseIssueItem>('/api/v1/license-issues'),
      ])
      setCustomers(customerItems)
      setPolicies(policyItems)
      setIssues(issueItems)
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : '加载失败')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    void loadData()
  }, [])

  async function handleCreateCustomer(): Promise<void> {
    try {
      setActionMessage('正在创建客户...')
      await request<CustomerItem>('/api/v1/customers', {
        method: 'POST',
        body: JSON.stringify(form),
      })
      setForm(initialForm)
      setActionMessage('客户已创建')
      await loadData()
    } catch (loadError) {
      setActionMessage(loadError instanceof Error ? loadError.message : '创建客户失败')
    }
  }

  const portfolio = useMemo(() => buildCustomerPortfolio(customers, policies, issues), [customers, issues, policies])
  const filteredPortfolio = portfolio.filter((item) => {
    const normalized = query.trim().toLowerCase()
    if (!normalized) return true
    return item.customer.customer_code.toLowerCase().includes(normalized) || item.customer.customer_name.toLowerCase().includes(normalized)
  })
  const customerScore = clampScore((portfolio.filter((item) => item.issueCount > 0).length / Math.max(1, portfolio.length)) * 100)

  return (
    <div className="page-container">
      <section className="panel">
        <div className="section-header">
          <div>
            <h2>客户组合视图</h2>
            <p>把客户从基础资料页升级为“客户 + 策略 + 签发 + 应用”的授权组合视图。</p>
          </div>
          <span className="badge">L20-L24</span>
        </div>
        {loading && <p className="info-text">正在加载数据...</p>}
        {error && <p className="error-text">数据加载失败：{error}</p>}
        {actionMessage && <p className="success-text">{actionMessage}</p>}
        <div className="enterprise-hero-grid">
          <article className={`enterprise-score-card tone-${scoreTone(customerScore)}`}>
            <span>客户资产沉淀度</span>
            <strong>{customerScore}</strong>
            <p>根据客户是否已沉淀策略 / 签发资产计算。</p>
          </article>
          <article className="enterprise-note-card">
            <strong>客户搜索</strong>
            <label className="workspace-field enterprise-search-field">
              搜索客户
              <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="按客户代码或客户名称搜索" />
            </label>
          </article>
        </div>
      </section>

      <section className="panel">
        <div className="workspace-panel-grid">
          <div className="workspace-stack">
            <article className="workspace-note-block">
              <h3>新建客户</h3>
              <div className="workspace-form-grid">
                <label className="workspace-field">
                  客户代码
                  <input value={form.customer_code} onChange={(event) => setForm((current) => ({ ...current, customer_code: event.target.value }))} />
                </label>
                <label className="workspace-field">
                  客户名称
                  <input value={form.customer_name} onChange={(event) => setForm((current) => ({ ...current, customer_name: event.target.value }))} />
                </label>
                <label className="workspace-field">
                  联系人
                  <input value={form.contact_name} onChange={(event) => setForm((current) => ({ ...current, contact_name: event.target.value }))} />
                </label>
                <label className="workspace-field">
                  联系邮箱
                  <input value={form.contact_email} onChange={(event) => setForm((current) => ({ ...current, contact_email: event.target.value }))} />
                </label>
              </div>
              <div className="workspace-action-row">
                <button className="action-button" onClick={() => void handleCreateCustomer()} type="button">创建客户</button>
              </div>
            </article>
          </div>
          <div className="workspace-stack">
            <article className="workspace-note-block">
              <h3>客户资产卡片</h3>
              <div className="capability-card-grid">
                {filteredPortfolio.map((item) => (
                  <article key={item.customer.customer_id} className="capability-card">
                    <div className="section-header">
                      <div>
                        <h3>{item.customer.customer_name}</h3>
                        <p>{item.customer.customer_code}</p>
                      </div>
                      <span className={`status-pill ${statusTone(item.customer.status)}`}>{item.customer.status}</span>
                    </div>
                    <div className="workspace-meta-column">
                      <span>联系人：{item.customer.contact_name ?? '-'}</span>
                      <span>邮箱：{item.customer.contact_email ?? '-'}</span>
                      <span>策略数：{item.policyCount}</span>
                      <span>签发数：{item.issueCount}</span>
                      <span>有效签发：{item.activeIssueCount}</span>
                    </div>
                    <div className="enterprise-inline-card tone-neutral">
                      <strong>应用列表</strong>
                      <p>{item.applications.join(', ') || '尚未沉淀应用'}</p>
                    </div>
                  </article>
                ))}
              </div>
            </article>
          </div>
        </div>
      </section>
    </div>
  )
}
