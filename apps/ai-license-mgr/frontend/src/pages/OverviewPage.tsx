import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { request, fetchList, statusTone } from '../api'
import type {
  CustomerItem,
  KeyPairItem,
  LicensePolicyItem,
  LicenseIssueItem,
  LicenseToolReleaseItem,
  AuditLogItem,
  ValidationContract,
  ValidationVectors,
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

export default function OverviewPage() {
  const navigate = useNavigate()
  const [dashboard, setDashboard] = useState<DashboardState>(initialState)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [selectedKeyPairId, setSelectedKeyPairId] = useState<number | null>(null)
  const [selectedIssueId, setSelectedIssueId] = useState<number | null>(null)

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
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : '加载失败')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    void loadDashboard()
  }, [])

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

  return (
    <div className="page-container">
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
                      navigate('/risk')
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
              <li>先在"连续签发工作台"完成客户、密钥、策略与签发闭环。</li>
              <li>再在"校验与工具工作台"验证平台字段、结果码与 tool bundle。</li>
              <li>最终把签发记录推进到 ai-builder 构建交付包。</li>
            </ul>
          </article>
        </div>
      </section>

      <section className="panel">
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
                      navigate('/validation')
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
      </section>
    </div>
  )
}
