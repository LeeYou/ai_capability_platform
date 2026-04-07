import { useEffect, useMemo, useState } from 'react'
import './App.css'
import '../../../frontend-common/src/r7Workspace.css'
import { buildR7Workspace } from '../../../frontend-common/src/r7Workspace.ts'

type CapabilityItem = {
  capability_name: string
  display_name: string
  task_type: string
  dataset_path: string
  dataset_status: string
  source: string
  annotation_schema: Record<string, unknown>
  template_bundle: Record<string, unknown>
}

type AnnotationSampleItem = {
  sample_id: string
  status: string
  annotation: Record<string, unknown> | null
  updated_at?: string | null
}

type AnnotationTaskItem = {
  task_id: number
  capability_name: string
  task_type: string
  task_name: string
  dataset_path: string
  status: string
  sample_total: number
  labeled_count: number
  result_path?: string | null
  completion_ratio?: number
  sample_items?: AnnotationSampleItem[]
  annotation_schema?: Record<string, unknown>
}

type TrainingTaskItem = {
  task_id: number
  capability_name: string
  task_type: string
  task_name: string
  dataset_path: string
  status: string
  framework: string
  backend_type: string
  annotation_task_id?: number | null
  retry_count: number
  log_path?: string | null
  workspace_path?: string | null
  started_at?: string | null
  completed_at?: string | null
  latest_logs?: string[]
  execution_plan?: Record<string, unknown> | null
  result_summary?: Record<string, unknown> | null
  training_input_path?: string | null
  template_bundle_path?: string | null
  export_dir?: string | null
}

type ModelArtifactItem = {
  artifact_id: number
  capability_name: string
  task_type: string
  model_version: string
  source_training_task_id: number
  artifact_path: string
  manifest_path: string
  backend_type: string
  checksum: string
  status: string
  manifest_preview?: Record<string, unknown> | null
  delivery_metadata?: Record<string, unknown> | null
  runtime_contract?: Record<string, unknown> | null
}

type ApiListResponse<T> = { items: T[] }

type DashboardData = {
  capabilities: CapabilityItem[]
  annotationTasks: AnnotationTaskItem[]
  trainingTasks: TrainingTaskItem[]
  modelArtifacts: ModelArtifactItem[]
}

type AnnotationDraft = {
  label: string
  note: string
  attributesJson: string
  objectsJson: string
  text: string
  regionsJson: string
  fieldsJson: string
  confidenceJson: string
}

const initialData: DashboardData = {
  capabilities: [],
  annotationTasks: [],
  trainingTasks: [],
  modelArtifacts: [],
}

const tabs = ['overview', 'annotation', 'training', 'model'] as const
type TabKey = (typeof tabs)[number]

const apiBaseUrl = import.meta.env.VITE_API_BASE_URL ?? ''
const workspace = buildR7Workspace(import.meta.env, 'ai-train')


