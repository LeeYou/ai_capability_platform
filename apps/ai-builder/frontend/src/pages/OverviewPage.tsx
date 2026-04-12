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

  const overviewCards = useMemo(
    () => [
      { title: '平台矩阵', value: dashboard.platforms.length, description: '统一管理 Linux / Windows / JNI / 多架构交付目标。' },
      { title: '可构建模型', value: dashboard.catalog.models.length, description: '从 ai-train 同步真实模型与 manifest。' },
      { title: '可用授权', value: dashboard.catalog.license_issues.length, description: '与 ai-license-mgr 对齐后的签发记录。' },
      { title: '构建队列', value: dashboard.buildTasks.length, description: '当前 delivery_package / SDK / 动态库构建任务总数。' },
    ],
    [dashboard],
  )

  const failedTasks = useMemo(
    () => dashboard.buildTasks.filter((item) => item.status === 'failed').slice(0, 4),
    [dashboard.buildTasks],
  )

  const readyModels = useMemo(
    () => dashboard.catalog.models.slice(0, 4),
    [dashboard.catalog.models],
  )

  function handleModelClick(item: { capability_name: string; model_version: string }) {
    const params = new URLSearchParams({
      capability_name: item.capability_name,
      model_version: item.model_version,
    })
    navigate(`/wizard?${params.toString()}`)
  }

  return (
    <div className="page-container">
      <section className="panel">
        <div className="section-header">
          <div>
            <h2>首页概览</h2>
            <p>优先把模型、授权、平台矩阵与失败任务放到同一视图下统一决策。</p>
          </div>
          <span className="badge">B15-B18</span>
        </div>
        {loading && <p className="info-text">正在加载交付构建数据...</p>}
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
            <h3>优先构建模型</h3>
            {readyModels.length === 0 ? (
              <div className="workspace-empty">当前没有可构建模型，请先在 ai-train / ai-test 完成上游动作。</div>
            ) : (
              <div className="workspace-list">
                {readyModels.map((item) => (
                  <button
                    key={`${item.capability_name}-${item.model_version}`}
                    className="workspace-list-item"
                    onClick={() => handleModelClick(item)}
                    type="button"
                  >
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
          <article className="workspace-summary-card">
            <h3>失败任务回看</h3>
            {failedTasks.length === 0 ? (
              <div className="workspace-empty">当前暂无失败构建任务。</div>
            ) : (
              <div className="workspace-list">
                {failedTasks.map((item) => (
                  <button
                    key={item.task_id}
                    className="workspace-list-item"
                    onClick={() => navigate(`/tasks?taskId=${item.task_id}`)}
                    type="button"
                  >
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
            <h3>当前设计原则</h3>
            <ul>
              <li>构建任务创建要向导化，不再要求工程师手工理解所有平台参数。</li>
              <li>产物详情必须展示 provenance、校验结果与下载动作。</li>
              <li>构建完成后明确下一步动作：去 ai-prod 做生产验收。</li>
            </ul>
          </article>
        </div>
      </section>

      <section className="panel">
        <div className="workspace-panel-grid">
          <div className="workspace-stack">
            <article className="workspace-note-block">
              <h3>平台矩阵</h3>
              <div className="workspace-table-wrap">
                <table className="workspace-table">
                  <thead>
                    <tr>
                      <th>目标</th>
                      <th>平台</th>
                      <th>格式</th>
                      <th>工具链</th>
                    </tr>
                  </thead>
                  <tbody>
                    {dashboard.platforms.map((item) => (
                      <tr key={item.target_name}>
                        <td>{item.target_name}</td>
                        <td>{item.os_name}/{item.arch_name}</td>
                        <td>{item.artifact_format}</td>
                        <td>{item.toolchain_name}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </article>
          </div>
          <div className="workspace-stack">
            <article className="workspace-note-block">
              <h3>最近构建队列</h3>
              <div className="workspace-list">
                {dashboard.buildTasks.slice(0, 5).map((item) => (
                  <button
                    key={item.task_id}
                    className="workspace-list-item"
                    onClick={() => navigate(`/tasks?taskId=${item.task_id}`)}
                    type="button"
                  >
                    <strong>任务 #{item.task_id}</strong>
                    <div className="workspace-meta-row">
                      <span>{item.capability_name}</span>
                      <span>{item.model_version}</span>
                      <span className={`status-pill ${statusTone(item.status)}`}>{item.status}</span>
                    </div>
                  </button>
                ))}
              </div>
            </article>
          </div>
        </div>
      </section>
    </div>
  )
}
