import { useEffect, useState } from 'react'
import type { AnnotationTaskItem, AnnotationDraft } from '../types'
import { request, fetchList, statusTone, extractDraft, buildAnnotationPayload } from '../api'

export default function AnnotationPage() {
  const [annotationTasks, setAnnotationTasks] = useState<AnnotationTaskItem[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [selectedAnnotationTaskId, setSelectedAnnotationTaskId] = useState<number | null>(null)
  const [annotationDetail, setAnnotationDetail] = useState<AnnotationTaskItem | null>(null)
  const [annotationDrafts, setAnnotationDrafts] = useState<Record<string, AnnotationDraft>>({})
  const [actionMessage, setActionMessage] = useState<string | null>(null)

  async function loadAnnotationTasks(): Promise<void> {
    setLoading(true)
    setError(null)
    try {
      const tasks = await fetchList<AnnotationTaskItem>('/api/v1/annotation-tasks')
      setAnnotationTasks(tasks)
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
    })
  }, [selectedAnnotationTaskId])

  async function handleSaveAnnotations(markSubmitted: boolean): Promise<void> {
    if (!annotationDetail) return
    try {
      const annotations = Object.entries(annotationDrafts)
        .map(([sampleId, draft]) => buildAnnotationPayload(sampleId, draft, annotationDetail.task_type))
        .filter((item): item is Record<string, unknown> => item != null)

      await request(`/api/v1/annotation-tasks/${annotationDetail.task_id}/samples`, {
        method: 'PATCH',
        body: JSON.stringify({
          annotations,
          mark_submitted: markSubmitted,
        }),
      })
      setActionMessage(markSubmitted ? '标注任务已提交' : '标注草稿已保存')
      await loadAnnotationTasks()
    } catch (loadError) {
      setActionMessage(loadError instanceof Error ? loadError.message : '保存标注失败')
    }
  }

  return (
    <div className="page-container">
      {loading && <p className="info-text">正在加载标注任务数据...</p>}
      {error && <p className="error-text">数据加载失败：{error}</p>}
      {actionMessage && <p className="success-text">{actionMessage}</p>}
      <div className="workspace-panel-grid">
        <div className="workspace-stack">
          <article className="workspace-note-block">
            <div className="section-header">
              <h3>标注任务列表</h3>
              <span className="badge badge-muted">T17</span>
            </div>
            <div className="workspace-list">
              {annotationTasks.map((item) => (
                <button
                  key={item.task_id}
                  className={`workspace-list-item${selectedAnnotationTaskId === item.task_id ? ' active' : ''}`}
                  onClick={() => setSelectedAnnotationTaskId(item.task_id)}
                  type="button"
                >
                  <strong>{item.task_name}</strong>
                  <div className="workspace-meta-row">
                    <span>{item.task_type}</span>
                    <span>{item.labeled_count}/{item.sample_total}</span>
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
              <h3>三栏标注视图</h3>
              {annotationDetail && <span className={`status-pill ${statusTone(annotationDetail.status)}`}>{annotationDetail.status}</span>}
            </div>
            {!annotationDetail ? (
              <div className="workspace-empty">请选择标注任务查看样本编辑区。</div>
            ) : (
              <>
                <div className="workspace-kpi-grid">
                  <article className="workspace-kpi-card">
                    <span>完成率</span>
                    <strong>{Math.round((annotationDetail.completion_ratio ?? 0) * 100)}%</strong>
                  </article>
                  <article className="workspace-kpi-card">
                    <span>已标注</span>
                    <strong>{annotationDetail.labeled_count}</strong>
                  </article>
                  <article className="workspace-kpi-card">
                    <span>任务类型</span>
                    <strong>{annotationDetail.task_type}</strong>
                  </article>
                </div>
                <div className="sample-grid">
                  {(annotationDetail.sample_items ?? []).map((sample) => {
                    const draft = annotationDrafts[sample.sample_id]
                    if (!draft) return null
                    return (
                      <article key={sample.sample_id} className="sample-card">
                        <div className="card-header">
                          <strong>{sample.sample_id}</strong>
                          <span className={`status-pill ${statusTone(sample.status)}`}>{sample.status}</span>
                        </div>
                        {annotationDetail.task_type === 'classification' && (
                          <>
                            <label className="workspace-field">
                              标签
                              <input
                                value={draft.label}
                                onChange={(event) =>
                                  setAnnotationDrafts((current) => ({
                                    ...current,
                                    [sample.sample_id]: { ...draft, label: event.target.value },
                                  }))
                                }
                              />
                            </label>
                            <label className="workspace-field">
                              属性 JSON
                              <textarea
                                rows={4}
                                value={draft.attributesJson}
                                onChange={(event) =>
                                  setAnnotationDrafts((current) => ({
                                    ...current,
                                    [sample.sample_id]: { ...draft, attributesJson: event.target.value },
                                  }))
                                }
                              />
                            </label>
                          </>
                        )}
                        {annotationDetail.task_type === 'detection' && (
                          <label className="workspace-field">
                            目标框 JSON
                            <textarea
                              rows={6}
                              value={draft.objectsJson}
                              onChange={(event) =>
                                setAnnotationDrafts((current) => ({
                                  ...current,
                                  [sample.sample_id]: { ...draft, objectsJson: event.target.value },
                                }))
                              }
                            />
                          </label>
                        )}
                        {annotationDetail.task_type === 'ocr' && (
                          <>
                            <label className="workspace-field">
                              文本
                              <input
                                value={draft.text}
                                onChange={(event) =>
                                  setAnnotationDrafts((current) => ({
                                    ...current,
                                    [sample.sample_id]: { ...draft, text: event.target.value },
                                  }))
                                }
                              />
                            </label>
                            <label className="workspace-field">
                              区域 JSON
                              <textarea
                                rows={6}
                                value={draft.regionsJson}
                                onChange={(event) =>
                                  setAnnotationDrafts((current) => ({
                                    ...current,
                                    [sample.sample_id]: { ...draft, regionsJson: event.target.value },
                                  }))
                                }
                              />
                            </label>
                          </>
                        )}
                        {annotationDetail.task_type === 'structured_extraction' && (
                          <>
                            <label className="workspace-field">
                              字段 JSON
                              <textarea
                                rows={6}
                                value={draft.fieldsJson}
                                onChange={(event) =>
                                  setAnnotationDrafts((current) => ({
                                    ...current,
                                    [sample.sample_id]: { ...draft, fieldsJson: event.target.value },
                                  }))
                                }
                              />
                            </label>
                            <label className="workspace-field">
                              置信度 JSON
                              <textarea
                                rows={4}
                                value={draft.confidenceJson}
                                onChange={(event) =>
                                  setAnnotationDrafts((current) => ({
                                    ...current,
                                    [sample.sample_id]: { ...draft, confidenceJson: event.target.value },
                                  }))
                                }
                              />
                            </label>
                          </>
                        )}
                      </article>
                    )
                  })}
                </div>
                <div className="workspace-action-row">
                  <button className="action-button" onClick={() => void handleSaveAnnotations(false)} type="button">批量保存</button>
                  <button className="action-button" onClick={() => void handleSaveAnnotations(true)} type="button">提交标注</button>
                </div>
                <pre className="workspace-code-block">{JSON.stringify(annotationDetail.annotation_schema ?? {}, null, 2)}</pre>
              </>
            )}
          </article>
        </div>
      </div>
    </div>
  )
}