async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${apiBaseUrl}${path}`, {
    headers: {
      'Content-Type': 'application/json',
      ...(init?.headers ?? {}),
    },
    ...init,
  })
  if (!response.ok) {
    const message = await response.text()
    throw new Error(message || `请求失败：${path}`)
  }
  return (await response.json()) as T
}

async function fetchList<T>(path: string): Promise<T[]> {
  const payload = await request<ApiListResponse<T>>(path)
  return payload.items
}

function prettyJson(value: unknown): string {
  return JSON.stringify(value ?? {}, null, 2)
}

function extractDraft(sample: AnnotationSampleItem): AnnotationDraft {
  const annotation = sample.annotation ?? {}
  return {
    label: typeof annotation.label === 'string' ? annotation.label : '',
    note: typeof annotation.note === 'string' ? annotation.note : '',
    attributesJson: prettyJson(annotation.attributes ?? {}),
    objectsJson: prettyJson(annotation.objects ?? []),
    text: typeof annotation.text === 'string' ? annotation.text : '',
    regionsJson: prettyJson(annotation.regions ?? []),
    fieldsJson: prettyJson(annotation.fields ?? {}),
    confidenceJson: prettyJson(annotation.confidence ?? {}),
  }
}

function parseJsonInput(raw: string, fallback: unknown): unknown {
  const normalized = raw.trim()
  if (!normalized) return fallback
  return JSON.parse(normalized) as unknown
}

function buildAnnotationPayload(sampleId: string, draft: AnnotationDraft, taskType: string): Record<string, unknown> | null {
  if (taskType === 'classification') {
    if (!draft.label.trim()) return null
    return {
      sample_id: sampleId,
      label: draft.label.trim(),
      note: draft.note.trim(),
      attributes: parseJsonInput(draft.attributesJson, {}),
    }
  }
  if (taskType === 'detection') {
    const objects = parseJsonInput(draft.objectsJson, [])
    if (!Array.isArray(objects) || objects.length === 0) return null
    return {
      sample_id: sampleId,
      objects,
      note: draft.note.trim(),
    }
  }
  if (taskType === 'ocr') {
    if (!draft.text.trim()) return null
    return {
      sample_id: sampleId,
      text: draft.text.trim(),
      regions: parseJsonInput(draft.regionsJson, []),
      note: draft.note.trim(),
    }
  }
  const fields = parseJsonInput(draft.fieldsJson, {})
  if (typeof fields !== 'object' || fields == null || Array.isArray(fields) || Object.keys(fields).length === 0) {
    return null
  }
  return {
    sample_id: sampleId,
    fields,
    confidence: parseJsonInput(draft.confidenceJson, {}),
    note: draft.note.trim(),
  }
}

function App() {
  const [activeTab, setActiveTab] = useState<TabKey>('overview')
  const [data, setData] = useState<DashboardData>(initialData)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [selectedAnnotationTaskId, setSelectedAnnotationTaskId] = useState<number | null>(null)
  const [selectedTrainingTaskId, setSelectedTrainingTaskId] = useState<number | null>(null)
  const [selectedModelArtifactId, setSelectedModelArtifactId] = useState<number | null>(null)
  const [annotationDetail, setAnnotationDetail] = useState<AnnotationTaskItem | null>(null)
  const [trainingDetail, setTrainingDetail] = useState<TrainingTaskItem | null>(null)
  const [modelDetail, setModelDetail] = useState<ModelArtifactItem | null>(null)
  const [annotationDrafts, setAnnotationDrafts] = useState<Record<string, AnnotationDraft>>({})
  const [resultSummaryText, setResultSummaryText] = useState('{\n  "best_metric": 0.92,\n  "exported_files": ["weights.bin", "manifest.json"]\n}')
  const [actionMessage, setActionMessage] = useState<string | null>(null)

  async function loadDashboard(): Promise<void> {
    setLoading(true)
    setError(null)
    try {
      const [capabilities, annotationTasks, trainingTasks, modelArtifacts] = await Promise.all([
        fetchList<CapabilityItem>('/api/v1/capabilities'),
        fetchList<AnnotationTaskItem>('/api/v1/annotation-tasks'),
        fetchList<TrainingTaskItem>('/api/v1/training-tasks'),
        fetchList<ModelArtifactItem>('/api/v1/models'),
      ])
      setData({ capabilities, annotationTasks, trainingTasks, modelArtifacts })
      setSelectedAnnotationTaskId((current) => current ?? annotationTasks[0]?.task_id ?? null)
      setSelectedTrainingTaskId((current) => current ?? trainingTasks[0]?.task_id ?? null)
      setSelectedModelArtifactId((current) => current ?? modelArtifacts[0]?.artifact_id ?? null)
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : '加载数据失败')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    void loadDashboard()
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

  useEffect(() => {
    if (selectedTrainingTaskId == null) {
      setTrainingDetail(null)
      return
    }
    let disposed = false
    void request<TrainingTaskItem>(`/api/v1/training-tasks/${selectedTrainingTaskId}`).then((payload) => {
      if (!disposed) {
        setTrainingDetail(payload)
      }
    })
    const poll = window.setInterval(() => {
      void request<{ latest_logs: string[]; execution_plan: Record<string, unknown> | null; result_summary: Record<string, unknown> | null; status: string; task_id: number; log_path: string | null }>(
        `/api/v1/training-tasks/${selectedTrainingTaskId}/logs`,
      ).then((snapshot) => {
        if (!disposed) {
          setTrainingDetail((current) =>
            current == null
              ? null
              : {
                  ...current,
                  status: snapshot.status,
                  log_path: snapshot.log_path,
                  latest_logs: snapshot.latest_logs,
                  execution_plan: snapshot.execution_plan,
                  result_summary: snapshot.result_summary,
                },
          )
        }
      })
    }, 5000)
    return () => {
      disposed = true
      window.clearInterval(poll)
    }
  }, [selectedTrainingTaskId])

  useEffect(() => {
    if (selectedModelArtifactId == null) {
      setModelDetail(null)
      return
    }
    void request<ModelArtifactItem>(`/api/v1/models/${selectedModelArtifactId}`).then(setModelDetail)
  }, [selectedModelArtifactId])

  const overviewCards = useMemo(
    () => [
      {
        title: '能力与数据集',
        status: `${data.capabilities.length} 个能力`,
        description: '能力已补齐任务类型、标注 schema 与统一模板脚手架视图。',
      },
      {
        title: '标注台',
        status: `${data.annotationTasks.length} 个任务`,
        description: '支持按任务类型执行分层标注与批量提交。',
      },
      {
        title: '训练台',
        status: `${data.trainingTasks.length} 个任务`,
        description: '支持训练输入适配、执行计划、模板 bundle 与导出追踪。',
      },
      {
        title: '模型管理',
        status: `${data.modelArtifacts.length} 个版本`,
        description: '统一展示 manifest、runtime 契约与交付元数据。',
      },
    ],
    [data],
  )

  async function refreshListsPreserveSelection(): Promise<void> {
    await loadDashboard()
    if (selectedAnnotationTaskId != null) {
      const payload = await request<AnnotationTaskItem>(`/api/v1/annotation-tasks/${selectedAnnotationTaskId}`)
      setAnnotationDetail(payload)
    }
    if (selectedTrainingTaskId != null) {
      const payload = await request<TrainingTaskItem>(`/api/v1/training-tasks/${selectedTrainingTaskId}`)
      setTrainingDetail(payload)
    }
    if (selectedModelArtifactId != null) {
      const payload = await request<ModelArtifactItem>(`/api/v1/models/${selectedModelArtifactId}`)
      setModelDetail(payload)
    }
  }

  async function saveAnnotationSample(sampleId: string, markSubmitted: boolean): Promise<void> {
    if (annotationDetail == null) return
    const draft = annotationDrafts[sampleId]
    let payload: Record<string, unknown> | null
    try {
      payload = buildAnnotationPayload(sampleId, draft, annotationDetail.task_type)
    } catch (error) {
      setActionMessage(error instanceof Error ? error.message : '标注内容格式错误')
      return
    }
    if (payload == null) {
      setActionMessage(`样本 ${sampleId} 缺少 ${annotationDetail.task_type} 所需字段`)
      return
    }
    await request<AnnotationTaskItem>(`/api/v1/annotation-tasks/${annotationDetail.task_id}/samples`, {
      method: 'PATCH',
      body: JSON.stringify({
        annotations: [payload],
        mark_submitted: markSubmitted,
      }),
    })
    setActionMessage(markSubmitted ? `样本 ${sampleId} 已提交` : `样本 ${sampleId} 已保存`)
    await refreshListsPreserveSelection()
  }

  async function submitAnnotatedSamples(): Promise<void> {
    if (annotationDetail == null) return
    let annotations: Record<string, unknown>[]
    try {
      annotations = Object.entries(annotationDrafts)
        .map(([sampleId, draft]) => buildAnnotationPayload(sampleId, draft, annotationDetail.task_type))
        .filter((item): item is Record<string, unknown> => item != null)
    } catch (error) {
      setActionMessage(error instanceof Error ? error.message : '标注内容格式错误')
      return
    }
    await request<AnnotationTaskItem>(`/api/v1/annotation-tasks/${annotationDetail.task_id}/submit`, {
      method: 'POST',
      body: JSON.stringify({ annotations }),
    })
    setActionMessage(`已批量提交 ${annotations.length} 个样本`)
    await refreshListsPreserveSelection()
  }

  async function prepareTraining(): Promise<void> {
    if (trainingDetail == null) return
    await request<TrainingTaskItem>(`/api/v1/training-tasks/${trainingDetail.task_id}/prepare`, { method: 'POST' })
    setActionMessage('已更新训练执行计划')
    await refreshListsPreserveSelection()
  }

  async function executeTraining(): Promise<void> {
    if (trainingDetail == null) return
    await request<TrainingTaskItem>(`/api/v1/training-tasks/${trainingDetail.task_id}/execute`, { method: 'POST' })
    setActionMessage('已执行训练任务并生成导出产物')
    await refreshListsPreserveSelection()
  }

  async function recordTrainingResult(): Promise<void> {
    if (trainingDetail == null) return
    const resultSummary = JSON.parse(resultSummaryText) as Record<string, unknown>
    await request<TrainingTaskItem>(`/api/v1/training-tasks/${trainingDetail.task_id}/result`, {
      method: 'POST',
      body: JSON.stringify({ result_summary: resultSummary }),
    })
    setActionMessage('已写入训练结果摘要')
    await refreshListsPreserveSelection()
  }

  return (
    <div className="page">
      <header className="hero">
        <div>
          <p className="eyebrow">北京爱知之星科技股份有限公司（Agile Star）</p>
          <h1>ai-train 专业管理台</h1>
          <p className="hero-text">
            面向内部工业化训练流程，统一收口任务类型化标注 schema、训练输入适配、模板脚手架与模型运行契约。
          </p>
        </div>
        <div className="hero-panel">
          <div>
            <span className="label">当前阶段</span>
            <strong>T12 / T13 / T14 / T15 / T16 执行中</strong>
          </div>
          <div>
            <span className="label">默认端口</span>
            <strong>26000</strong>
          </div>
          <div>
            <span className="label">管理重点</span>
            <strong>任务类型 schema / 训练适配 / 模板脚手架 / runtime 契约</strong>
          </div>
        </div>
      </header>

      <main className="content">
        <section className="panel">
          <div className="section-header">
            <h2>跨模块联调导航</h2>
            <span className="badge badge-muted">R7 第二轮</span>
          </div>
          <div className="module-grid">
            {workspace.moduleLinks.map((item) => (
              <a
                key={item.id}
                className={`module-link-card${item.isCurrent ? ' active' : ''}`}
                href={item.url}
              >
                <div className="module-link-header">
                  <strong>{item.title}</strong>
                  <span className="module-tag">{item.isCurrent ? '当前模块' : '联调入口'}</span>
                </div>
                <p>{item.summary}</p>
              </a>
            ))}
          </div>
          <ul className="module-checklist">
            {workspace.reviewItems.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </section>
        <section className="panel">
          <div className="section-header">
            <h2>总体联调复审</h2>
            <span className="badge">R7 已完成</span>
          </div>
          <div className="review-grid">
            {workspace.reviewSummary.map((item) => (
              <article key={item.title} className="review-card">
                <div className="module-link-header">
                  <h3>{item.title}</h3>
                  <span className="review-status">{item.status}</span>
                </div>
                <p>{item.detail}</p>
              </article>
            ))}
          </div>
          <p className="module-note">
            当前模块定位：{workspace.currentModule.title} / {workspace.currentModule.summary}
          </p>
        </section>
        <section className="panel">
          <div className="section-header">
            <h2>控制台总览</h2>
            <div className="toolbar">
              <div className="tab-list">
                {tabs.map((tab) => (
                  <button
                    key={tab}
                    className={`tab-button${activeTab === tab ? ' active' : ''}`}
                    onClick={() => setActiveTab(tab)}
                  >
                    {tab === 'overview' ? '概览' : tab === 'annotation' ? '标注台' : tab === 'training' ? '训练台' : '模型管理'}
                  </button>
                ))}
              </div>
              <button className="primary-button" onClick={() => void loadDashboard()}>
                刷新总览
              </button>
            </div>
          </div>
          {loading && <p className="info-text">正在加载 ai-train 最新数据...</p>}
          {error && <p className="error-text">数据加载失败：{error}</p>}
          {actionMessage && <p className="success-text">{actionMessage}</p>}
          <div className="card-grid">
            {overviewCards.map((card) => (
              <article key={card.title} className="card">
                <div className="card-header">
                  <h3>{card.title}</h3>
                  <span>{card.status}</span>
                </div>
                <p>{card.description}</p>
              </article>
            ))}
          </div>
        </section>

        {activeTab === 'overview' && (
          <section className="panel">
            <div className="data-grid">
              <article className="sub-panel">
                <h3>能力列表</h3>
                <div className="table-wrap">
                  <table>
                    <thead>
                      <tr>
                        <th>能力</th>
                        <th>任务类型</th>
                        <th>数据集</th>
                        <th>状态</th>
                      </tr>
                    </thead>
                    <tbody>
                      {data.capabilities.map((item) => (
                        <tr key={item.capability_name}>
                          <td>{item.display_name}</td>
                          <td>{item.task_type}</td>
                          <td><code>{item.dataset_path}</code></td>
                          <td>{item.dataset_status}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </article>
              <article className="sub-panel">
                <h3>交付收口提示</h3>
                <ul className="todo-list">
                  <li>标注任务已按任务类型暴露 annotation schema。</li>
                  <li>训练任务已补齐 training_input / template_bundle / export_dir 追踪。</li>
                  <li>模型 manifest 已补齐 task_type / runtime_contract / delivery_metadata。</li>
                </ul>
              </article>
            </div>
          </section>
        )}

        {activeTab === 'annotation' && (
          <section className="panel split-layout">
            <article className="sub-panel list-panel">
              <h3>标注任务</h3>
              <div className="list-stack">
                {data.annotationTasks.map((task) => (
                  <button
                    key={task.task_id}
                    className={`list-item-button${selectedAnnotationTaskId === task.task_id ? ' active' : ''}`}
                    onClick={() => setSelectedAnnotationTaskId(task.task_id)}
                  >
                    <strong>{task.task_name}</strong>
                    <span>{task.capability_name}</span>
                    <span>{task.labeled_count}/{task.sample_total}</span>
                  </button>
                ))}
              </div>
            </article>
            <article className="sub-panel detail-panel">
              <div className="section-header">
                <h3>样本级标注台</h3>
                <button className="primary-button" onClick={() => void submitAnnotatedSamples()} disabled={annotationDetail == null}>
                  批量提交已填写样本
                </button>
              </div>
              {annotationDetail == null ? (
                <p className="info-text">请选择标注任务。</p>
              ) : (
                <>
                  <p className="meta-text">
                    任务状态：<strong>{annotationDetail.status}</strong> · 任务类型：
                    <strong>{annotationDetail.task_type}</strong> · 完成度：
                    {Math.round((annotationDetail.completion_ratio ?? 0) * 100)}%
                  </p>
                  <pre className="json-box">{JSON.stringify(annotationDetail.annotation_schema ?? {}, null, 2)}</pre>
                  <div className="sample-grid">
                    {(annotationDetail.sample_items ?? []).map((sample) => (
                      <div key={sample.sample_id} className="sample-card">
                        <div className="card-header">
                          <strong>{sample.sample_id}</strong>
                          <span>{sample.status}</span>
                        </div>
                        {annotationDetail.task_type === 'classification' && (
                          <>
                            <label>
                              标签
                              <input
                                value={annotationDrafts[sample.sample_id]?.label ?? ''}
                                onChange={(event) =>
                                  setAnnotationDrafts((current) => ({
                                    ...current,
                                    [sample.sample_id]: {
                                      ...(current[sample.sample_id] ?? extractDraft(sample)),
                                      label: event.target.value,
                                    },
                                  }))
                                }
                              />
                            </label>
                            <label>
                              attributes(JSON)
                              <textarea
                                rows={3}
                                value={annotationDrafts[sample.sample_id]?.attributesJson ?? '{}'}
                                onChange={(event) =>
                                  setAnnotationDrafts((current) => ({
                                    ...current,
                                    [sample.sample_id]: {
                                      ...(current[sample.sample_id] ?? extractDraft(sample)),
                                      attributesJson: event.target.value,
                                    },
                                  }))
                                }
                              />
                            </label>
                          </>
                        )}
                        {annotationDetail.task_type === 'detection' && (
                          <label>
                            objects(JSON)
                            <textarea
                              rows={5}
                              value={annotationDrafts[sample.sample_id]?.objectsJson ?? '[]'}
                              onChange={(event) =>
                                setAnnotationDrafts((current) => ({
                                  ...current,
                                  [sample.sample_id]: {
                                    ...(current[sample.sample_id] ?? extractDraft(sample)),
                                    objectsJson: event.target.value,
                                  },
                                }))
                              }
                            />
                          </label>
                        )}
                        {annotationDetail.task_type === 'ocr' && (
                          <>
                            <label>
                              text
                              <textarea
                                rows={3}
                                value={annotationDrafts[sample.sample_id]?.text ?? ''}
                                onChange={(event) =>
                                  setAnnotationDrafts((current) => ({
                                    ...current,
                                    [sample.sample_id]: {
                                      ...(current[sample.sample_id] ?? extractDraft(sample)),
                                      text: event.target.value,
                                    },
                                  }))
                                }
                              />
                            </label>
                            <label>
                              regions(JSON)
                              <textarea
                                rows={4}
                                value={annotationDrafts[sample.sample_id]?.regionsJson ?? '[]'}
                                onChange={(event) =>
                                  setAnnotationDrafts((current) => ({
                                    ...current,
                                    [sample.sample_id]: {
                                      ...(current[sample.sample_id] ?? extractDraft(sample)),
                                      regionsJson: event.target.value,
                                    },
                                  }))
                                }
                              />
                            </label>
                          </>
                        )}
                        {annotationDetail.task_type === 'structured_extraction' && (
                          <>
                            <label>
                              fields(JSON)
                              <textarea
                                rows={4}
                                value={annotationDrafts[sample.sample_id]?.fieldsJson ?? '{}'}
                                onChange={(event) =>
                                  setAnnotationDrafts((current) => ({
                                    ...current,
                                    [sample.sample_id]: {
                                      ...(current[sample.sample_id] ?? extractDraft(sample)),
                                      fieldsJson: event.target.value,
                                    },
                                  }))
                                }
                              />
                            </label>
                            <label>
                              confidence(JSON)
                              <textarea
                                rows={3}
                                value={annotationDrafts[sample.sample_id]?.confidenceJson ?? '{}'}
                                onChange={(event) =>
                                  setAnnotationDrafts((current) => ({
                                    ...current,
                                    [sample.sample_id]: {
                                      ...(current[sample.sample_id] ?? extractDraft(sample)),
                                      confidenceJson: event.target.value,
                                    },
                                  }))
                                }
                              />
                            </label>
                          </>
                        )}
                        <label>
                          备注
                          <textarea
                            rows={3}
                            value={annotationDrafts[sample.sample_id]?.note ?? ''}
                            onChange={(event) =>
                              setAnnotationDrafts((current) => ({
                                ...current,
                                [sample.sample_id]: {
                                  ...(current[sample.sample_id] ?? extractDraft(sample)),
                                  note: event.target.value,
                                },
                              }))
                            }
                          />
                        </label>
                        <div className="button-row">
                          <button onClick={() => void saveAnnotationSample(sample.sample_id, false)}>保存</button>
                          <button onClick={() => void saveAnnotationSample(sample.sample_id, true)}>提交当前样本</button>
                        </div>
                      </div>
                    ))}
                  </div>
                </>
              )}
            </article>
          </section>
        )}

        {activeTab === 'training' && (
          <section className="panel split-layout">
            <article className="sub-panel list-panel">
              <h3>训练任务</h3>
              <div className="list-stack">
                {data.trainingTasks.map((task) => (
                  <button
                    key={task.task_id}
                    className={`list-item-button${selectedTrainingTaskId === task.task_id ? ' active' : ''}`}
                    onClick={() => setSelectedTrainingTaskId(task.task_id)}
                    >
                      <strong>{task.task_name}</strong>
                      <span>{task.task_type} / {task.backend_type}</span>
                      <span>{task.status}</span>
                    </button>
                ))}
              </div>
            </article>
            <article className="sub-panel detail-panel">
              <div className="section-header">
                <h3>训练台</h3>
                <div className="button-row">
                  <button onClick={() => void prepareTraining()} disabled={trainingDetail == null}>生成执行计划</button>
                  <button onClick={() => void executeTraining()} disabled={trainingDetail == null}>执行训练并导出</button>
                  <button onClick={() => void refreshListsPreserveSelection()} disabled={trainingDetail == null}>刷新日志</button>
                </div>
              </div>
              {trainingDetail == null ? (
                <p className="info-text">请选择训练任务。</p>
              ) : (
                <>
                  <p className="meta-text">
                    状态：<strong>{trainingDetail.status}</strong> · 任务类型：
                    <strong>{trainingDetail.task_type}</strong> · 后端：
                    <strong>{trainingDetail.backend_type}</strong> · 重试：
                    <strong>{trainingDetail.retry_count}</strong>
                  </p>
                  <ul className="todo-list">
                    <li>training_input：{trainingDetail.training_input_path ?? '尚未生成'}</li>
                    <li>template_bundle：{trainingDetail.template_bundle_path ?? '尚未生成'}</li>
                    <li>export_dir：{trainingDetail.export_dir ?? '尚未导出'}</li>
                  </ul>
                  <div className="data-grid compact-grid">
                    <div className="sub-card">
                      <h4>最近日志</h4>
                      <pre className="log-box">{(trainingDetail.latest_logs ?? []).join('\n') || '暂无日志'}</pre>
                    </div>
                    <div className="sub-card">
                      <h4>执行计划</h4>
                      <pre className="json-box">
                        {JSON.stringify(trainingDetail.execution_plan ?? { message: '尚未生成执行计划' }, null, 2)}
                      </pre>
                    </div>
                  </div>
                  <div className="sub-card">
                    <div className="section-header">
                      <h4>训练结果回显</h4>
                      <button onClick={() => void recordTrainingResult()}>写入结果摘要</button>
                    </div>
                    <textarea rows={8} value={resultSummaryText} onChange={(event) => setResultSummaryText(event.target.value)} />
                    <pre className="json-box">
                      {JSON.stringify(trainingDetail.result_summary ?? { message: '尚未写入结果摘要' }, null, 2)}
                    </pre>
                  </div>
                </>
              )}
            </article>
          </section>
        )}

        {activeTab === 'model' && (
          <section className="panel split-layout">
            <article className="sub-panel list-panel">
              <h3>模型版本</h3>
              <div className="list-stack">
                {data.modelArtifacts.map((item) => (
                  <button
                    key={item.artifact_id}
                    className={`list-item-button${selectedModelArtifactId === item.artifact_id ? ' active' : ''}`}
                    onClick={() => setSelectedModelArtifactId(item.artifact_id)}
                    >
                      <strong>{item.model_version}</strong>
                      <span>{item.capability_name}</span>
                      <span>{item.task_type} / {item.backend_type}</span>
                    </button>
                ))}
              </div>
            </article>
            <article className="sub-panel detail-panel">
              <h3>模型包标准化预览</h3>
              {modelDetail == null ? (
                <p className="info-text">请选择模型版本。</p>
              ) : (
                <div className="data-grid compact-grid">
                  <div className="sub-card">
                    <h4>Manifest</h4>
                    <pre className="json-box">{JSON.stringify(modelDetail.manifest_preview ?? {}, null, 2)}</pre>
                  </div>
                  <div className="sub-card">
                    <h4>交付元数据</h4>
                    <pre className="json-box">{JSON.stringify(modelDetail.delivery_metadata ?? {}, null, 2)}</pre>
                  </div>
                  <div className="sub-card">
                    <h4>Runtime 契约</h4>
                    <pre className="json-box">{JSON.stringify(modelDetail.runtime_contract ?? {}, null, 2)}</pre>
                  </div>
                </div>
              )}
            </article>
          </section>
        )}
      </main>
    </div>
  )
}

export default App
