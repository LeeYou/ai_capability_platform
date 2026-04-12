import { useEffect, useState } from 'react'
import type { TrainingTaskItem } from '../types'
import { request, fetchList, statusTone } from '../api'

export default function TrainingPage() {
  const [trainingTasks, setTrainingTasks] = useState<TrainingTaskItem[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [selectedTrainingTaskId, setSelectedTrainingTaskId] = useState<number | null>(null)
  const [trainingDetail, setTrainingDetail] = useState<TrainingTaskItem | null>(null)
  const [actionMessage, setActionMessage] = useState<string | null>(null)

  async function loadTrainingTasks(): Promise<void> {
    setLoading(true)
    setError(null)
    try {
      const tasks = await fetchList<TrainingTaskItem>('/api/v1/training-tasks')
      setTrainingTasks(tasks)
      setSelectedTrainingTaskId((current) => current ?? tasks[0]?.task_id ?? null)
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : '加载数据失败')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    void loadTrainingTasks()
  }, [])

  useEffect(() => {
    if (selectedTrainingTaskId == null) {
      setTrainingDetail(null)
      return
    }
    void request<TrainingTaskItem>(`/api/v1/training-tasks/${selectedTrainingTaskId}`).then(setTrainingDetail)
  }, [selectedTrainingTaskId])

  async function handleTrainingAction(path: 'prepare' | 'execute'): Promise<void> {
    if (selectedTrainingTaskId == null) return
    try {
      await request(`/api/v1/training-tasks/${selectedTrainingTaskId}/${path}`, {
        method: 'POST',
      })
      setActionMessage(path === 'prepare' ? '训练工作区准备完成' : '训练执行已完成')
      await loadTrainingTasks()
    } catch (loadError) {
      setActionMessage(loadError instanceof Error ? loadError.message : '训练动作失败')
    }
  }

  return (
    <div className="page-container">
      {loading && <p className="info-text">正在加载训练任务数据...</p>}
      {error && <p className="error-text">数据加载失败：{error}</p>}
      {actionMessage && <p className="success-text">{actionMessage}</p>}
      <div className="workspace-panel-grid">
        <div className="workspace-stack">
          <article className="workspace-note-block">
            <div className="section-header">
              <h3>训练任务列表</h3>
              <span className="badge badge-muted">T18</span>
            </div>
            <div className="workspace-list">
              {trainingTasks.map((item) => (
                <button
                  key={item.task_id}
                  className={`workspace-list-item${selectedTrainingTaskId === item.task_id ? ' active' : ''}`}
                  onClick={() => setSelectedTrainingTaskId(item.task_id)}
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
        <div className="workspace-stack">
          <article className="workspace-note-block">
            <div className="section-header">
              <h3>训练执行视图</h3>
              {trainingDetail && <span className={`status-pill ${statusTone(trainingDetail.status)}`}>{trainingDetail.status}</span>}
            </div>
            {!trainingDetail ? (
              <div className="workspace-empty">请选择训练任务查看日志与阶段状态。</div>
            ) : (
              <>
                <div className="workspace-kpi-grid">
                  <article className="workspace-kpi-card">
                    <span>重试次数</span>
                    <strong>{trainingDetail.retry_count}</strong>
                  </article>
                  <article className="workspace-kpi-card">
                    <span>后端</span>
                    <strong>{trainingDetail.backend_type}</strong>
                  </article>
                  <article className="workspace-kpi-card">
                    <span>任务类型</span>
                    <strong>{trainingDetail.task_type}</strong>
                  </article>
                </div>
                <div className="workspace-action-row">
                  <button className="action-button" onClick={() => void handleTrainingAction('prepare')} type="button">准备工作区</button>
                  <button className="action-button" onClick={() => void handleTrainingAction('execute')} type="button">执行训练</button>
                </div>
                <pre className="workspace-code-block">{(trainingDetail.latest_logs ?? []).join('\n') || '暂无日志'}</pre>
                <pre className="workspace-code-block">{JSON.stringify(trainingDetail.execution_plan ?? {}, null, 2)}</pre>
                <pre className="workspace-code-block">{JSON.stringify(trainingDetail.result_summary ?? {}, null, 2)}</pre>
              </>
            )}
          </article>
        </div>
      </div>
    </div>
  )
}
