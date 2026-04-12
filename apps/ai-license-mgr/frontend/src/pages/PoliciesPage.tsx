import { useEffect, useState } from 'react'
import { fetchList, statusTone } from '../api'
import type { LicensePolicyItem, LicenseIssueItem } from '../types'

export default function PoliciesPage() {
  const [policies, setPolicies] = useState<LicensePolicyItem[]>([])
  const [issues, setIssues] = useState<LicenseIssueItem[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    async function loadData(): Promise<void> {
      setLoading(true)
      setError(null)
      try {
        const [pol, iss] = await Promise.all([
          fetchList<LicensePolicyItem>('/api/v1/license-policies'),
          fetchList<LicenseIssueItem>('/api/v1/license-issues'),
        ])
        setPolicies(pol)
        setIssues(iss)
      } catch (loadError) {
        setError(loadError instanceof Error ? loadError.message : '加载失败')
      } finally {
        setLoading(false)
      }
    }
    void loadData()
  }, [])

  return (
    <div className="page-container">
      <section className="panel">
        <div className="section-header">
          <div>
            <h2>策略与签发记录</h2>
            <p>浏览授权策略和签发记录，查看签发状态与过期时间。</p>
          </div>
          <span className="badge">POL</span>
        </div>
        {loading && <p className="info-text">正在加载数据...</p>}
        {error && <p className="error-text">数据加载失败：{error}</p>}
      </section>

      <section className="panel">
        <h3>授权策略</h3>
        {policies.length === 0 && !loading ? (
          <div className="workspace-empty">暂无授权策略。</div>
        ) : (
          <div className="workspace-table-wrap">
            <table className="workspace-table">
              <thead>
                <tr>
                  <th>策略名称</th>
                  <th>客户代码</th>
                  <th>密钥名称</th>
                  <th>操作系统</th>
                  <th>能力范围</th>
                  <th>生效时间</th>
                  <th>过期时间</th>
                  <th>状态</th>
                </tr>
              </thead>
              <tbody>
                {policies.map((item) => (
                  <tr key={item.policy_id}>
                    <td>{item.policy_name}</td>
                    <td>{item.customer_code}</td>
                    <td>{item.key_name}</td>
                    <td>{item.operating_system}</td>
                    <td>{item.capability_scope.join(', ')}</td>
                    <td>{item.start_at_cst}</td>
                    <td>{item.expire_at_cst}</td>
                    <td><span className={`status-pill ${statusTone(item.status)}`}>{item.status}</span></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      <section className="panel">
        <h3>签发记录</h3>
        {issues.length === 0 && !loading ? (
          <div className="workspace-empty">暂无签发记录。</div>
        ) : (
          <div className="workspace-table-wrap">
            <table className="workspace-table">
              <thead>
                <tr>
                  <th>签发ID</th>
                  <th>客户代码</th>
                  <th>密钥名称</th>
                  <th>应用名称</th>
                  <th>操作系统</th>
                  <th>能力范围</th>
                  <th>签发时间</th>
                  <th>校验结果</th>
                  <th>状态</th>
                </tr>
              </thead>
              <tbody>
                {issues.map((item) => (
                  <tr key={item.issue_record_id}>
                    <td>{item.issue_record_id}</td>
                    <td>{item.customer_code}</td>
                    <td>{item.key_name}</td>
                    <td>{item.application_name}</td>
                    <td>{item.operating_system}</td>
                    <td>{item.capability_scope.join(', ')}</td>
                    <td>{item.issued_at_cst}</td>
                    <td>{item.last_validation_result ?? '-'}</td>
                    <td><span className={`status-pill ${statusTone(item.status)}`}>{item.status}</span></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  )
}
