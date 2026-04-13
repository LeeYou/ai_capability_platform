import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import type { CapabilityItem, AnnotationTaskItem, TrainingTaskItem, ModelArtifactItem, DashboardData } from '../types'
import { fetchList, statusTone, formatDateTime } from '../api'
import { buildOverviewInsights } from '../enterprise'

const initialData: DashboardData = {
  capabilities: [],
  annotationTasks: [],
  trainingTasks: [],
  modelArtifacts: [],
}

export default function OverviewPage() {
  const navigate = useNavigate()
  const [data, setData] = useState<DashboardData>(initialData)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    async function load() {
      try {
        const [capabilities, annotationTasks, trainingTasks, modelArtifacts] = await Promise.all([
          fetchList<CapabilityItem>('/api/v1/capabilities'),
          fetchList<AnnotationTaskItem>('/api/v1/annotation-tasks'),
          fetchList<TrainingTaskItem>('/api/v1/training-tasks'),
          fetchList<ModelArtifactItem>('/api/v1/models'),
        ])
        if (!cancelled) setData({ capabilities, annotationTasks, trainingTasks, modelArtifacts })
      } catch (loadError) {
        if (!cancelled) setError(loadError instanceof Error ? loadError.message : '加载数据失败')
      } finally {
        if (!cancelled) setLoading(false)
      }
    }
    void load()
    return () => { cancelled = true }
  }, [])

  const overviewCards = useMemo(
    () => [
      { title: '能力目录', value: data.capabilities.length, description: '已接入的任务类型能力与数据集绑定。' },
      { title: '标注任务', value: data.annotationTasks.length, description: '支持任务创建、单样本编辑与结果导出。' },
      { title: '训练任务', value: data.trainingTasks.length, description: '支持任务创建、执行、监控与模型登记。' },
      { title: '模型资产', value: data.modelArtifacts.length, description: '支持 manifest/runtime contract/delivery metadata。' },
    ],
    [data],
  )

  const pendingAnnotationTasks = data.annotationTasks.filter((item) => item.status !== 'completed').slice(0, 5)
  const latestTrainingTasks = data.trainingTasks.slice(0, 6)
  const latestModelArtifacts = data.modelArtifacts.slice(0, 4)
  const overviewInsights = useMemo(() => buildOverviewInsights(data), [data])

  return (
    <div className="page-container">
      <section className="panel">
        <div className="section-header">
          <div>
            <h2>首页概览</h2>
            <p>按“待标注 → 待训练 → 待送测”的企业级研发流转组织训练台首页，并补齐经营驾驶舱视角。</p>
          </div>
          <span className="badge">T17-T20</span>
        </div>
        {loading && <p className="info-text">正在加载研发工作台数据...</p>}
        {error && <p className="error-text">数据加载失败：{error}</p>}
        <div className="enterprise-hero-grid">
          <article className="enterprise-score-card">
            <span>整体交付就绪度</span>
            <strong>{overviewInsights.overallScore}</strong>
            <p>综合数据准入、标注交付、训练产出与模型就绪四个阶段门禁评分。</p>
          </article>
          <article className="enterprise-note-card">
            <strong>平台定位</strong>
            <p>当前训练台已经从“功能页面集合”升级为“企业级研发运营台”，重点强调闭环、准入、可交付和风险透明。</p>
          </article>
        </div>
        <div className="card-grid">
          {overviewCards.map((card) => (
            <article key={card.title} className="card">
              <h3>{card.title}</h3>
              <strong>{card.value}</strong>
              <p>{card.description}</p>
            </article>
          ))}
        </div>
        <div className="workspace-action-row">
          <button className="action-button" onClick={() => navigate('/annotation')} type="button">新建标注任务</button>
          <button className="action-button" onClick={() => navigate('/training')} type="button">新建训练任务</button>
          <button className="action-button" onClick={() => navigate('/model')} type="button">查看模型资产</button>
          <button className="action-button" onClick={() => navigate('/capabilities')} type="button">管理能力目录</button>
        </div>
        <div className="enterprise-stage-grid">
          {overviewInsights.stageCards.map((item) => (
            <article key={item.title} className={`enterprise-stage-card tone-${item.tone}`}>
              <span>{item.title}</span>
              <strong>{item.score}</strong>
              <p>{item.detail}</p>
              <small>当前就绪对象：{item.count}</small>
            </article>
          ))}
        </div>
      </section>

      <section className="panel">
        <div className="workspace-summary-grid">
          <article className="workspace-summary-card">
            <h3>待处理标注任务</h3>
            <div className="workspace-list">
              {pendingAnnotationTasks.map((item) => (
                <button
                  key={item.task_id}
                  className="workspace-list-item"
                  onClick={() => navigate('/annotation')}
                  type="button"
                >
                  <strong>{item.task_name}</strong>
                  <div className="workspace-meta-row">
                    <span>{item.capability_name}</span>
                    <span>{item.labeled_count}/{item.sample_total}</span>
                    <span className={`status-pill ${statusTone(item.status)}`}>{item.status}</span>
                  </div>
                </button>
              ))}
            </div>
          </article>
          <article className="workspace-summary-card">
            <h3>待送测模型</h3>
            <div className="workspace-list">
              {latestModelArtifacts.map((item) => (
                <button
                  key={item.artifact_id}
                  className="workspace-list-item"
                  onClick={() => navigate('/model')}
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
          </article>
        </div>
      </section>

      <section className="panel">
        <div className="section-header">
          <div>
            <h3>风险与推荐动作</h3>
            <p>让训练台具备面向负责人/运营值守的状态总结能力。</p>
          </div>
        </div>
        <div className="enterprise-two-column">
          <div className="enterprise-stack">
            {overviewInsights.risks.map((item) => (
              <article key={item.title} className={`enterprise-note-card tone-${item.tone}`}>
                <strong>{item.title}</strong>
                <p>{item.detail}</p>
              </article>
            ))}
          </div>
          <article className="enterprise-note-card">
            <strong>建议动作</strong>
            <ul className="enterprise-list">
              {overviewInsights.actions.map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ul>
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
                      <th>任务类型</th>
                      <th>数据集状态</th>
                      <th>最近更新时间</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.capabilities.map((item) => (
                      <tr key={item.capability_name}>
                        <td>{item.display_name}</td>
                        <td>{item.task_type}</td>
                        <td><span className={`status-pill ${statusTone(item.dataset_status)}`}>{item.dataset_status}</span></td>
                        <td>{formatDateTime(item.updated_at)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </article>
          </div>
          <div className="workspace-stack">
            <article className="workspace-note-block">
              <h3>最近训练任务</h3>
              <div className="workspace-table-wrap">
                <table className="workspace-table">
                  <thead>
                    <tr>
                      <th>任务</th>
                      <th>能力</th>
                      <th>状态</th>
                      <th>创建时间</th>
                    </tr>
                  </thead>
                  <tbody>
                    {latestTrainingTasks.map((item) => (
                      <tr key={item.task_id}>
                        <td>{item.task_name}</td>
                        <td>{item.capability_name}</td>
                        <td><span className={`status-pill ${statusTone(item.status)}`}>{item.status}</span></td>
                        <td>{formatDateTime(item.created_at)}</td>
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
