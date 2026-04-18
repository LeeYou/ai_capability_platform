import { useEffect, useMemo, useState } from 'react'
import './App.css'
import '../../../frontend-common/src/r7Workspace.css'
import { WorkspaceShell } from '../../../frontend-common/src/workspaceShell.tsx'
import { buildR7Workspace } from '../../../frontend-common/src/r7Workspace.ts'
import { useRequest } from '../../../frontend-common/src/useRequest.ts'
import { WorkspaceFeedback } from '../../../frontend-common/src/workspaceFeedback.tsx'
import { statusTone } from '../../../frontend-common/src/statusTone.ts'
import { RiskBanner } from '../../../frontend-common/src/riskBanner.tsx'
import type { RiskItem } from '../../../frontend-common/src/riskBanner.tsx'
import { ListDetailLayout } from '../../../frontend-common/src/listDetailLayout.tsx'
import type { ListItem } from '../../../frontend-common/src/listDetailLayout.tsx'

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
  execution_mode: string
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
  const { loading, error, actionMessage, request, fetchList, setLoading, setError, setActionMessage } = useRequest(apiBaseUrl, { initialLoading: true })
  const [activeTab, setActiveTab] = useState<TabKey>('overview')
  const [data, setData] = useState<DashboardData>(initialData)
  const [selectedAnnotationTaskId, setSelectedAnnotationTaskId] = useState<number | null>(null)
  const [selectedTrainingTaskId, setSelectedTrainingTaskId] = useState<number | null>(null)
  const [selectedModelArtifactId, setSelectedModelArtifactId] = useState<number | null>(null)
  const [annotationDetail, setAnnotationDetail] = useState<AnnotationTaskItem | null>(null)
  const [trainingDetail, setTrainingDetail] = useState<TrainingTaskItem | null>(null)
  const [modelDetail, setModelDetail] = useState<ModelArtifactItem | null>(null)
  const [annotationDrafts, setAnnotationDrafts] = useState<Record<string, AnnotationDraft>>({})

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
    void request<TrainingTaskItem>(`/api/v1/training-tasks/${selectedTrainingTaskId}`).then(setTrainingDetail)
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
      { title: '能力目录', value: data.capabilities.length, description: '已接入的任务类型能力与数据集绑定。' },
      { title: '标注任务', value: data.annotationTasks.length, description: '样本级编辑、批量保存与提交的入口。' },
      { title: '训练任务', value: data.trainingTasks.length, description: '训练执行、日志与结果摘要的统一视图。' },
      { title: '模型资产', value: data.modelArtifacts.length, description: '可直接送测的模型卡片与 manifest 契约。' },
    ],
    [data],
  )

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
      await loadDashboard()
    } catch (loadError) {
      setActionMessage(loadError instanceof Error ? loadError.message : '保存标注失败')
    }
  }

  async function handleTrainingAction(path: 'prepare' | 'execute'): Promise<void> {
    if (selectedTrainingTaskId == null) return
    try {
      await request(`/api/v1/training-tasks/${selectedTrainingTaskId}/${path}`, {
        method: 'POST',
      })
      setActionMessage(path === 'prepare' ? '训练工作区准备完成' : '训练执行已完成')
      await loadDashboard()
    } catch (loadError) {
      setActionMessage(loadError instanceof Error ? loadError.message : '训练动作失败')
    }
  }

  return (
    <WorkspaceShell moduleId="ai-train" title="ai-train" subtitle="统一研发工作台">
      <header className="hero">
        <div className="hero-text">
          <p className="eyebrow">北京爱知之星科技股份有限公司（Agile Star）</p>
          <h1>ai-train 研发训练工作台</h1>
          <p>
            在现有真实标注、训练执行与模型产物基础上，把页面收口为“首页总览 / 标注工作台 /
            训练工作台 / 模型资产台”四段式研发入口，强化对象链路与送测动作。
          </p>
          <div className="workspace-action-row">
            {workspace.nextModule && (
              <a className="workspace-action-chip" href={workspace.nextModule.url}>
                送测到 {workspace.nextModule.shortTitle}
              </a>
            )}
          </div>
        </div>
        <div className="hero-panel">
          <div><span className="label">服务端口</span><strong>26000</strong></div>
          <div><span className="label">当前重点</span><strong>标注 / 训练 / 模型资产一体化</strong></div>
          <div><span className="label">任务类型</span><strong>classification / detection / ocr / structured</strong></div>
        </div>
      </header>

      <main className="content">
        <section className="panel">
          <div className="section-header">
            <div>
              <h2>首页概览</h2>
              <p>围绕待标注、待训练、待送测对象组织研发首页。</p>
            </div>
            <span className="badge">T17-T20</span>
          </div>
          <WorkspaceFeedback
            loading={loading}
            loadingMessage="正在加载研发工作台数据..."
            error={error}
            actionMessage={actionMessage}
          />
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
            <RiskBanner
              title="待处理标注任务"
              items={data.annotationTasks.slice(0, 4).map((item): RiskItem => ({
                id: item.task_id,
                label: item.task_name,
                meta: [item.capability_name, `${item.labeled_count}/${item.sample_total}`],
                status: item.status,
              }))}
              emptyMessage="当前没有待处理标注任务。"
              selectedId={selectedAnnotationTaskId}
              onSelect={(id) => {
                setSelectedAnnotationTaskId(id as number)
                setActiveTab('annotation')
              }}
            />
            <RiskBanner
              title="待送测模型"
              items={data.modelArtifacts.slice(0, 4).map((item): RiskItem => ({
                id: item.artifact_id,
                label: item.capability_name,
                meta: [item.model_version, item.backend_type],
                status: item.status,
              }))}
              emptyMessage="当前没有待送测模型。"
              selectedId={selectedModelArtifactId}
              onSelect={(id) => {
                setSelectedModelArtifactId(id as number)
                setActiveTab('model')
              }}
            />
          </div>
        </section>

        <section className="panel">
          <div className="toolbar">
            <div>
              <h2>研发工作台</h2>
              <p>把样本、训练任务与模型资产组织成连续作业流。</p>
            </div>
            <div className="tab-list">
              {tabs.map((tab) => (
                <button
                  key={tab}
                  className={`tab-button${activeTab === tab ? ' active' : ''}`}
                  onClick={() => setActiveTab(tab)}
                  type="button"
                >
                  {tab === 'overview' && '总览'}
                  {tab === 'annotation' && '标注工作台'}
                  {tab === 'training' && '训练工作台'}
                  {tab === 'model' && '模型资产'}
                </button>
              ))}
            </div>
          </div>

          {activeTab === 'overview' && (
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
                        className={`workspace-list-item${selectedTrainingTaskId === item.task_id ? ' active' : ''}`}
                        onClick={() => {
                          setSelectedTrainingTaskId(item.task_id)
                          setActiveTab('training')
                        }}
                        type="button"
                      >
                        <strong>{item.task_name}</strong>
                        <div className="workspace-meta-row">
                          <span>{item.capability_name}</span>
                          <span>{item.framework}</span>
                          <span>{item.execution_mode}</span>
                          <span className={`status-pill ${statusTone(item.status)}`}>{item.status}</span>
                        </div>
                      </button>
                    ))}
                  </div>
                </article>
              </div>
            </div>
          )}

          {activeTab === 'annotation' && (
            <div className="workspace-panel-grid">
              <div className="workspace-stack">
                <article className="workspace-note-block">
                  <div className="section-header">
                    <h3>标注任务列表</h3>
                    <span className="badge badge-muted">T17</span>
                  </div>
                  <div className="workspace-list">
                    {data.annotationTasks.map((item) => (
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
          )}

          {activeTab === 'training' && (
            <ListDetailLayout
              listTitle="训练任务列表"
              listBadge="T18"
              items={data.trainingTasks.map((item): ListItem => ({
                id: item.task_id,
                label: item.task_name,
                meta: [item.capability_name, item.framework, item.execution_mode],
                status: item.status,
              }))}
              selectedId={selectedTrainingTaskId}
              onSelect={(id) => setSelectedTrainingTaskId(id as number)}
              detailTitle="训练执行视图"
              detailStatus={trainingDetail?.status}
              emptyMessage="请选择训练任务查看日志与阶段状态。"
              detail={trainingDetail ? (
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
                      <span>执行模式</span>
                      <strong>{trainingDetail.execution_mode}</strong>
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
              ) : null}
            />
          )}

          {activeTab === 'model' && (
            <ListDetailLayout
              listTitle="模型资产列表"
              listBadge="T19-T20"
              items={data.modelArtifacts.map((item): ListItem => ({
                id: item.artifact_id,
                label: item.capability_name,
                meta: [item.model_version, item.backend_type],
                status: item.status,
              }))}
              selectedId={selectedModelArtifactId}
              onSelect={(id) => setSelectedModelArtifactId(id as number)}
              detailTitle="模型卡片与送测动作"
              detailStatus={modelDetail?.status}
              emptyMessage="请选择模型查看详情。"
              detail={modelDetail ? (
                <>
                  <div className="workspace-kpi-grid">
                    <article className="workspace-kpi-card">
                      <span>模型版本</span>
                      <strong>{modelDetail.model_version}</strong>
                    </article>
                    <article className="workspace-kpi-card">
                      <span>来源训练任务</span>
                      <strong>{modelDetail.source_training_task_id}</strong>
                    </article>
                    <article className="workspace-kpi-card">
                      <span>后端</span>
                      <strong>{modelDetail.backend_type}</strong>
                    </article>
                  </div>
                  <div className="workspace-action-row">
                    {workspace.nextModule && (
                      <a className="workspace-action-chip" href={workspace.nextModule.url}>
                        送测到 {workspace.nextModule.shortTitle}
                      </a>
                    )}
                  </div>
                  <pre className="workspace-code-block">{JSON.stringify(modelDetail.manifest_preview ?? {}, null, 2)}</pre>
                  <pre className="workspace-code-block">{JSON.stringify(modelDetail.runtime_contract ?? {}, null, 2)}</pre>
                  <pre className="workspace-code-block">{JSON.stringify(modelDetail.delivery_metadata ?? {}, null, 2)}</pre>
                </>
              ) : null}
            />
          )}
        </section>
      </main>
    </WorkspaceShell>
  )
}

export default App
