import { useEffect, useMemo, useState } from 'react'
import type { DashboardState } from '../types'
import { initialState, loadDashboard, runtimeAction, statusTone } from '../api'
import { buildControlChecklist, buildRevisionRiskItems, clampScore, scoreTone } from '../enterprise'

export default function ControlPage() {
  const [dashboard, setDashboard] = useState<DashboardState>(initialState)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [selectedRevisionId, setSelectedRevisionId] = useState<number | null>(null)
  const [actionMessage, setActionMessage] = useState<string | null>(null)

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
  const checklist = useMemo(() => buildControlChecklist(selectedRevision), [selectedRevision])
  const revisionScore = clampScore((checklist.filter((item) => item.done).length / Math.max(1, checklist.length)) * 100)
  const riskItems = useMemo(() => buildRevisionRiskItems(selectedRevision), [selectedRevision])

  async function handleRuntimeAction(action: 'reload' | 'rollback', targetRevisionId?: number): Promise<void> {
    try {
      setActionMessage(`正在执行 ${action}...`)
      await runtimeAction(action, targetRevisionId)
      setActionMessage(`${action} 已完成`)
      await refresh()
    } catch (loadError) {
      setActionMessage(loadError instanceof Error ? loadError.message : `${action} 失败`)
    }
  }

  return (
    <div className="page-container">
      <section className="panel">
        <div className="section-header">
          <div>
            <h2>高风险变更控制台</h2>
            <p>把 revision 列表升级为高风险变更工作台，在 reload / rollback 前先确认影响范围、授权状态和回滚关系。</p>
          </div>
          <span className="badge">P45-P49</span>
        </div>
        {loading && <p className="info-text">正在加载...</p>}
        {error && <p className="error-text">数据加载失败：{error}</p>}
        {actionMessage && <p className="success-text">{actionMessage}</p>}
        <div className="enterprise-hero-grid">
          <article className={`enterprise-score-card tone-${scoreTone(revisionScore)}`}>
            <span>当前变更准备度</span>
            <strong>{revisionScore}</strong>
            <p>根据 revision 选择、影响能力、授权状态和可决策状态四项门禁计算。</p>
          </article>
          <article className="enterprise-note-card">
            <strong>高风险提示</strong>
            <p>reload / rollback 是运行态高风险操作，必须先看当前 revision、目标 revision、影响能力和授权限制，再执行动作。</p>
          </article>
        </div>
      </section>

      <section className="panel">
        <div className="workspace-panel-grid">
          <div className="workspace-stack">
            <article className="workspace-note-block">
              <div className="section-header">
                <h3>revision 列表</h3>
                <span className="badge badge-muted">Control</span>
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
              <div className="section-header">
                <h3>变更门禁与建议</h3>
                {selectedRevision && <span className={`status-pill ${statusTone(selectedRevision.status)}`}>{selectedRevision.status}</span>}
              </div>
              {!selectedRevision ? (
                <div className="workspace-empty">请选择 revision 查看影响范围。</div>
              ) : (
                <>
                  <div className="enterprise-two-column">
                    <article className="enterprise-note-card">
                      <strong>变更门禁</strong>
                      <ul className="enterprise-checklist">
                        {checklist.map((item) => (
                          <li key={item.label} className={item.done ? 'done' : 'pending'}>
                            <span>{item.done ? '✓' : '•'}</span>
                            <div>
                              <strong>{item.label}</strong>
                              <p>{item.detail}</p>
                            </div>
                          </li>
                        ))}
                      </ul>
                    </article>
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
                  </div>
                  <div className="workspace-action-row">
                    <button className="action-button" onClick={() => void handleRuntimeAction('reload')} type="button">执行 reload</button>
                    <button className="action-button" onClick={() => void handleRuntimeAction('rollback', selectedRevision.revision_id)} type="button">回滚到该 revision</button>
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
            <strong>revision 影响范围</strong>
            <div className="workspace-kpi-grid">
              <article className="workspace-kpi-card">
                <span>能力数</span>
                <strong>{selectedRevision?.capability_names.length ?? 0}</strong>
              </article>
              <article className="workspace-kpi-card">
                <span>授权</span>
                <strong>{selectedRevision ? (selectedRevision.license_valid ? '有效' : '受限') : '-'}</strong>
              </article>
              <article className="workspace-kpi-card">
                <span>当前运行 revision</span>
                <strong>{dashboard.health?.runtime_revision_id ?? '-'}</strong>
              </article>
              <article className="workspace-kpi-card">
                <span>回滚来源</span>
                <strong>{selectedRevision?.rollback_of_revision_id ?? '-'}</strong>
              </article>
            </div>
            <pre className="workspace-code-block">{JSON.stringify(selectedRevision?.detail ?? {}, null, 2)}</pre>
          </article>
          <article className="enterprise-note-card">
            <strong>source summary / 审计联动</strong>
            <pre className="workspace-code-block">{JSON.stringify(selectedRevision?.source_summary ?? {}, null, 2)}</pre>
            <div className="workspace-table-wrap" style={{ marginTop: 16 }}>
              <table className="workspace-table">
                <thead>
                  <tr>
                    <th>时间</th>
                    <th>动作</th>
                    <th>状态</th>
                  </tr>
                </thead>
                <tbody>
                  {dashboard.operations.slice(0, 6).map((item) => (
                    <tr key={item.operation_id}>
                      <td>{item.created_at ?? '-'}</td>
                      <td>{item.action}</td>
                      <td>{item.status}</td>
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
