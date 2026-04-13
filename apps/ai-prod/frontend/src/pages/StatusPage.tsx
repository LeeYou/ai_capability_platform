import { useEffect, useMemo, useState } from 'react'
import type { DashboardState } from '../types'
import { initialState, loadDashboard } from '../api'
import { buildStatusRiskItems } from '../enterprise'

export default function StatusPage() {
  const [dashboard, setDashboard] = useState<DashboardState>(initialState)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  async function refresh(): Promise<void> {
    try {
      setLoading(true)
      setError(null)
      const data = await loadDashboard()
      setDashboard(data)
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : '加载失败')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    void refresh()
  }, [])

  const riskItems = useMemo(() => buildStatusRiskItems(dashboard), [dashboard])

  return (
    <div className="page-container">
      <section className="panel">
        <div className="section-header">
          <div>
            <h2>运行资产视图</h2>
            <p>以能力、授权、revision 和资源池为核心，展示 ai-prod 当前真实运行资产，而不是只看单点状态。</p>
          </div>
          <button className="action-button" onClick={() => void refresh()} type="button">刷新</button>
        </div>
        {loading && <p className="info-text">正在加载运行状态...</p>}
        {error && <p className="error-text">数据加载失败：{error}</p>}
        <div className="enterprise-hero-grid">
          <article className="enterprise-score-card tone-neutral">
            <span>当前运行 revision</span>
            <strong>{dashboard.health?.runtime_revision_id ?? '-'}</strong>
            <p>所有运行能力、授权状态和资源池利用率都应围绕当前 revision 做确认。</p>
          </article>
          <article className="enterprise-note-card">
            <strong>运行态势</strong>
            <div className="enterprise-stack">
              {riskItems.map((item) => (
                <div key={item.title} className={`enterprise-inline-card tone-${item.tone}`}>
                  <strong>{item.title}</strong>
                  <p>{item.detail}</p>
                </div>
              ))}
            </div>
          </article>
        </div>
      </section>

      <section className="panel">
        <div className="workspace-summary-grid">
          <article className="workspace-summary-card">
            <h3>服务状态</h3>
            <strong>{dashboard.health?.status ?? '-'}</strong>
            <p>能力数：{dashboard.health?.capability_count ?? 0}</p>
          </article>
          <article className="workspace-summary-card">
            <h3>License 状态</h3>
            <strong>{dashboard.licenseStatus?.code ?? '-'}</strong>
            <p>{dashboard.licenseStatus?.result ?? '-'}</p>
          </article>
          <article className="workspace-summary-card">
            <h3>资源池</h3>
            <strong>{dashboard.runtimeMetrics?.pool_summary.total_pool_slots ?? '-'}</strong>
            <p>idle {dashboard.runtimeMetrics?.pool_summary.idle_pool_slots ?? '-'} / busy {dashboard.runtimeMetrics?.pool_summary.busy_pool_slots ?? '-'}</p>
          </article>
        </div>
      </section>

      <section className="panel">
        <div className="enterprise-two-column">
          <article className="enterprise-note-card">
            <strong>能力运行资产</strong>
            <div className="workspace-table-wrap">
              <table className="workspace-table">
                <thead>
                  <tr>
                    <th>能力名称</th>
                    <th>模型版本</th>
                    <th>后端</th>
                    <th>设备模式</th>
                    <th>池大小</th>
                    <th>活动来源</th>
                    <th>Revision</th>
                  </tr>
                </thead>
                <tbody>
                  {dashboard.capabilities.map((item) => (
                    <tr key={item.capability_name}>
                      <td>{item.capability_name}</td>
                      <td>{item.model_version}</td>
                      <td>{item.backend_type}</td>
                      <td>{item.device_mode}</td>
                      <td>{item.pool_size}</td>
                      <td>{item.active_source}</td>
                      <td>{item.revision_id ?? '-'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </article>
          <article className="enterprise-note-card">
            <strong>授权与资源池概况</strong>
            <div className="workspace-kpi-grid">
              <article className="workspace-kpi-card">
                <span>结果</span>
                <strong>{dashboard.licenseStatus?.result ?? '-'}</strong>
              </article>
              <article className="workspace-kpi-card">
                <span>阶段</span>
                <strong>{dashboard.licenseStatus?.stage ?? '-'}</strong>
              </article>
              <article className="workspace-kpi-card">
                <span>客户代码</span>
                <strong>{dashboard.licenseStatus?.customer_code ?? '-'}</strong>
              </article>
              <article className="workspace-kpi-card">
                <span>利用率</span>
                <strong>{dashboard.runtimeMetrics ? `${(dashboard.runtimeMetrics.pool_summary.utilization_ratio * 100).toFixed(1)}%` : '-'}</strong>
              </article>
            </div>
            <pre className="workspace-code-block">{JSON.stringify(dashboard.licenseStatus?.details ?? {}, null, 2)}</pre>
          </article>
        </div>
      </section>
    </div>
  )
}
