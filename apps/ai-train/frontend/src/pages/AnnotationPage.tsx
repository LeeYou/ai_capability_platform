import { useCallback, useEffect, useMemo, useState } from 'react'
import type { AnnotationTaskItem, AnnotationDraft, CapabilityItem } from '../types'
import { request, fetchList, statusTone, extractDraft, buildAnnotationPayload, prettyJson, formatDateTime, emptyAnnotationDraft } from '../api'
import { buildAnnotationChecklist, buildSampleOpsSummary, clampScore, scoreTone } from '../enterprise'

const initialTaskForm = {
  capability_name: '',
  task_name: '',
  sample_total: '20',
}

export default function AnnotationPage() {
  const [annotationTasks, setAnnotationTasks] = useState<AnnotationTaskItem[]>([])
  const [capabilities, setCapabilities] = useState<CapabilityItem[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [selectedAnnotationTaskId, setSelectedAnnotationTaskId] = useState<number | null>(null)
  const [annotationDetail, setAnnotationDetail] = useState<AnnotationTaskItem | null>(null)
  const [annotationDrafts, setAnnotationDrafts] = useState<Record<string, AnnotationDraft>>({})
  const [actionMessage, setActionMessage] = useState<string | null>(null)
  const [taskForm, setTaskForm] = useState(initialTaskForm)
  const [taskCapabilityFilter, setTaskCapabilityFilter] = useState('all')
  const [taskStatusFilter, setTaskStatusFilter] = useState('all')
  const [sampleStatusFilter, setSampleStatusFilter] = useState('all')
  const [selectedSampleId, setSelectedSampleId] = useState<string | null>(null)
  const [jumpSampleId, setJumpSampleId] = useState('')

  async function loadAnnotationTasks(): Promise<void> {
    setLoading(true)
    setError(null)
    try {
      const [tasks, capabilityItems] = await Promise.all([
        fetchList<AnnotationTaskItem>('/api/v1/annotation-tasks'),
        fetchList<CapabilityItem>('/api/v1/capabilities'),
      ])
      setAnnotationTasks(tasks)
      setCapabilities(capabilityItems)
      setSelectedAnnotationTaskId((current) => current ?? tasks[0]?.task_id ?? null)
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : '加载数据失败')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    void loadAnnotationTasks()
  }, [])

  useEffect(() => {
    if (selectedAnnotationTaskId == null) {
      setAnnotationDetail(null)
      return
    }
    void request<AnnotationTaskItem>(`/api/v1/annotation-tasks/${selectedAnnotationTaskId}`).then((payload) => {
      setAnnotationDetail(payload)
      const nextDrafts: Record<string, AnnotationDraft> = {}
      for (const sample of payload.sample_items ?? []) {
        nextDrafts[sample.sample_id] = extractDraft(sample)
      }
      setAnnotationDrafts(nextDrafts)
      const firstSampleId = payload.sample_items?.[0]?.sample_id ?? null
      setSelectedSampleId(firstSampleId)
      setJumpSampleId(firstSampleId ?? '')
    })
  }, [selectedAnnotationTaskId])

  const filteredTasks = useMemo(
    () =>
      annotationTasks.filter((item) => {
        if (taskCapabilityFilter !== 'all' && item.capability_name !== taskCapabilityFilter) return false
        if (taskStatusFilter !== 'all' && item.status !== taskStatusFilter) return false
        return true
      }),
    [annotationTasks, taskCapabilityFilter, taskStatusFilter],
  )

  const filteredSamples = useMemo(() => {
    const sampleItems = annotationDetail?.sample_items ?? []
    if (sampleStatusFilter === 'all') return sampleItems
    return sampleItems.filter((item) => item.status === sampleStatusFilter)
  }, [annotationDetail?.sample_items, sampleStatusFilter])

  const currentSampleIndex = useMemo(
    () => filteredSamples.findIndex((item) => item.sample_id === selectedSampleId),
    [filteredSamples, selectedSampleId],
  )

  const currentSample = currentSampleIndex >= 0 ? filteredSamples[currentSampleIndex] : null
  const currentDraft = currentSample ? annotationDrafts[currentSample.sample_id] : null
  const submissionScore = annotationDetail
    ? clampScore(
        (annotationDetail.sample_total === 0 ? 0 : (annotationDetail.labeled_count / annotationDetail.sample_total) * 70) +
        ((annotationDetail.sample_items ?? []).filter((item) => item.status === 'submitted').length / Math.max(1, annotationDetail.sample_total)) * 30,
      )
    : 0
  const annotationChecklist = useMemo(() => buildAnnotationChecklist(annotationDetail), [annotationDetail])
  const sampleOpsSummary = useMemo(
    () => buildSampleOpsSummary(annotationDetail?.sample_items ?? []),
    [annotationDetail?.sample_items],
  )

  useEffect(() => {
    if (filteredSamples.length === 0) {
      setSelectedSampleId(null)
      return
    }
    if (!selectedSampleId || !filteredSamples.some((item) => item.sample_id === selectedSampleId)) {
      setSelectedSampleId(filteredSamples[0].sample_id)
      setJumpSampleId(filteredSamples[0].sample_id)
    }
  }, [filteredSamples, selectedSampleId])

  const navigateSample = useCallback((offset: number): void => {
    const nextIndex = currentSampleIndex + offset
    if (nextIndex < 0 || nextIndex >= filteredSamples.length) return
    const nextSample = filteredSamples[nextIndex]
    setSelectedSampleId(nextSample.sample_id)
    setJumpSampleId(nextSample.sample_id)
  }, [currentSampleIndex, filteredSamples])

  useEffect(() => {
    function handleKeyDown(event: KeyboardEvent): void {
      if (event.target instanceof HTMLInputElement || event.target instanceof HTMLTextAreaElement || event.target instanceof HTMLSelectElement) {
        return
      }
      if (event.key === 'ArrowLeft') {
        navigateSample(-1)
      }
      if (event.key === 'ArrowRight') {
        navigateSample(1)
      }
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [navigateSample])

  function updateDraft(sampleId: string, patch: Partial<AnnotationDraft>): void {
    setAnnotationDrafts((current) => ({
      ...current,
      [sampleId]: {
        ...(current[sampleId] ?? emptyAnnotationDraft),
        ...patch,
      },
    }))
  }

  async function handleCreateTask(event: React.FormEvent): Promise<void> {
    event.preventDefault()
    setActionMessage(null)
    try {
      const created = await request<AnnotationTaskItem>('/api/v1/annotation-tasks', {
        method: 'POST',
        body: JSON.stringify({
          capability_name: taskForm.capability_name,
          task_name: taskForm.task_name,
          sample_total: Number(taskForm.sample_total),
        }),
      })
      setActionMessage(`标注任务 ${created.task_name} 已创建`)
      setTaskForm(initialTaskForm)
      await loadAnnotationTasks()
      setSelectedAnnotationTaskId(created.task_id)
    } catch (submitError) {
      setActionMessage(submitError instanceof Error ? submitError.message : '创建标注任务失败')
    }
  }

  async function saveAnnotations(sampleIds: string[], markSubmitted: boolean): Promise<void> {
    if (!annotationDetail) return
    try {
      const annotations = sampleIds
        .map((sampleId) => buildAnnotationPayload(sampleId, annotationDrafts[sampleId], annotationDetail.task_type))
        .filter((item): item is Record<string, unknown> => item != null)

      await request(`/api/v1/annotation-tasks/${annotationDetail.task_id}/samples`, {
        method: 'PATCH',
        body: JSON.stringify({
          annotations,
          mark_submitted: markSubmitted,
        }),
      })

      setActionMessage(markSubmitted ? '标注结果已提交' : '标注草稿已保存')
      const refreshed = await request<AnnotationTaskItem>(`/api/v1/annotation-tasks/${annotationDetail.task_id}`)
      setAnnotationDetail(refreshed)
      await loadAnnotationTasks()
    } catch (saveError) {
      setActionMessage(saveError instanceof Error ? saveError.message : '保存标注失败')
    }
  }

  async function handleDeleteTask(taskId: number): Promise<void> {
    if (!window.confirm(`确认删除标注任务 #${taskId} 吗？`)) return
    try {
      await request(`/api/v1/annotation-tasks/${taskId}`, { method: 'DELETE' })
      setActionMessage(`标注任务 #${taskId} 已删除`)
      setAnnotationDetail(null)
      setSelectedAnnotationTaskId(null)
      await loadAnnotationTasks()
    } catch (deleteError) {
      setActionMessage(deleteError instanceof Error ? deleteError.message : '删除标注任务失败')
    }
  }

  function exportCurrentTask(): void {
    if (!annotationDetail) return
    const payload = {
      task_id: annotationDetail.task_id,
      task_name: annotationDetail.task_name,
      capability_name: annotationDetail.capability_name,
      annotations: (annotationDetail.sample_items ?? [])
        .filter((item) => item.annotation)
        .map((item) => ({
          sample_id: item.sample_id,
          ...item.annotation,
        })),
    }
    const blob = new Blob([JSON.stringify(payload, null, 2)], { type: 'application/json;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const anchor = document.createElement('a')
    anchor.href = url
    anchor.download = `${annotationDetail.task_name || `annotation-task-${annotationDetail.task_id}`}.json`
    anchor.click()
    URL.revokeObjectURL(url)
  }

  const progressValue = annotationDetail ? Math.round((annotationDetail.completion_ratio ?? 0) * 100) : 0

  return (
    <div className="page-container">
      <section className="panel">
        <div className="section-header">
          <div>
            <h2>标注任务中心</h2>
            <p>补齐标注任务创建、单样本工作台、批量保存/提交与结果导出，并加入企业级质量门禁。</p>
          </div>
          <div className="workspace-action-row">
            <button className="action-button" type="button" onClick={() => void loadAnnotationTasks()}>刷新任务</button>
          </div>
        </div>
        <div className="enterprise-stage-grid">
          <article className={`enterprise-stage-card tone-${scoreTone(submissionScore)}`}>
            <span>提交流程成熟度</span>
            <strong>{submissionScore}</strong>
            <p>根据样本覆盖率和 submitted 覆盖率自动计算。</p>
          </article>
          {sampleOpsSummary.slice(0, 3).map((item) => (
            <article key={item.title} className={`enterprise-stage-card tone-${item.tone}`}>
              <span>{item.title}</span>
              <strong>{item.detail.split(' ')[0]}</strong>
              <p>{item.detail}</p>
            </article>
          ))}
        </div>
      </section>

      <section className="panel">
        <div className="workspace-panel-grid">
          <div className="workspace-stack">
            <article className="workspace-note-block">
              <div className="section-header">
                <h3>创建标注任务</h3>
                <span className="badge badge-muted">T17</span>
              </div>
              <form className="workspace-form-grid" onSubmit={(event) => void handleCreateTask(event)}>
                <label className="workspace-field">
                  能力
                  <select
                    value={taskForm.capability_name}
                    onChange={(event) => setTaskForm((current) => ({ ...current, capability_name: event.target.value }))}
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
                    value={taskForm.task_name}
                    onChange={(event) => setTaskForm((current) => ({ ...current, task_name: event.target.value }))}
                    placeholder="如 face_detect_round_1"
                  />
                </label>
                <label className="workspace-field">
                  样本总数
                  <input
                    type="number"
                    min={1}
                    value={taskForm.sample_total}
                    onChange={(event) => setTaskForm((current) => ({ ...current, sample_total: event.target.value }))}
                  />
                </label>
                <div className="workspace-action-row full-span">
                  <button className="action-button" type="submit">创建标注任务</button>
                </div>
              </form>
              {actionMessage && <p className="info-text">{actionMessage}</p>}
            </article>

            <article className="workspace-note-block">
              <div className="section-header">
                <h3>标注任务列表</h3>
                <span className="badge badge-muted">{filteredTasks.length} 项</span>
              </div>
              <div className="workspace-form-grid">
                <label className="workspace-field">
                  能力筛选
                  <select value={taskCapabilityFilter} onChange={(event) => setTaskCapabilityFilter(event.target.value)}>
                    <option value="all">全部</option>
                    {capabilities.map((item) => (
                      <option key={item.capability_name} value={item.capability_name}>{item.display_name}</option>
                    ))}
                  </select>
                </label>
                <label className="workspace-field">
                  状态筛选
                  <select value={taskStatusFilter} onChange={(event) => setTaskStatusFilter(event.target.value)}>
                    <option value="all">全部</option>
                    <option value="pending">pending</option>
                    <option value="annotating">annotating</option>
                    <option value="completed">completed</option>
                  </select>
                </label>
              </div>
              {loading && <div className="workspace-empty">正在加载标注任务数据...</div>}
              {error && <p className="error-text">数据加载失败：{error}</p>}
              {!loading && !error && filteredTasks.length === 0 && (
                <div className="workspace-empty">暂无符合筛选条件的标注任务。</div>
              )}
              {!loading && !error && filteredTasks.length > 0 && (
                <div className="workspace-list">
                  {filteredTasks.map((item) => (
                    <button
                      key={item.task_id}
                      className={`workspace-list-item${selectedAnnotationTaskId === item.task_id ? ' active' : ''}`}
                      onClick={() => setSelectedAnnotationTaskId(item.task_id)}
                      type="button"
                    >
                      <strong>{item.task_name}</strong>
                      <div className="workspace-meta-row">
                        <span>{item.capability_name}</span>
                        <span>{item.task_type}</span>
                        <span>{item.labeled_count}/{item.sample_total}</span>
                        <span className={`status-pill ${statusTone(item.status)}`}>{item.status}</span>
                      </div>
                      <div className="workspace-meta-row">
                        <span>创建：{formatDateTime(item.created_at)}</span>
                        <span>结果：{item.result_path ? '已生成' : '未生成'}</span>
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
                <h3>标注工作台</h3>
                {annotationDetail && <span className={`status-pill ${statusTone(annotationDetail.status)}`}>{annotationDetail.status}</span>}
              </div>
              {!annotationDetail ? (
                <div className="workspace-empty">请选择标注任务查看样本工作台。</div>
              ) : (
                <>
                  <div className="workspace-kpi-grid">
                    <article className="workspace-kpi-card">
                      <span>完成率</span>
                      <strong>{progressValue}%</strong>
                    </article>
                    <article className="workspace-kpi-card">
                      <span>任务类型</span>
                      <strong>{annotationDetail.task_type}</strong>
                    </article>
                    <article className="workspace-kpi-card">
                      <span>已标注</span>
                      <strong>{annotationDetail.labeled_count}</strong>
                    </article>
                    <article className="workspace-kpi-card">
                      <span>最近更新</span>
                      <strong className="kpi-date">{formatDateTime(annotationDetail.updated_at)}</strong>
                    </article>
                  </div>

                  <div className="workspace-table-wrap">
                    <table className="workspace-table">
                      <tbody>
                        <tr><th>任务名称</th><td>{annotationDetail.task_name}</td><th>能力</th><td>{annotationDetail.capability_name}</td></tr>
                        <tr><th>数据集路径</th><td colSpan={3}><code>{annotationDetail.dataset_path}</code></td></tr>
                        <tr><th>结果文件</th><td colSpan={3}><code>{annotationDetail.result_path ?? '-'}</code></td></tr>
                      </tbody>
                    </table>
                  </div>

                  <div className="workspace-action-row">
                    <button className="action-button" type="button" onClick={() => navigateSample(-1)}>上一条</button>
                    <button className="action-button" type="button" onClick={() => navigateSample(1)}>下一条</button>
                    <button className="action-button" type="button" onClick={() => void saveAnnotations(currentSample ? [currentSample.sample_id] : [], false)}>保存当前样本</button>
                    <button className="action-button" type="button" onClick={() => void saveAnnotations(filteredSamples.map((item) => item.sample_id), false)}>批量保存</button>
                    <button className="action-button" type="button" onClick={() => void saveAnnotations(filteredSamples.map((item) => item.sample_id), true)}>提交当前筛选集</button>
                    <button className="action-button" type="button" onClick={() => exportCurrentTask()}>导出结果</button>
                    <button className="action-button danger-button" type="button" onClick={() => void handleDeleteTask(annotationDetail.task_id)}>删除任务</button>
                  </div>

                  <div className="enterprise-two-column">
                    <article className="enterprise-note-card">
                      <strong>质量门禁</strong>
                      <ul className="enterprise-checklist">
                        {annotationChecklist.map((item) => (
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
                      <strong>样本作业态势</strong>
                      <div className="enterprise-stack">
                        {sampleOpsSummary.map((item) => (
                          <div key={item.title} className={`enterprise-inline-card tone-${item.tone}`}>
                            <strong>{item.title}</strong>
                            <p>{item.detail}</p>
                          </div>
                        ))}
                      </div>
                    </article>
                  </div>

                  <div className="workspace-form-grid">
                    <label className="workspace-field">
                      样本状态筛选
                      <select value={sampleStatusFilter} onChange={(event) => setSampleStatusFilter(event.target.value)}>
                        <option value="all">全部样本</option>
                        <option value="pending">pending</option>
                        <option value="labeled">labeled</option>
                        <option value="submitted">submitted</option>
                      </select>
                    </label>
                    <label className="workspace-field">
                      跳转样本 ID
                      <div className="inline-input-row">
                        <input value={jumpSampleId} onChange={(event) => setJumpSampleId(event.target.value)} placeholder="如 sample_1" />
                        <button
                          className="action-button"
                          type="button"
                          onClick={() => {
                            if (filteredSamples.some((item) => item.sample_id === jumpSampleId)) {
                              setSelectedSampleId(jumpSampleId)
                            }
                          }}
                        >
                          跳转
                        </button>
                      </div>
                    </label>
                  </div>

                  <div className="annotation-workspace-grid">
                    <div className="workspace-note-block">
                      <div className="section-header">
                        <h3>样本列表</h3>
                        <span className="badge badge-muted">{filteredSamples.length} 条</span>
                      </div>
                      <div className="workspace-list sample-scroll-list">
                        {filteredSamples.map((sample) => (
                          <button
                            key={sample.sample_id}
                            className={`workspace-list-item${selectedSampleId === sample.sample_id ? ' active' : ''}`}
                            onClick={() => {
                              setSelectedSampleId(sample.sample_id)
                              setJumpSampleId(sample.sample_id)
                            }}
                            type="button"
                          >
                            <strong>{sample.sample_id}</strong>
                            <div className="workspace-meta-row">
                              <span className={`status-pill ${statusTone(sample.status)}`}>{sample.status}</span>
                              <span>{formatDateTime(sample.updated_at)}</span>
                            </div>
                          </button>
                        ))}
                      </div>
                    </div>

                    <div className="workspace-note-block">
                      <div className="section-header">
                        <h3>单样本编辑区</h3>
                        {currentSample && <span className={`status-pill ${statusTone(currentSample.status)}`}>{currentSample.status}</span>}
                      </div>
                      {!currentSample || !currentDraft ? (
                        <div className="workspace-empty">当前筛选条件下暂无样本。</div>
                      ) : (
                        <>
                          <div className="workspace-meta-row">
                            <span>样本位置：{currentSampleIndex + 1} / {filteredSamples.length}</span>
                            <span>样本 ID：{currentSample.sample_id}</span>
                          </div>
                          {annotationDetail.task_type === 'classification' && (
                            <>
                              <label className="workspace-field">
                                标签
                                <input
                                  value={currentDraft.label}
                                  onChange={(event) => updateDraft(currentSample.sample_id, { label: event.target.value })}
                                />
                              </label>
                              <label className="workspace-field">
                                属性 JSON
                                <textarea
                                  rows={6}
                                  value={currentDraft.attributesJson}
                                  onChange={(event) => updateDraft(currentSample.sample_id, { attributesJson: event.target.value })}
                                />
                              </label>
                            </>
                          )}
                          {annotationDetail.task_type === 'detection' && (
                            <label className="workspace-field">
                              目标框 JSON
                              <textarea
                                rows={10}
                                value={currentDraft.objectsJson}
                                onChange={(event) => updateDraft(currentSample.sample_id, { objectsJson: event.target.value })}
                              />
                            </label>
                          )}
                          {annotationDetail.task_type === 'ocr' && (
                            <>
                              <label className="workspace-field">
                                文本
                                <input
                                  value={currentDraft.text}
                                  onChange={(event) => updateDraft(currentSample.sample_id, { text: event.target.value })}
                                />
                              </label>
                              <label className="workspace-field">
                                区域 JSON
                                <textarea
                                  rows={10}
                                  value={currentDraft.regionsJson}
                                  onChange={(event) => updateDraft(currentSample.sample_id, { regionsJson: event.target.value })}
                                />
                              </label>
                            </>
                          )}
                          {annotationDetail.task_type === 'structured_extraction' && (
                            <>
                              <label className="workspace-field">
                                字段 JSON
                                <textarea
                                  rows={10}
                                  value={currentDraft.fieldsJson}
                                  onChange={(event) => updateDraft(currentSample.sample_id, { fieldsJson: event.target.value })}
                                />
                              </label>
                              <label className="workspace-field">
                                置信度 JSON
                                <textarea
                                  rows={6}
                                  value={currentDraft.confidenceJson}
                                  onChange={(event) => updateDraft(currentSample.sample_id, { confidenceJson: event.target.value })}
                                />
                              </label>
                            </>
                          )}
                          <label className="workspace-field">
                            备注
                            <textarea
                              rows={4}
                              value={currentDraft.note}
                              onChange={(event) => updateDraft(currentSample.sample_id, { note: event.target.value })}
                            />
                          </label>
                        </>
                      )}
                    </div>
                  </div>

                  <div>
                    <h3>标注契约</h3>
                    <pre className="workspace-code-block">{prettyJson(annotationDetail.annotation_schema ?? {})}</pre>
                  </div>
                  <div className="enterprise-note-card">
                    <strong>提交治理说明</strong>
                    <ul className="enterprise-list">
                      <li>建议先完成 labeled 全量保存，再执行 submitted 提交流程，便于质检抽查。</li>
                      <li>对于 detection / OCR / structured_extraction，优先保证 JSON 结构合法，再追求高覆盖率。</li>
                      <li>若样本超过 3 天未更新，应在班次交接前明确责任人与处理策略。</li>
                    </ul>
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
