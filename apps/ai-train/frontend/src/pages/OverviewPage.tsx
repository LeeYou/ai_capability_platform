import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import type { CapabilityItem, AnnotationTaskItem, TrainingTaskItem, ModelArtifactItem, DashboardData } from '../types'
import { fetchList, statusTone } from '../api'

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
    setLoading(true)
    setError(null)
    Promise.all([
      fetchList<CapabilityItem>('/api/v1/capabilities'),
      fetchList<AnnotationTaskItem>('/api/v1/annotation-tasks'),
      fetchList<TrainingTaskItem>('/api/v1/training-tasks'),
      fetchList<ModelArtifactItem>('/api/v1/models'),
    ])
      .then(([capabilities, annotationTasks, trainingTasks, modelArtifacts]) => {
        setData({ capabilities, annotationTasks, trainingTasks, modelArtifacts })
      })
      .catch((loadError) => {
        setError(loadError instanceof Error ? loadError.message : '加载数据失败')
      })
      .finally(() => {
        setLoading(false)
      })
  }, [])

  const overviewCards = useMemo(
    () => [
      { title: '能力目录', value: data.capabilities.length, description: '已接入的任务类型能力与数据集绑定。' },
      { title: '标注任务', value: data.annotationTasks.length, description: '样本级编辑、批量保存与提交的入口。' },
      { title: '训练任务', value: data.trainingTasks.length, description: '训练执行、日志与结果摘要的统一视图。' },
      { title: '模型资产', value: data.modelArtifacts.length, description: '可直接送测的模型卡片与 manifest 契约。' },
    ],
    [data],
  )

  return (
    <div className="page-container">
      <section className="panel">
        <div className="section-header">
          <div>
            <h2>首页概览</h2>
            <p>围绕待标注、待训练、待送测对象组织研发首页。</p>
          </div>
          <span className="badge">T17-T20</span>
        </div>
        {loading && <p className="info-text">正在加载研发工作台数据...</p>}
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
            <h3>待处理标注任务</h3>
            <div className="workspace-list">
              {data.annotationTasks.slice(0, 4).map((item) => (
                <button
                  key={item.task_id}
                  className="workspace-list-item"
                  onClick={() => {
                    navigate('/annotation')
                  }}
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
              {data.modelArtifacts.slice(0, 4).map((item) => (
                <button
                  key={item.artifact_id}
                  className="workspace-list-item"
                  onClick={() => {
                    navigate('/model')
                  }}
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
                      <th>数据集</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.capabilities.map((item) => (
                      <tr key={item.capability_name}>
                        <td>{item.display_name}</td>
                        <td>{item.task_type}</td>
                        <td>{item.dataset_status}</td>
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
              <div className="workspace-list">
                {data.trainingTasks.slice(0, 5).map((item) => (
                  <button
                    key={item.task_id}
                    className="workspace-list-item"
                    onClick={() => {
                      navigate('/training')
                    }}
                    type="button"
                  >
                    <strong>{item.task_name}</strong>
                    <div className="workspace-meta-row">
                      <span>{item.capability_name}</span>
                      <span>{item.framework}</span>
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
