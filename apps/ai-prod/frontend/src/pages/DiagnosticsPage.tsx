import { useEffect, useMemo, useState } from 'react'
import type { DashboardState } from '../types'
import { initialState, loadDashboard, statusTone } from '../api'
import { buildAuditRiskItems, buildDiagnosticsRiskItems, maxEndpointP95 } from '../enterprise'

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

  const selectedRevision = useMemo(
    () => dashboard.revisions.find((item) => item.revision_id === selectedRevisionId) ?? null,
    [dashboard.revisions, selectedRevisionId],
  )
  const riskItems = useMemo(() => buildDiagnosticsRiskItems(dashboard), [dashboard])
  const auditSummary = useMemo(() => buildAuditRiskItems(dashboard.auditLogs), [dashboard.auditLogs])

  return (
    <div className="page-container">
      <section className="panel">
        <div className="section-header">
          <div>
            <h2>监控诊断工作台</h2>
            <p>把 metrics、revision source summary、admission 失败明细和审计留痕收口成可行动诊断视图。</p>
          </div>
          <span className="badge">P45-P49</span>
        </div>
        {loading && <p className="info-text">正在加载...</p>}
        {error && <p className="error-text">数据加载失败：{error}</p>}
        <div className="enterprise-hero-grid">
          <article className="enterprise-score-card tone-neutral">
            <span>P95 峰值</span>
            <strong>{maxEndpointP95(dashboard.runtimeMetrics)}</strong>
            <p>优先关注排队超时、繁忙拒绝和高时延端点，而不是只看原始 metrics JSON。</p>
          </article>
          <article className="enterprise-note-card">
            <strong>诊断摘要</strong>
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
        <div className="workspace-panel-grid">
          <div className="workspace-stack">
            <article className="workspace-note-block">
              <div className="section-header">
                <h3>revision 诊断视图</h3>
                <span className="badge badge-muted">Diagnostics</span>
              </div>
              <div className="workspace-list">
                {dashboard.revisions.map((item) => (
                  <button key={item.revision_id} className={`workspace-list-item${selectedRevisionId === item.revision_id ? ' active' : ''}`} onClick={() => setSelectedRevisionId(item.revision_id)} type="button">
                    <strong>revision #{item.revision_id}</strong>
                    <div className="workspace-meta-row">
                      <span>{item.action}</span>
                      <span>{item.capability_names.join(', ') || '无能力'}</span>
                      <span className={`status-pill ${statusTone(item.status)}`}>{item.status}</span>
                    </div>
                  </button>
                ))}
              </div>
            </article>
          </div>
          <div className="workspace-stack">
            <article className="workspace-note-block">
              <strong>source summary / admission</strong>
              <pre className="workspace-code-block">{JSON.stringify(selectedRevision?.source_summary ?? {}, null, 2)}</pre>
            </article>
            <article className="workspace-note-block">
              <strong>运行时 metrics 摘要</strong>
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
                  <span>最大排队</span>
                  <strong>{dashboard.runtimeMetrics?.request_summary.max_queue_wait_ms ?? 0} ms</strong>
                </article>
              </div>
              <pre className="workspace-code-block">{JSON.stringify(dashboard.runtimeMetrics ?? {}, null, 2)}</pre>
            </article>
          </div>
        </div>
      </section>

      <section className="panel">
        <div className="enterprise-two-column">
          <article className="enterprise-note-card">
            <strong>审计留痕摘要</strong>
            <div className="enterprise-stack">
              {auditSummary.map((item) => (
                <div key={item.title} className={`enterprise-inline-card tone-${item.tone}`}>
                  <strong>{item.title}</strong>
                  <p>{item.detail}</p>
                </div>
              ))}
            </div>
          </article>
          <article className="enterprise-note-card">
            <strong>最近审计记录</strong>
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
      </section>
    </div>
  )
}
