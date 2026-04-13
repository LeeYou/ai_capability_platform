import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import type { DashboardState } from '../types'
import { initialState, loadDashboard, statusTone } from '../api'
import { buildAuditRiskItems, buildOverviewInsights } from '../enterprise'

export default function OverviewPage() {
  const navigate = useNavigate()
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

  const insights = useMemo(() => buildOverviewInsights(dashboard), [dashboard])
  const auditSummary = useMemo(() => buildAuditRiskItems(dashboard.auditLogs), [dashboard.auditLogs])

  return (
    <div className="page-container">
      <section className="panel">
        <div className="section-header">
          <div>
            <h2>内部运行中枢</h2>
            <p>把服务健康、授权状态、排队风险、最近变更和重点能力收口到同一首页，用于运行确认和变更前决策。</p>
          </div>
          <span className="badge">P45-P49</span>
        </div>
        {loading && <p className="info-text">正在加载运行控制台...</p>}
        {error && <p className="error-text">数据加载失败：{error}</p>}
        <div className="enterprise-hero-grid">
          <article className={`enterprise-score-card tone-${insights.stageCards[0]?.tone ?? 'neutral'}`}>
            <span>运行健康度</span>
            <strong>{insights.overallScore}</strong>
            <p>综合服务可用性、授权状态、队列健康和版本闭环四段信号计算。</p>
          </article>
          <article className="enterprise-note-card">
            <strong>中枢定位</strong>
            <p>首页不是静态状态墙，而是告诉研发、QA、交付和运维当前是否可验证、可变更、可验收。</p>
            <div className="workspace-action-row">
              <button className="action-button" onClick={() => navigate('/verify')} type="button">去在线验证</button>
              <button className="action-button" onClick={() => navigate('/control')} type="button">去版本控制</button>
              <button className="action-button" onClick={() => navigate('/diagnostics')} type="button">去监控诊断</button>
            </div>
          </article>
        </div>
        <div className="enterprise-stage-grid">
          {insights.stageCards.map((item) => (
            <article key={item.title} className={`enterprise-stage-card tone-${item.tone}`}>
              <span>{item.title}</span>
              <strong>{item.score}</strong>
              <p>{item.detail}</p>
              <small>当前对象：{item.count}</small>
            </article>
          ))}
        </div>
      </section>

      <section className="panel">
        <div className="enterprise-two-column">
          <article className="enterprise-note-card">
            <strong>当前阻塞</strong>
            <div className="enterprise-stack">
              {insights.blockers.map((item) => (
                <div key={item.title} className={`enterprise-inline-card tone-${item.tone}`}>
                  <strong>{item.title}</strong>
                  <p>{item.detail}</p>
                </div>
              ))}
            </div>
          </article>
          <article className="enterprise-note-card">
            <strong>推荐动作</strong>
            <ul>
              {insights.actions.map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ul>
          </article>
        </div>
      </section>

      <section className="panel">
        <div className="workspace-summary-grid">
          <article className="workspace-summary-card">
            <h3>最近变更</h3>
            <div className="workspace-list">
              {insights.latestOperations.map((item) => (
                <button key={item.operation_id} className="workspace-list-item" onClick={() => navigate('/control')} type="button">
                  <strong>{item.action} / #{item.operation_id}</strong>
                  <div className="workspace-meta-row">
                    <span>{item.created_at ?? '-'}</span>
                    <span>{item.revision_id != null ? `revision ${item.revision_id}` : '无 revision'}</span>
                    <span className={`status-pill ${statusTone(item.status)}`}>{item.status}</span>
                  </div>
                </button>
              ))}
            </div>
          </article>
          <article className="workspace-summary-card">
            <h3>重点能力</h3>
            <div className="workspace-list">
              {insights.highlightedCapabilities.map((item) => (
                <button key={item.capability_name} className="workspace-list-item" onClick={() => navigate('/status')} type="button">
                  <strong>{item.capability_name}</strong>
                  <div className="workspace-meta-row">
                    <span>{item.model_version}</span>
                    <span>{item.device_mode}</span>
                    <span>pool {item.pool_size}</span>
                  </div>
                </button>
              ))}
            </div>
          </article>
          <article className="workspace-summary-card">
            <h3>审计留痕</h3>
            <div className="enterprise-stack">
              {auditSummary.map((item) => (
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
        <div className="enterprise-two-column">
          <article className="enterprise-note-card">
            <strong>在线能力目录</strong>
            <div className="workspace-table-wrap">
              <table className="workspace-table">
                <thead>
                  <tr>
                    <th>能力</th>
                    <th>版本</th>
                    <th>设备</th>
                    <th>来源</th>
                    <th>revision</th>
                  </tr>
                </thead>
                <tbody>
                  {dashboard.capabilities.map((item) => (
                    <tr key={item.capability_name}>
                      <td>{item.capability_name}</td>
                      <td>{item.model_version}</td>
                      <td>{item.device_mode}</td>
                      <td>{item.active_source}</td>
                      <td>{item.revision_id ?? '-'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
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
