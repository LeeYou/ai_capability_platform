import { useEffect, useState } from 'react'
import { request, fetchList, statusTone } from '../api'
import type { CustomerItem, CustomerFormState } from '../types'

const initialForm: CustomerFormState = {
  customer_code: '',
  customer_name: '',
  contact_name: '',
  contact_email: '',
}

export default function CustomersPage() {
  const [customers, setCustomers] = useState<CustomerItem[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [form, setForm] = useState<CustomerFormState>(initialForm)
  const [actionMessage, setActionMessage] = useState<string | null>(null)

  async function loadCustomers(): Promise<void> {
    setLoading(true)
    setError(null)
    try {
      const items = await fetchList<CustomerItem>('/api/v1/customers')
      setCustomers(items)
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : '加载失败')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    void loadCustomers()
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
      await loadCustomers()
    } catch (loadError) {
      setActionMessage(loadError instanceof Error ? loadError.message : '创建客户失败')
    }
  }

  return (
    <div className="page-container">
      <section className="panel">
        <div className="section-header">
          <div>
            <h2>客户管理</h2>
            <p>管理授权客户信息，包括客户代码、名称和联系人。</p>
          </div>
          <span className="badge">CUS</span>
        </div>
        {loading && <p className="info-text">正在加载数据...</p>}
        {error && <p className="error-text">数据加载失败：{error}</p>}
        {actionMessage && <p className="success-text">{actionMessage}</p>}

        <div className="workspace-panel-grid">
          <div className="workspace-stack">
            <article className="workspace-note-block">
              <h3>新建客户</h3>
              <div className="workspace-field">
                <label className="workspace-label">客户代码</label>
                <input
                  className="workspace-input"
                  placeholder="客户代码，如 acme-corp"
                  value={form.customer_code}
                  onChange={(event) => setForm((current) => ({ ...current, customer_code: event.target.value }))}
                />
              </div>
              <div className="workspace-field">
                <label className="workspace-label">客户名称</label>
                <input
                  className="workspace-input"
                  placeholder="客户名称"
                  value={form.customer_name}
                  onChange={(event) => setForm((current) => ({ ...current, customer_name: event.target.value }))}
                />
              </div>
              <div className="workspace-field">
                <label className="workspace-label">联系人</label>
                <input
                  className="workspace-input"
                  placeholder="联系人姓名"
                  value={form.contact_name}
                  onChange={(event) => setForm((current) => ({ ...current, contact_name: event.target.value }))}
                />
              </div>
              <div className="workspace-field">
                <label className="workspace-label">联系邮箱</label>
                <input
                  className="workspace-input"
                  placeholder="联系邮箱"
                  value={form.contact_email}
                  onChange={(event) => setForm((current) => ({ ...current, contact_email: event.target.value }))}
                />
              </div>
              <div className="button-row">
                <button className="action-btn" onClick={() => void handleCreateCustomer()} type="button">创建客户</button>
              </div>
            </article>
          </div>

          <div className="workspace-stack">
            <article className="workspace-note-block">
              <h3>客户列表</h3>
              {customers.length === 0 && !loading ? (
                <div className="workspace-empty">暂无客户记录。</div>
              ) : (
                <div className="workspace-table-wrap">
                  <table className="workspace-table">
                    <thead>
                      <tr>
                        <th>客户代码</th>
                        <th>客户名称</th>
                        <th>联系人</th>
                        <th>联系邮箱</th>
                        <th>状态</th>
                      </tr>
                    </thead>
                    <tbody>
                      {customers.map((item) => (
                        <tr key={item.customer_id}>
                          <td>{item.customer_code}</td>
                          <td>{item.customer_name}</td>
                          <td>{item.contact_name ?? '-'}</td>
                          <td>{item.contact_email ?? '-'}</td>
                          <td><span className={`status-pill ${statusTone(item.status)}`}>{item.status}</span></td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </article>
          </div>
        </div>
      </section>
    </div>
  )
}
