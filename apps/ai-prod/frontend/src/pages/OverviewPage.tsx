import { useEffect, useMemo, useState } from 'react'
import type { DashboardState } from '../types'
import { initialState, loadDashboard, statusTone } from '../api'

export default function OverviewPage() {
  const [dashboard, setDashboard] = useState<DashboardState>(initialState)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [selectedRevisionId, setSelectedRevisionId] = useState<number | null>(null)

  async function refresh(): Promise<void> {
    try {
      setLoading(true)
      setError(null)
      const data = await loadDashboard()
      setDashboard(data)
      setSelectedRevisionId((current) => current ?? data.revisions[0]?.revision_id ?? null)
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : '加载失败')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    void refresh()
  }, [])

  const overviewCards = useMemo(
    () => [
      { title: '能力数量', value: dashboard.health?.capability_count ?? 0, description: '当前运行态可提供服务的能力数量。' },
      { title: '活动 revision', value: dashboard.health?.runtime_revision_id ?? 0, description: '当前线上启用的运行版本。' },
      { title: '累计请求', value: dashboard.runtimeMetrics?.request_summary.capability_total_requests ?? 0, description: '聚合能力请求总量。' },
      { title: '队列中请求', value: dashboard.runtimeMetrics?.request_summary.queued_request_count ?? 0, description: '当前排队中的运行请求。' },
    ],
    [dashboard],
  )

  return (
    <div className="page-container">
      <section className="panel">
        <div className="section-header">
          <div>
            <h2>首页概览</h2>
            <p>优先展示 revision、license、排队风险与异常能力，而不是纯信息堆叠。</p>
          </div>
          <span className="badge">P41-P44</span>
        </div>
        {loading && <p className="info-text">正在加载运行控制台...</p>}
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
            <h3>当前风险</h3>
            <ul>
              <li>License：{dashboard.licenseStatus?.valid ? '有效' : `受限 / ${dashboard.licenseStatus?.code ?? 'unknown'}`}</li>
              <li>队列超时：{dashboard.runtimeMetrics?.request_summary.queue_timeout_count ?? 0}</li>
              <li>繁忙拒绝：{dashboard.runtimeMetrics?.request_summary.busy_reject_count ?? 0}</li>
            </ul>
          </article>
          <article className="workspace-summary-card">
            <h3>最近变更</h3>
            <div className="workspace-list">
              {dashboard.operations.slice(0, 4).map((item) => (
                <button
                  key={item.operation_id}
                  className={`workspace-list-item${selectedRevisionId === item.revision_id ? ' active' : ''}`}
                  onClick={() => setSelectedRevisionId(item.revision_id)}
                  type="button"
                >
                  <strong>{item.action} / #{item.operation_id}</strong>
                  <div className="workspace-meta-row">
                    <span>{item.created_at ?? '-'}</span>
                    <span className={`status-pill ${statusTone(item.status)}`}>{item.status}</span>
                  </div>
                </button>
              ))}
            </div>
          </article>
        </div>
      </section>

      <section className="panel">
        <div className="workspace-panel-grid">
          <div className="workspace-stack">
            <article className="workspace-note-block">
              <h3>能力目录</h3>
              <div className="workspace-table-wrap">
                <table className="workspace-table">
                  <thead>
                    <tr>
                      <th>能力</th>
                      <th>版本</th>
                      <th>设备</th>
                      <th>revision</th>
                    </tr>
                  </thead>
                  <tbody>
                    {dashboard.capabilities.map((item) => (
                      <tr key={item.capability_name}>
                        <td>{item.capability_name}</td>
                        <td>{item.model_version}</td>
                        <td>{item.device_mode}</td>
                        <td>{item.revision_id ?? '-'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </article>
          </div>
          <div className="workspace-stack">
            <article className="workspace-note-block">
              <h3>License 状态</h3>
              <div className="workspace-kpi-grid">
                <article className="workspace-kpi-card">
                  <span>结果</span>
                  <strong>{dashboard.licenseStatus?.result ?? '-'}</strong>
                </article>
                <article className="workspace-kpi-card">
                  <span>结果码</span>
                  <strong>{dashboard.licenseStatus?.code ?? '-'}</strong>
                </article>
                <article className="workspace-kpi-card">
                  <span>阶段</span>
                  <strong>{dashboard.licenseStatus?.stage ?? '-'}</strong>
                </article>
              </div>
            </article>
          </div>
        </div>
      </section>
    </div>
  )
}
