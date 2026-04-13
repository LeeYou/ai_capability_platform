import { useEffect, useMemo, useState } from 'react'
import { fetchList, statusTone } from '../api'
import type { KeyPairItem, LicensePolicyItem, LicenseIssueItem } from '../types'
import { buildPolicyRiskItems, clampScore, scoreTone } from '../enterprise'

export default function PoliciesPage() {
  const [policies, setPolicies] = useState<LicensePolicyItem[]>([])
  const [issues, setIssues] = useState<LicenseIssueItem[]>([])
  const [keyPairs, setKeyPairs] = useState<KeyPairItem[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [selectedPolicyId, setSelectedPolicyId] = useState<number | null>(null)

  useEffect(() => {
    async function loadData(): Promise<void> {
      setLoading(true)
      setError(null)
      try {
        const [pol, iss, kp] = await Promise.all([
          fetchList<LicensePolicyItem>('/api/v1/license-policies'),
          fetchList<LicenseIssueItem>('/api/v1/license-issues'),
          fetchList<KeyPairItem>('/api/v1/key-pairs'),
        ])
        setPolicies(pol)
        setIssues(iss)
        setKeyPairs(kp)
        setSelectedPolicyId((current) => current ?? pol[0]?.policy_id ?? null)
      } catch (loadError) {
        setError(loadError instanceof Error ? loadError.message : '加载失败')
      } finally {
        setLoading(false)
      }
    }
    void loadData()
  }, [])

  const selectedPolicy = policies.find((item) => item.policy_id === selectedPolicyId) ?? null
  const relatedIssues = issues.filter((item) => item.policy_id === selectedPolicyId)
  const riskItems = useMemo(() => (selectedPolicy ? buildPolicyRiskItems(selectedPolicy, issues, keyPairs) : []), [issues, keyPairs, selectedPolicy])
  const policyScore = clampScore((policies.filter((item) => item.status === 'active' || item.status === 'issued').length / Math.max(1, policies.length)) * 100)

  return (
    <div className="page-container">
      <section className="panel">
        <div className="section-header">
          <div>
            <h2>策略与签发联动台</h2>
            <p>把策略页从纯表格升级为“策略风险、环境约束、签发联动、到期视图”的授权资产面板。</p>
          </div>
          <span className="badge">L20-L24</span>
        </div>
        {loading && <p className="info-text">正在加载数据...</p>}
        {error && <p className="error-text">数据加载失败：{error}</p>}
        <div className="enterprise-hero-grid">
          <article className={`enterprise-score-card tone-${scoreTone(policyScore)}`}>
            <span>策略池活跃度</span>
            <strong>{policyScore}</strong>
            <p>根据 active / issued 状态策略占比计算。</p>
          </article>
          <article className="enterprise-note-card">
            <strong>页面定位</strong>
            <p>在同一页面中查看策略环境约束、密钥状态、签发沉淀与到期风险，减少策略与签发脱节。</p>
          </article>
        </div>
      </section>

      <section className="panel">
        <div className="workspace-panel-grid">
          <div className="workspace-stack">
            <article className="workspace-note-block">
              <h3>策略列表</h3>
              <div className="workspace-list">
                {policies.map((item) => (
                  <button key={item.policy_id} className={`workspace-list-item${selectedPolicyId === item.policy_id ? ' active' : ''}`} onClick={() => setSelectedPolicyId(item.policy_id)} type="button">
                    <strong>{item.policy_name}</strong>
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
              <h3>策略详情</h3>
              {!selectedPolicy ? (
                <div className="workspace-empty">请选择策略查看详情。</div>
              ) : (
                <>
                  <div className="workspace-table-wrap">
                    <table className="workspace-table">
                      <tbody>
                        <tr><th>策略</th><td>{selectedPolicy.policy_name}</td><th>客户</th><td>{selectedPolicy.customer_code}</td></tr>
                        <tr><th>密钥</th><td>{selectedPolicy.key_name}</td><th>应用</th><td>{selectedPolicy.application_name}</td></tr>
                        <tr><th>操作系统</th><td>{selectedPolicy.operating_system}</td><th>最低版本</th><td>{selectedPolicy.min_operating_system_version ?? '-'}</td></tr>
                        <tr><th>系统架构</th><td>{selectedPolicy.system_architecture ?? '-'}</td><th>状态</th><td>{selectedPolicy.status}</td></tr>
                        <tr><th>能力范围</th><td colSpan={3}>{selectedPolicy.capability_scope.join(', ') || '*'}</td></tr>
                      </tbody>
                    </table>
                  </div>
                  <div className="enterprise-two-column">
                    <article className="enterprise-note-card">
                      <strong>风险摘要</strong>
                      <div className="enterprise-stack">
                        {riskItems.map((item) => (
                          <div key={item.title} className={`enterprise-inline-card tone-${item.tone}`}>
                            <strong>{item.title}</strong>
                            <p>{item.detail}</p>
                          </div>
                        ))}
                      </div>
                    </article>
                    <article className="enterprise-note-card">
                      <strong>版本约束</strong>
                      <pre className="workspace-code-block">{JSON.stringify(selectedPolicy.version_constraints, null, 2)}</pre>
                    </article>
                  </div>
                </>
              )}
            </article>
          </div>
        </div>
      </section>

      <section className="panel">
        <div className="enterprise-two-column">
          <article className="enterprise-note-card">
            <strong>关联签发记录</strong>
            <div className="workspace-table-wrap">
              <table className="workspace-table">
                <thead>
                  <tr>
                    <th>签发ID</th>
                    <th>客户</th>
                    <th>应用</th>
                    <th>最近校验</th>
                    <th>状态</th>
                  </tr>
                </thead>
                <tbody>
                  {relatedIssues.map((item) => (
                    <tr key={item.issue_record_id}>
                      <td>{item.issue_record_id}</td>
                      <td>{item.customer_code}</td>
                      <td>{item.application_name}</td>
                      <td>{item.last_validation_code ?? '-'}</td>
                      <td><span className={`status-pill ${statusTone(item.status)}`}>{item.status}</span></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </article>
          <article className="enterprise-note-card">
            <strong>全局签发记录</strong>
            <div className="workspace-table-wrap">
              <table className="workspace-table">
                <thead>
                  <tr>
                    <th>签发ID</th>
                    <th>策略</th>
                    <th>应用</th>
                    <th>状态</th>
                  </tr>
                </thead>
                <tbody>
                  {issues.map((item) => (
                    <tr key={item.issue_record_id}>
                      <td>{item.issue_record_id}</td>
                      <td>{item.policy_id}</td>
                      <td>{item.application_name}</td>
                      <td><span className={`status-pill ${statusTone(item.status)}`}>{item.status}</span></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </article>
        </div>
      </section>
    </div>
  )
}
