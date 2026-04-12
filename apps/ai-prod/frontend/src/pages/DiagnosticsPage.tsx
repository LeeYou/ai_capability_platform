import { useEffect, useState } from 'react'
import type { DashboardState } from '../types'
import { initialState, loadDashboard, statusTone } from '../api'

export default function DiagnosticsPage() {
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

  const selectedRevision = dashboard.revisions.find((item) => item.revision_id === selectedRevisionId) ?? null

  return (
    <div className="page-container">
      <section className="panel">
        {loading && <p className="info-text">正在加载...</p>}
        {error && <p className="error-text">数据加载失败：{error}</p>}
        <div className="workspace-panel-grid">
          <div className="workspace-stack">
            <article className="workspace-note-block">
              <div className="section-header">
                <h3>监控与诊断</h3>
                <span className="badge badge-muted">P44</span>
              </div>
              <div className="workspace-kpi-grid">
                <article className="workspace-kpi-card">
                  <span>池利用率</span>
                  <strong>{Math.round((dashboard.runtimeMetrics?.pool_summary.utilization_ratio ?? 0) * 100)}%</strong>
                </article>
                <article className="workspace-kpi-card">
                  <span>平均排队</span>
                  <strong>{dashboard.runtimeMetrics?.request_summary.avg_queue_wait_ms ?? 0} ms</strong>
                </article>
                <article className="workspace-kpi-card">
                  <span>P95 最大值</span>
                  <strong>{Math.max(...Object.values(dashboard.runtimeMetrics?.endpoint_metrics ?? {}).map((item) => item.p95_latency_ms), 0)} ms</strong>
                </article>
              </div>
              <pre className="workspace-code-block">{JSON.stringify(dashboard.runtimeMetrics ?? {}, null, 2)}</pre>
            </article>
          </div>
          <div className="workspace-stack">
            <article className="workspace-note-block">
              <h3>revision 诊断与审计</h3>
              {selectedRevision && <pre className="workspace-code-block">{JSON.stringify(selectedRevision.source_summary, null, 2)}</pre>}
              <div className="workspace-table-wrap" style={{ marginTop: 16 }}>
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
