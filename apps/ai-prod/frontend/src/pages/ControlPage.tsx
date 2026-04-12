import { useEffect, useState } from 'react'
import type { DashboardState } from '../types'
import { initialState, loadDashboard, runtimeAction, statusTone } from '../api'

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

  const selectedRevision = dashboard.revisions.find((item) => item.revision_id === selectedRevisionId) ?? null

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
        {loading && <p className="info-text">正在加载...</p>}
        {error && <p className="error-text">数据加载失败：{error}</p>}
        {actionMessage && <p className="success-text">{actionMessage}</p>}
        <div className="workspace-panel-grid">
          <div className="workspace-stack">
            <article className="workspace-note-block">
              <div className="section-header">
                <h3>revision 列表</h3>
                <span className="badge badge-muted">P43</span>
              </div>
              <div className="workspace-list">
                {dashboard.revisions.map((item) => (
                  <button
                    key={item.revision_id}
                    className={`workspace-list-item${selectedRevisionId === item.revision_id ? ' active' : ''}`}
                    onClick={() => setSelectedRevisionId(item.revision_id)}
                    type="button"
                  >
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
                <h3>受控变更</h3>
                {selectedRevision && <span className={`status-pill ${statusTone(selectedRevision.status)}`}>{selectedRevision.status}</span>}
              </div>
              {!selectedRevision ? (
                <div className="workspace-empty">请选择 revision 查看影响范围。</div>
              ) : (
                <>
                  <div className="workspace-kpi-grid">
                    <article className="workspace-kpi-card">
                      <span>能力数</span>
                      <strong>{selectedRevision.capability_names.length}</strong>
                    </article>
                    <article className="workspace-kpi-card">
                      <span>license</span>
                      <strong>{selectedRevision.license_valid ? '有效' : '受限'}</strong>
                    </article>
                  </div>
                  <div className="workspace-action-row">
                    <button className="action-button" onClick={() => void handleRuntimeAction('reload')} type="button">执行 reload</button>
                    <button className="action-button" onClick={() => void handleRuntimeAction('rollback', selectedRevision.revision_id)} type="button">回滚到该 revision</button>
                  </div>
                  <pre className="workspace-code-block">{JSON.stringify(selectedRevision.detail, null, 2)}</pre>
                </>
              )}
            </article>
          </div>
        </div>
      </section>
    </div>
  )
}
