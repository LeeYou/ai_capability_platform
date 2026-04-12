import { useEffect, useState } from 'react'
import type { DashboardState } from '../types'
import { initialState, loadDashboard } from '../api'

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

  return (
    <div className="page-container">
      <section className="panel">
        <div className="section-header">
          <div>
            <h2>运行状态</h2>
            <p>查看当前已加载能力的运行状态、模型版本、资源池与 License 信息。</p>
          </div>
          <button className="action-btn" onClick={() => void refresh()} type="button">刷新</button>
        </div>
        {loading && <p className="info-text">正在加载运行状态...</p>}
        {error && <p className="error-text">数据加载失败：{error}</p>}

        <div className="card-grid">
          <article className="card">
            <h3>服务状态</h3>
            <strong className={dashboard.health?.status === 'ok' ? 'status-good' : 'status-danger'}>{dashboard.health?.status ?? '-'}</strong>
            <p>当前服务运行状态。</p>
          </article>
          <article className="card">
            <h3>加载能力数</h3>
            <strong>{dashboard.health?.capability_count ?? 0}</strong>
            <p>已加载的推理能力总数。</p>
          </article>
          <article className="card">
            <h3>当前 Revision</h3>
            <strong>{dashboard.health?.runtime_revision_id ?? '-'}</strong>
            <p>当前活动的运行版本号。</p>
          </article>
          <article className="card">
            <h3>License 状态</h3>
            <strong className={dashboard.health?.license_valid ? 'status-good' : 'status-danger'}>{dashboard.health?.license_valid ? '有效' : '无效/受限'}</strong>
            <p>当前 License 授权状态。</p>
          </article>
        </div>
      </section>

      <section className="panel">
        <div className="workspace-panel-grid">
          <div className="workspace-stack">
            <article className="workspace-note-block">
              <h3>能力运行详情</h3>
              {dashboard.capabilities.length === 0 ? (
                <p className="workspace-empty">当前没有已加载的能力。</p>
              ) : (
                <div className="workspace-table-wrap">
                  <table className="workspace-table">
                    <thead>
                      <tr>
                        <th>能力名称</th>
                        <th>模型版本</th>
                        <th>后端类型</th>
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
              )}
            </article>
          </div>
          <div className="workspace-stack">
            <article className="workspace-note-block">
              <h3>License 详情</h3>
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
              {dashboard.licenseStatus && (
                <div className="workspace-kpi-grid" style={{ marginTop: '0.75rem' }}>
                  <article className="workspace-kpi-card">
                    <span>客户代码</span>
                    <strong>{dashboard.licenseStatus.customer_code ?? '-'}</strong>
                  </article>
                  <article className="workspace-kpi-card">
                    <span>能力范围</span>
                    <strong>{dashboard.licenseStatus.capability_scope?.join(', ') || '-'}</strong>
                  </article>
                  <article className="workspace-kpi-card">
                    <span>诊断版本</span>
                    <strong>{dashboard.licenseStatus.diagnostics_version ?? '-'}</strong>
                  </article>
                </div>
              )}
            </article>
            <article className="workspace-note-block">
              <h3>资源池概况</h3>
              <div className="workspace-kpi-grid">
                <article className="workspace-kpi-card">
                  <span>利用率</span>
                  <strong>{dashboard.runtimeMetrics ? `${(dashboard.runtimeMetrics.pool_summary.utilization_ratio * 100).toFixed(1)}%` : '-'}</strong>
                </article>
                <article className="workspace-kpi-card">
                  <span>总池位</span>
                  <strong>{dashboard.runtimeMetrics?.pool_summary.total_pool_slots ?? '-'}</strong>
                </article>
                <article className="workspace-kpi-card">
                  <span>空闲池位</span>
                  <strong>{dashboard.runtimeMetrics?.pool_summary.idle_pool_slots ?? '-'}</strong>
                </article>
              </div>
            </article>
          </div>
        </div>
      </section>
    </div>
  )
}
