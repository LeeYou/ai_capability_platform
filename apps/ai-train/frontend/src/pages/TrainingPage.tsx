import { useEffect, useMemo, useState } from 'react'
import type { AnnotationTaskItem, CapabilityItem, TrainingTaskItem } from '../types'
import { fetchList, formatDateTime, prettyJson, request, statusTone } from '../api'

const initialTrainingForm = {
  capability_name: '',
  task_name: '',
  framework: 'pytorch',
  backend_type: 'cpu',
  annotation_task_id: '',
  train_params_json: '{\n  "epochs": 3,\n  "batch_size": 4,\n  "learning_rate": 0.001\n}',
}

const initialModelForm = {
  model_version: '',
  backend_type: '',
}

type LogSnapshot = {
  task_id: number
  status: string
  log_path?: string | null
  latest_logs?: string[]
  execution_plan?: Record<string, unknown> | null
  result_summary?: Record<string, unknown> | null
}

export default function TrainingPage() {
  const [trainingTasks, setTrainingTasks] = useState<TrainingTaskItem[]>([])
  const [annotationTasks, setAnnotationTasks] = useState<AnnotationTaskItem[]>([])
  const [capabilities, setCapabilities] = useState<CapabilityItem[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [selectedTrainingTaskId, setSelectedTrainingTaskId] = useState<number | null>(null)
  const [trainingDetail, setTrainingDetail] = useState<TrainingTaskItem | null>(null)
  const [actionMessage, setActionMessage] = useState<string | null>(null)
  const [capabilityFilter, setCapabilityFilter] = useState('all')
  const [statusFilter, setStatusFilter] = useState('all')
  const [trainingForm, setTrainingForm] = useState(initialTrainingForm)
  const [modelForm, setModelForm] = useState(initialModelForm)

  async function loadTrainingWorkspace(): Promise<void> {
    setLoading(true)
    setError(null)
    try {
      const [taskItems, annotationItems, capabilityItems] = await Promise.all([
        fetchList<TrainingTaskItem>('/api/v1/training-tasks'),
        fetchList<AnnotationTaskItem>('/api/v1/annotation-tasks'),
        fetchList<CapabilityItem>('/api/v1/capabilities'),
      ])
      setTrainingTasks(taskItems)
      setAnnotationTasks(annotationItems)
      setCapabilities(capabilityItems)
      setSelectedTrainingTaskId((current) => current ?? taskItems[0]?.task_id ?? null)
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : '加载数据失败')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    void loadTrainingWorkspace()
  }, [])

  useEffect(() => {
    if (selectedTrainingTaskId == null) {
      setTrainingDetail(null)
      return
    }
    void request<TrainingTaskItem>(`/api/v1/training-tasks/${selectedTrainingTaskId}`).then(setTrainingDetail)
  }, [selectedTrainingTaskId])

  const filteredTrainingTasks = useMemo(
    () =>
      trainingTasks.filter((item) => {
        if (capabilityFilter !== 'all' && item.capability_name !== capabilityFilter) return false
        if (statusFilter !== 'all' && item.status !== statusFilter) return false
        return true
      }),
    [capabilityFilter, statusFilter, trainingTasks],
  )

  const availableAnnotationTasks = useMemo(() => {
    if (!trainingForm.capability_name) return annotationTasks
    return annotationTasks.filter(
      (item) => item.capability_name === trainingForm.capability_name && item.status === 'completed',
    )
  }, [annotationTasks, trainingForm.capability_name])

  const summaryCards = useMemo(() => {
    const completedCount = trainingTasks.filter((item) => item.status === 'completed').length
    const runningCount = trainingTasks.filter((item) => item.status === 'running').length
    const failedCount = trainingTasks.filter((item) => item.status === 'failed').length
    return [
      { title: '训练任务', value: trainingTasks.length, detail: '全量训练作业' },
      { title: '执行中', value: runningCount, detail: '当前处于 running 的作业' },
      { title: '已完成', value: completedCount, detail: '可登记模型产物' },
      { title: '失败任务', value: failedCount, detail: '可直接重新执行' },
    ]
  }, [trainingTasks])

  async function handleCreateTrainingTask(event: React.FormEvent): Promise<void> {
    event.preventDefault()
    setActionMessage(null)
    try {
      const trainParams = JSON.parse(trainingForm.train_params_json) as Record<string, unknown>
      const created = await request<TrainingTaskItem>('/api/v1/training-tasks', {
        method: 'POST',
        body: JSON.stringify({
          capability_name: trainingForm.capability_name,
          task_name: trainingForm.task_name,
          framework: trainingForm.framework,
          backend_type: trainingForm.backend_type,
          annotation_task_id: trainingForm.annotation_task_id ? Number(trainingForm.annotation_task_id) : null,
          train_params: trainParams,
        }),
      })
      setActionMessage(`训练任务 ${created.task_name} 已创建`)
      setTrainingForm(initialTrainingForm)
      await loadTrainingWorkspace()
      setSelectedTrainingTaskId(created.task_id)
    } catch (submitError) {
      setActionMessage(submitError instanceof Error ? submitError.message : '创建训练任务失败')
    }
  }

  async function handleTrainingAction(path: 'prepare' | 'execute'): Promise<void> {
    if (selectedTrainingTaskId == null) return
    try {
      await request(`/api/v1/training-tasks/${selectedTrainingTaskId}/${path}`, {
        method: 'POST',
      })
      setActionMessage(path === 'prepare' ? '训练工作区准备完成' : '训练执行已完成')
      await loadTrainingWorkspace()
      const detail = await request<TrainingTaskItem>(`/api/v1/training-tasks/${selectedTrainingTaskId}`)
      setTrainingDetail(detail)
    } catch (loadError) {
      setActionMessage(loadError instanceof Error ? loadError.message : '训练动作失败')
    }
  }

  async function handleStatusUpdate(status: 'failed' | 'running'): Promise<void> {
    if (selectedTrainingTaskId == null) return
    try {
      const detail = await request<TrainingTaskItem>(`/api/v1/training-tasks/${selectedTrainingTaskId}/status`, {
        method: 'PATCH',
        body: JSON.stringify({ status }),
      })
      setTrainingDetail(detail)
      setActionMessage(`训练任务状态已更新为 ${status}`)
      await loadTrainingWorkspace()
    } catch (statusError) {
      setActionMessage(statusError instanceof Error ? statusError.message : '更新训练状态失败')
    }
  }

  async function refreshLogs(): Promise<void> {
    if (selectedTrainingTaskId == null) return
    try {
      const snapshot = await request<LogSnapshot>(`/api/v1/training-tasks/${selectedTrainingTaskId}/logs`)
      setTrainingDetail((current) =>
        current == null
          ? current
          : {
              ...current,
              latest_logs: snapshot.latest_logs ?? [],
              execution_plan: snapshot.execution_plan ?? current.execution_plan,
              result_summary: snapshot.result_summary ?? current.result_summary,
              status: snapshot.status,
            },
      )
      setActionMessage('日志快照已刷新')
    } catch (snapshotError) {
      setActionMessage(snapshotError instanceof Error ? snapshotError.message : '刷新日志失败')
    }
  }

  async function handleCreateModelArtifact(event: React.FormEvent): Promise<void> {
    event.preventDefault()
    if (!trainingDetail) return
    try {
      await request('/api/v1/models', {
        method: 'POST',
        body: JSON.stringify({
          capability_name: trainingDetail.capability_name,
          model_version: modelForm.model_version,
          source_training_task_id: trainingDetail.task_id,
          backend_type: modelForm.backend_type || trainingDetail.backend_type,
        }),
      })
      setActionMessage(`模型版本 ${modelForm.model_version} 已登记`)
      setModelForm(initialModelForm)
    } catch (createError) {
      setActionMessage(createError instanceof Error ? createError.message : '登记模型失败')
    }
  }

  const bestMetric = trainingDetail?.result_summary?.best_metric
  const executionPlanTrainParams =
    trainingDetail?.execution_plan && typeof trainingDetail.execution_plan === 'object'
      ? (trainingDetail.execution_plan.train_params as Record<string, unknown> | undefined)
      : undefined
  const epochs = trainingDetail?.result_summary?.epochs ?? executionPlanTrainParams?.epochs

  return (
    <div className="page-container">
      <section className="panel">
        <div className="section-header">
          <div>
            <h2>训练任务中心</h2>
            <p>覆盖任务创建、执行监控、日志快照与模型登记的完整训练闭环。</p>
          </div>
          <div className="workspace-action-row">
            <button className="action-button" type="button" onClick={() => void loadTrainingWorkspace()}>刷新任务</button>
          </div>
        </div>
        <div className="workspace-highlight-grid">
          {summaryCards.map((item) => (
            <article key={item.title} className="workspace-highlight-card">
              <span>{item.title}</span>
              <strong>{item.value}</strong>
              <span>{item.detail}</span>
            </article>
          ))}
        </div>
      </section>

      <section className="panel">
        <div className="workspace-panel-grid">
          <div className="workspace-stack">
            <article className="workspace-note-block">
              <div className="section-header">
                <h3>新建训练任务</h3>
                <span className="badge badge-muted">T18</span>
              </div>
              <form className="workspace-form-grid" onSubmit={(event) => void handleCreateTrainingTask(event)}>
                <label className="workspace-field">
                  能力
                  <select
                    value={trainingForm.capability_name}
                    onChange={(event) => setTrainingForm((current) => ({
                      ...current,
                      capability_name: event.target.value,
                      annotation_task_id: '',
                    }))}
                  >
                    <option value="">请选择能力</option>
                    {capabilities.map((item) => (
                      <option key={item.capability_name} value={item.capability_name}>
                        {item.display_name} ({item.capability_name})
                      </option>
                    ))}
                  </select>
                </label>
                <label className="workspace-field">
                  任务名称
                  <input
                    value={trainingForm.task_name}
                    onChange={(event) => setTrainingForm((current) => ({ ...current, task_name: event.target.value }))}
                    placeholder="如 face_detect_v2_train"
                  />
                </label>
                <label className="workspace-field">
                  框架
                  <select
                    value={trainingForm.framework}
                    onChange={(event) => setTrainingForm((current) => ({ ...current, framework: event.target.value }))}
                  >
                    <option value="pytorch">pytorch</option>
                    <option value="onnx">onnx</option>
                    <option value="custom">custom</option>
                  </select>
                </label>
                <label className="workspace-field">
                  执行后端
                  <select
                    value={trainingForm.backend_type}
                    onChange={(event) => setTrainingForm((current) => ({ ...current, backend_type: event.target.value }))}
                  >
                    <option value="cpu">cpu</option>
                    <option value="gpu">gpu</option>
                  </select>
                </label>
                <label className="workspace-field">
                  来源标注任务
                  <select
                    value={trainingForm.annotation_task_id}
                    onChange={(event) => setTrainingForm((current) => ({ ...current, annotation_task_id: event.target.value }))}
                  >
                    <option value="">不绑定标注任务</option>
                    {availableAnnotationTasks.map((item) => (
                      <option key={item.task_id} value={String(item.task_id)}>
                        #{item.task_id} {item.task_name}
                      </option>
                    ))}
                  </select>
                </label>
                <label className="workspace-field full-span">
                  训练参数 JSON
                  <textarea
                    rows={8}
                    value={trainingForm.train_params_json}
                    onChange={(event) => setTrainingForm((current) => ({ ...current, train_params_json: event.target.value }))}
                  />
                </label>
                <div className="workspace-action-row full-span">
                  <button className="action-button" type="submit">创建训练任务</button>
                </div>
              </form>
              {actionMessage && <p className="info-text">{actionMessage}</p>}
            </article>

            <article className="workspace-note-block">
              <div className="section-header">
                <h3>训练任务列表</h3>
                <span className="badge badge-muted">{filteredTrainingTasks.length} 项</span>
              </div>
              <div className="workspace-form-grid">
                <label className="workspace-field">
                  能力筛选
                  <select value={capabilityFilter} onChange={(event) => setCapabilityFilter(event.target.value)}>
                    <option value="all">全部</option>
                    {capabilities.map((item) => (
                      <option key={item.capability_name} value={item.capability_name}>{item.display_name}</option>
                    ))}
                  </select>
                </label>
                <label className="workspace-field">
                  状态筛选
                  <select value={statusFilter} onChange={(event) => setStatusFilter(event.target.value)}>
                    <option value="all">全部</option>
                    <option value="pending">pending</option>
                    <option value="running">running</option>
                    <option value="completed">completed</option>
                    <option value="failed">failed</option>
                  </select>
                </label>
              </div>
              {loading && <div className="workspace-empty">正在加载训练任务数据...</div>}
              {error && <p className="error-text">数据加载失败：{error}</p>}
              {!loading && !error && filteredTrainingTasks.length === 0 && (
                <div className="workspace-empty">暂无符合筛选条件的训练任务。</div>
              )}
              {!loading && !error && filteredTrainingTasks.length > 0 && (
                <div className="workspace-list">
                  {filteredTrainingTasks.map((item) => (
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
                        <span>{item.backend_type}</span>
                        <span className={`status-pill ${statusTone(item.status)}`}>{item.status}</span>
                      </div>
                      <div className="workspace-meta-row">
                        <span>创建：{formatDateTime(item.created_at)}</span>
                        <span>重试：{item.retry_count}</span>
                      </div>
                    </button>
                  ))}
                </div>
              )}
            </article>
          </div>

          <div className="workspace-stack">
            <article className="workspace-note-block">
              <div className="section-header">
                <h3>训练执行视图</h3>
                {trainingDetail && <span className={`status-pill ${statusTone(trainingDetail.status)}`}>{trainingDetail.status}</span>}
              </div>
              {!trainingDetail ? (
                <div className="workspace-empty">请选择训练任务查看执行信息。</div>
              ) : (
                <>
                  <div className="workspace-kpi-grid">
                    <article className="workspace-kpi-card">
                      <span>后端</span>
                      <strong>{trainingDetail.backend_type}</strong>
                    </article>
                    <article className="workspace-kpi-card">
                      <span>最佳指标</span>
                      <strong>{typeof bestMetric === 'number' ? bestMetric.toFixed(4) : '-'}</strong>
                    </article>
                    <article className="workspace-kpi-card">
                      <span>训练轮次</span>
                      <strong>{typeof epochs === 'number' ? epochs : '-'}</strong>
                    </article>
                    <article className="workspace-kpi-card">
                      <span>最近更新</span>
                      <strong className="kpi-date">{formatDateTime(trainingDetail.updated_at)}</strong>
                    </article>
                  </div>

                  <div className="workspace-table-wrap">
                    <table className="workspace-table">
                      <tbody>
                        <tr><th>任务 ID</th><td>{trainingDetail.task_id}</td><th>任务名称</th><td>{trainingDetail.task_name}</td></tr>
                        <tr><th>能力</th><td>{trainingDetail.capability_name}</td><th>任务类型</th><td>{trainingDetail.task_type}</td></tr>
                        <tr><th>数据集路径</th><td colSpan={3}><code>{trainingDetail.dataset_path}</code></td></tr>
                        <tr><th>创建时间</th><td>{formatDateTime(trainingDetail.created_at)}</td><th>开始时间</th><td>{formatDateTime(trainingDetail.started_at)}</td></tr>
                        <tr><th>完成时间</th><td>{formatDateTime(trainingDetail.completed_at)}</td><th>重试次数</th><td>{trainingDetail.retry_count}</td></tr>
                      </tbody>
                    </table>
                  </div>

                  <div className="workspace-action-row">
                    <button className="action-button" onClick={() => void handleTrainingAction('prepare')} type="button">准备工作区</button>
                    <button className="action-button" onClick={() => void handleTrainingAction('execute')} type="button">
                      {trainingDetail.status === 'failed' ? '重新执行' : '执行训练'}
                    </button>
                    {trainingDetail.status === 'running' && (
                      <button className="action-button danger-button" onClick={() => void handleStatusUpdate('failed')} type="button">标记失败</button>
                    )}
                    {trainingDetail.status === 'failed' && (
                      <button className="action-button" onClick={() => void handleStatusUpdate('running')} type="button">标记重试</button>
                    )}
                    <button className="action-button" onClick={() => void refreshLogs()} type="button">刷新日志</button>
                  </div>

                  {trainingDetail.status === 'completed' && (
                    <div className="workspace-note-block">
                      <div className="section-header">
                        <h3>登记模型产物</h3>
                      </div>
                      <form className="workspace-form-grid" onSubmit={(event) => void handleCreateModelArtifact(event)}>
                        <label className="workspace-field">
                          模型版本
                          <input
                            value={modelForm.model_version}
                            onChange={(event) => setModelForm((current) => ({ ...current, model_version: event.target.value }))}
                            placeholder="如 v1.0.0"
                          />
                        </label>
                        <label className="workspace-field">
                          目标后端
                          <input
                            value={modelForm.backend_type}
                            onChange={(event) => setModelForm((current) => ({ ...current, backend_type: event.target.value }))}
                            placeholder={trainingDetail.backend_type}
                          />
                        </label>
                        <div className="workspace-action-row full-span">
                          <button className="action-button" type="submit">登记模型</button>
                        </div>
                      </form>
                    </div>
                  )}

                  <div className="workspace-stack">
                    <div>
                      <div className="section-header">
                        <h3>最新日志</h3>
                        <span className="badge badge-muted">{trainingDetail.latest_logs?.length ?? 0} 行</span>
                      </div>
                      <pre className="workspace-code-block">{(trainingDetail.latest_logs ?? []).join('\n') || '暂无日志'}</pre>
                    </div>
                    <div>
                      <h3>执行计划</h3>
                      <pre className="workspace-code-block">{prettyJson(trainingDetail.execution_plan ?? {})}</pre>
                    </div>
                    <div>
                      <h3>结果摘要</h3>
                      <pre className="workspace-code-block">{prettyJson(trainingDetail.result_summary ?? {})}</pre>
                    </div>
                  </div>
                </>
              )}
            </article>
          </div>
        </div>
      </section>
    </div>
  )
}
