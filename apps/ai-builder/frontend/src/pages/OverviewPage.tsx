import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { request, fetchList, statusTone } from '../api'
import type {
  PlatformTargetItem,
  CatalogResponse,
  BuildTaskItem,
  AuditLogItem,
  DashboardState,
} from '../types'
import { initialDashboardState } from '../types'
import { buildAuditRiskItems, buildOverviewInsights } from '../enterprise'

export default function OverviewPage() {
  const navigate = useNavigate()
  const [dashboard, setDashboard] = useState<DashboardState>(initialDashboardState)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  async function loadDashboard(): Promise<void> {
    setLoading(true)
    setError(null)
    try {
      const [platforms, catalog, buildTasks, auditLogs] = await Promise.all([
        fetchList<PlatformTargetItem>('/api/v1/platform-targets'),
        request<CatalogResponse>('/api/v1/catalog'),
        fetchList<BuildTaskItem>('/api/v1/build-tasks'),
        fetchList<AuditLogItem>('/api/v1/audit-logs?limit=8'),
      ])
      setDashboard({ platforms, catalog, buildTasks, auditLogs })
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : '加载失败')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    void loadDashboard()
  }, [])

  const insights = useMemo(() => buildOverviewInsights(dashboard), [dashboard])
  const auditSummary = useMemo(() => buildAuditRiskItems(dashboard.auditLogs), [dashboard.auditLogs])
  const failedTasks = dashboard.buildTasks.filter((item) => item.status === 'failed').slice(0, 4)
  const readyModels = dashboard.catalog.models.filter((item) => item.status === 'ready').slice(0, 5)

  function handleModelClick(capabilityName: string, modelVersion: string) {
    const params = new URLSearchParams({ capability_name: capabilityName, model_version: modelVersion })
    navigate(`/wizard?${params.toString()}`)
  }

  return (
    <div className="page-container">
      <section className="panel">
        <div className="section-header">
          <div>
            <h2>交付构建中枢</h2>
            <p>把模型、授权、平台矩阵、失败任务、最近交付和审计留痕收口到首页，形成可决策的构建中枢。</p>
          </div>
          <span className="badge">B19-B22</span>
        </div>
        {loading && <p className="info-text">正在加载交付构建数据...</p>}
        {error && <p className="error-text">数据加载失败：{error}</p>}
        <div className="enterprise-hero-grid">
          <article className={`enterprise-score-card tone-${insights.stageCards[0]?.tone ?? 'neutral'}`}>
            <span>交付链路健康度</span>
            <strong>{insights.overallScore}</strong>
            <p>综合模型、授权、构建闭环和平台矩阵四段链路计算。</p>
          </article>
          <article className="enterprise-note-card">
            <strong>首页定位</strong>
            <p>首页不只是“统计卡片”，而是告诉交付工程师先构哪个模型、补哪条授权、处理哪个失败任务、完成后去哪里验收。</p>
            <div className="workspace-action-row">
              <button className="action-button" onClick={() => navigate('/wizard')} type="button">进入构建向导</button>
              <button className="action-button" onClick={() => navigate('/tasks')} type="button">处理任务队列</button>
              <button className="action-button" onClick={() => navigate('/package')} type="button">查看交付包</button>
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
            <strong>优先构建模型</strong>
            {readyModels.length === 0 ? (
              <div className="workspace-empty">当前没有可构建模型，请先完成上游训练与测试动作。</div>
            ) : (
              <div className="workspace-list">
                {readyModels.map((item) => (
                  <button key={`${item.capability_name}-${item.model_version}`} className="workspace-list-item" onClick={() => handleModelClick(item.capability_name, item.model_version)} type="button">
                    <strong>{item.capability_name}</strong>
                    <div className="workspace-meta-row">
                      <span>{item.model_version}</span>
                      <span>{item.backend_type}</span>
                      <span className={`status-pill ${statusTone(item.status)}`}>{item.status}</span>
                    </div>
                  </button>
                ))}
              </div>
            )}
          </article>
          <article className="enterprise-note-card">
            <strong>交付阻塞</strong>
            <div className="enterprise-stack">
              {insights.blockers.map((item) => (
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
            <h3>失败任务回看</h3>
            {failedTasks.length === 0 ? (
              <div className="workspace-empty">当前暂无失败构建任务。</div>
            ) : (
              <div className="workspace-list">
                {failedTasks.map((item) => (
                  <button key={item.task_id} className="workspace-list-item" onClick={() => navigate(`/tasks?taskId=${item.task_id}`)} type="button">
                    <strong>任务 #{item.task_id}</strong>
                    <div className="workspace-meta-row">
                      <span>{item.capability_name}</span>
                      <span>{item.model_version}</span>
                      <span className={`status-pill ${statusTone(item.status)}`}>{item.status}</span>
                    </div>
                  </button>
                ))}
              </div>
            )}
          </article>
          <article className="workspace-summary-card">
            <h3>最近完成交付</h3>
            <div className="workspace-list">
              {insights.latestCompletedTasks.map((item) => (
                <button key={item.task_id} className="workspace-list-item" onClick={() => navigate(`/package?taskId=${item.task_id}`)} type="button">
                  <strong>任务 #{item.task_id}</strong>
                  <div className="workspace-meta-row">
                    <span>{item.capability_name}</span>
                    <span>{item.completed_at ?? '-'}</span>
                    <span className={`status-pill ${statusTone(item.status)}`}>{item.status}</span>
                  </div>
                </button>
              ))}
            </div>
          </article>
          <article className="workspace-summary-card">
            <h3>当前推荐动作</h3>
            <ul>
              {insights.actions.map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ul>
          </article>
        </div>
      </section>

      <section className="panel">
        <div className="enterprise-two-column">
          <article className="enterprise-note-card">
            <strong>平台矩阵</strong>
            <div className="workspace-table-wrap">
              <table className="workspace-table">
                <thead>
                  <tr>
                    <th>目标</th>
                    <th>平台</th>
                    <th>格式</th>
                    <th>JNI</th>
                  </tr>
                </thead>
                <tbody>
                  {dashboard.platforms.map((item) => (
                    <tr key={item.target_name}>
                      <td>{item.target_name}</td>
                      <td>{item.os_name}/{item.arch_name}</td>
                      <td>{item.artifact_format}</td>
                      <td>{item.supports_jni ? '支持' : '关闭'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </article>
          <article className="enterprise-note-card">
            <strong>最近审计留痕</strong>
            <div className="enterprise-stack">
              {auditSummary.map((item) => (
                <div key={item.title} className={`enterprise-inline-card tone-${item.tone}`}>
                  <strong>{item.title}</strong>
                  <p>{item.detail}</p>
                </div>
              ))}
            </div>
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
      </section>
    </div>
  )
}
