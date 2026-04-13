import { useEffect, useMemo, useState } from 'react'
import type {
  RemoteModelItem,
  BatchTestForm,
  BaselineForm,
  TestTaskItem,
  TestTaskDetail,
  PerformanceBaselineItem,
} from '../types'
import { fetchList, request, statusTone, parseBatchCases } from '../api'
import { averageDuration, buildBaselineSummary, buildBatchChecklist, buildCaseRiskItems, clampScore, scoreTone } from '../enterprise'

const initialBatchForm: BatchTestForm = {
  capability_name: '',
  model_version: '',
  requested_backend: 'auto',
  timeout_seconds: '45',
  cases_text:
    'case-01|/data/ai_capability_platform/datasets/demo/case-01.json|\ncase-02|/data/ai_capability_platform/datasets/demo/case-02.json|',
}

const initialBaselineForm: BaselineForm = {
  capability_name: 'all',
  scenario_name: 'delivery-default',
  p95_max_ms: '5000',
  success_rate_min: '1',
  description: '交付验收默认基线',
}

export function BatchTestPage() {
  const [models, setModels] = useState<RemoteModelItem[]>([])
  const [tasks, setTasks] = useState<TestTaskItem[]>([])
  const [baselines, setBaselines] = useState<PerformanceBaselineItem[]>([])
  const [batchForm, setBatchForm] = useState<BatchTestForm>(initialBatchForm)
  const [baselineForm, setBaselineForm] = useState<BaselineForm>(initialBaselineForm)
  const [selectedTaskId, setSelectedTaskId] = useState<number | null>(null)
  const [selectedTask, setSelectedTask] = useState<TestTaskDetail | null>(null)
  const [actionMessage, setActionMessage] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  async function loadData(): Promise<void> {
    setLoading(true)
    try {
      const [modelsRes, tasksRes, baselineRes] = await Promise.all([
        fetchList<RemoteModelItem>('/api/v1/remote-models'),
        fetchList<TestTaskItem>('/api/v1/test-tasks'),
        fetchList<PerformanceBaselineItem>('/api/v1/performance-baselines'),
      ])
      setModels(modelsRes.items)
      setTasks(tasksRes.items.filter((item) => item.task_type === 'batch'))
      setBaselines(baselineRes.items)
      setSelectedTaskId((current) => current ?? tasksRes.items.find((item) => item.task_type === 'batch')?.task_id ?? null)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    void loadData()
  }, [])

  useEffect(() => {
    const firstModel = models[0]
    if (!firstModel) return
    setBatchForm((current) => ({
      ...current,
      capability_name: current.capability_name || firstModel.capability_name,
      model_version: current.model_version || firstModel.model_version,
    }))
    setBaselineForm((current) => ({
      ...current,
      capability_name: current.capability_name || firstModel.capability_name,
    }))
  }, [models])

  useEffect(() => {
    if (selectedTaskId == null) {
      setSelectedTask(null)
      return
    }
    void request<TestTaskDetail>(`/api/v1/test-tasks/${selectedTaskId}`).then(setSelectedTask).catch(() => {
      setSelectedTask(null)
    })
  }, [selectedTaskId])

  async function handleCreateBatchTest(): Promise<void> {
    try {
      setActionMessage('正在创建批量测试任务...')
      const created = await request<TestTaskDetail>('/api/v1/batch-tests', {
        method: 'POST',
        body: JSON.stringify({
          capability_name: batchForm.capability_name,
          model_version: batchForm.model_version,
          requested_backend: batchForm.requested_backend,
          timeout_seconds: Number(batchForm.timeout_seconds),
          cases: parseBatchCases(batchForm.cases_text),
        }),
      })
      setSelectedTaskId(created.task_id)
      setActionMessage(`批量测试任务 #${created.task_id} 已创建`)
      await loadData()
    } catch (loadError) {
      setActionMessage(loadError instanceof Error ? loadError.message : '创建批量测试失败')
    }
  }

  async function handleSaveBaseline(): Promise<void> {
    try {
      setActionMessage('正在保存性能基线...')
      await request<PerformanceBaselineItem>('/api/v1/performance-baselines', {
        method: 'POST',
        body: JSON.stringify({
          capability_name: baselineForm.capability_name,
          scenario_name: baselineForm.scenario_name,
          p95_max_ms: Number(baselineForm.p95_max_ms),
          success_rate_min: Number(baselineForm.success_rate_min),
          description: baselineForm.description,
        }),
      })
      setActionMessage('性能基线已更新')
      await loadData()
    } catch (loadError) {
      setActionMessage(loadError instanceof Error ? loadError.message : '保存基线失败')
    }
  }

  const filteredModels = useMemo(
    () => models.filter((item) => item.capability_name === batchForm.capability_name),
    [batchForm.capability_name, models],
  )
  const baselineSummary = useMemo(() => buildBaselineSummary(baselines), [baselines])
  const checklist = useMemo(() => buildBatchChecklist(selectedTask), [selectedTask])
  const readinessScore = clampScore(checklist.filter((item) => item.done).length / Math.max(1, checklist.length) * 100)
  const riskItems = useMemo(() => buildCaseRiskItems(selectedTask?.cases ?? []), [selectedTask?.cases])
  const avgDuration = averageDuration(selectedTask?.cases ?? [])

  return (
    <div className="page-container">
      {loading && <p className="info-text">正在加载...</p>}
      {actionMessage && <p className="success-text">{actionMessage}</p>}

      <section className="panel">
        <div className="section-header">
          <div>
            <h2>批量测试工作台</h2>
            <p>对齐参考工程中的批量测试与精度评估主流程，并补齐企业级的任务治理、失败样本分析和基线管理视图。</p>
          </div>
          <span className="badge">TT20-TT24</span>
        </div>
        <div className="enterprise-hero-grid">
          <article className={`enterprise-score-card tone-${scoreTone(readinessScore)}`}>
            <span>批测发布成熟度</span>
            <strong>{readinessScore}</strong>
            <p>综合任务创建、失败样本分析、报告沉淀与基线治理四个维度。</p>
          </article>
          <article className="enterprise-note-card">
            <strong>本页重点</strong>
            <p>让批量测试不只是“跑一批 case”，而是可被团队值守、复盘和沉淀阈值模板的工作台。</p>
          </article>
        </div>
      </section>

      <section className="panel">
        <div className="workspace-panel-grid">
          <div className="workspace-stack">
            <article className="workspace-note-block">
              <div className="section-header">
                <h3>批量测试向导</h3>
                <span className="badge badge-muted">任务创建</span>
              </div>
              <div className="workspace-form-grid">
                <label className="workspace-field">
                  能力
                  <select
                    value={batchForm.capability_name}
                    onChange={(event) => setBatchForm((current) => ({
                      ...current,
                      capability_name: event.target.value,
                      model_version: models.find((item) => item.capability_name === event.target.value)?.model_version ?? '',
                    }))}
                  >
                    {Array.from(new Set(models.map((item) => item.capability_name))).map((item) => (
                      <option key={item} value={item}>{item}</option>
                    ))}
                  </select>
                </label>
                <label className="workspace-field">
                  模型版本
                  <select
                    value={batchForm.model_version}
                    onChange={(event) => setBatchForm((current) => ({ ...current, model_version: event.target.value }))}
                  >
                    {filteredModels.map((item) => (
                      <option key={item.model_version} value={item.model_version}>{item.model_version}</option>
                    ))}
                  </select>
                </label>
                <label className="workspace-field">
                  后端
                  <select
                    value={batchForm.requested_backend}
                    onChange={(event) =>
                      setBatchForm((current) => ({
                        ...current,
                        requested_backend: event.target.value as BatchTestForm['requested_backend'],
                      }))
                    }
                  >
                    <option value="auto">auto</option>
                    <option value="gpu">gpu</option>
                    <option value="cpu">cpu</option>
                  </select>
                </label>
                <label className="workspace-field">
                  超时时间
                  <input value={batchForm.timeout_seconds} onChange={(event) => setBatchForm((current) => ({ ...current, timeout_seconds: event.target.value }))} />
                </label>
                <label className="workspace-field full-span">
                  用例清单（每行：名称|输入路径|期望输出）
                  <textarea rows={8} value={batchForm.cases_text} onChange={(event) => setBatchForm((current) => ({ ...current, cases_text: event.target.value }))} />
                </label>
              </div>
              <div className="workspace-action-row">
                <button className="action-button" onClick={() => void handleCreateBatchTest()} type="button">创建批量测试</button>
              </div>
            </article>

            <article className="workspace-note-block">
              <div className="section-header">
                <h3>基线治理</h3>
                <span className="badge badge-muted">性能 / 稳定性模板</span>
              </div>
              <div className="enterprise-stage-grid">
                {baselineSummary.map((item) => (
                  <article key={item.title} className={`enterprise-stage-card tone-${item.tone}`}>
                    <span>{item.title}</span>
                    <strong>{item.detail.split(' ')[0]}</strong>
                    <p>{item.detail}</p>
                  </article>
                ))}
              </div>
              <div className="workspace-form-grid">
                <label className="workspace-field">
                  能力
                  <input value={baselineForm.capability_name} onChange={(event) => setBaselineForm((current) => ({ ...current, capability_name: event.target.value }))} />
                </label>
                <label className="workspace-field">
                  场景
                  <input value={baselineForm.scenario_name} onChange={(event) => setBaselineForm((current) => ({ ...current, scenario_name: event.target.value }))} />
                </label>
                <label className="workspace-field">
                  P95 阈值
                  <input value={baselineForm.p95_max_ms} onChange={(event) => setBaselineForm((current) => ({ ...current, p95_max_ms: event.target.value }))} />
                </label>
                <label className="workspace-field">
                  最小成功率
                  <input value={baselineForm.success_rate_min} onChange={(event) => setBaselineForm((current) => ({ ...current, success_rate_min: event.target.value }))} />
                </label>
                <label className="workspace-field full-span">
                  说明
                  <textarea rows={3} value={baselineForm.description} onChange={(event) => setBaselineForm((current) => ({ ...current, description: event.target.value }))} />
                </label>
              </div>
              <div className="workspace-action-row">
                <button className="action-button" onClick={() => void handleSaveBaseline()} type="button">保存基线</button>
              </div>
            </article>
          </div>

          <div className="workspace-stack">
            <article className="workspace-note-block">
              <div className="section-header">
                <h3>批量任务与问题样本</h3>
                {selectedTask && <span className={`status-pill ${statusTone(selectedTask.status)}`}>{selectedTask.status}</span>}
              </div>
              <div className="workspace-list">
                {tasks.map((item) => (
                  <button
                    key={item.task_id}
                    className={`workspace-list-item${selectedTaskId === item.task_id ? ' active' : ''}`}
                    onClick={() => setSelectedTaskId(item.task_id)}
                    type="button"
                  >
                    <strong>任务 #{item.task_id}</strong>
                    <div className="workspace-meta-row">
                      <span>{item.capability_name}</span>
                      <span>{item.model_version}</span>
                      <span>{item.passed_cases}/{item.total_cases} 通过</span>
                      <span className={`status-pill ${statusTone(item.status)}`}>{item.status}</span>
                    </div>
                  </button>
                ))}
              </div>
              {!selectedTask ? (
                <div className="workspace-empty">请选择批量任务查看详情。</div>
              ) : (
                <>
                  <div className="workspace-kpi-grid">
                    <article className="workspace-kpi-card">
                      <span>通过率</span>
                      <strong>{Math.round((selectedTask.passed_cases / Math.max(1, selectedTask.total_cases)) * 100)}%</strong>
                    </article>
                    <article className="workspace-kpi-card">
                      <span>平均耗时</span>
                      <strong>{avgDuration} ms</strong>
                    </article>
                    <article className="workspace-kpi-card">
                      <span>失败样本</span>
                      <strong>{selectedTask.failed_cases}</strong>
                    </article>
                    <article className="workspace-kpi-card">
                      <span>实际后端</span>
                      <strong>{selectedTask.execution_backend ?? '-'}</strong>
                    </article>
                  </div>
                  <div className="enterprise-two-column">
                    <article className="enterprise-note-card">
                      <strong>批测门禁</strong>
                      <ul className="enterprise-checklist">
                        {checklist.map((item) => (
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
                      <strong>失败样本画像</strong>
                      <div className="enterprise-stack">
                        {riskItems.map((item) => (
                          <div key={item.title} className={`enterprise-inline-card tone-${item.tone}`}>
                            <strong>{item.title}</strong>
                            <p>{item.detail}</p>
                          </div>
                        ))}
                      </div>
                    </article>
                  </div>
                  <div className="workspace-table-wrap">
                    <table className="workspace-table">
                      <thead>
                        <tr>
                          <th>样本</th>
                          <th>结果</th>
                          <th>耗时</th>
                          <th>得分</th>
                          <th>Provider</th>
                        </tr>
                      </thead>
                      <tbody>
                        {selectedTask.cases.map((item) => (
                          <tr key={item.case_id}>
                            <td>{item.case_name}</td>
                            <td><span className={`status-pill ${statusTone(item.status)}`}>{item.status}</span></td>
                            <td>{item.duration_ms} ms</td>
                            <td>{item.score.toFixed(4)}</td>
                            <td>{item.provider ?? '-'}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                  <div className="enterprise-two-column">
                    <article className="enterprise-note-card">
                      <strong>失败样本回看</strong>
                      <div className="workspace-list">
                        {selectedTask.cases.filter((item) => item.status !== 'passed').map((item) => (
                          <div key={item.case_id} className="workspace-list-item static-item">
                            <strong>{item.case_name}</strong>
                            <div className="workspace-meta-row">
                              <span>{item.input_path}</span>
                              <span>{item.actual_output ?? '-'}</span>
                              <span>{item.duration_ms} ms</span>
                            </div>
                          </div>
                        ))}
                        {selectedTask.failed_cases === 0 && <div className="workspace-empty">当前无失败样本。</div>}
                      </div>
                    </article>
                    <article className="enterprise-note-card">
                      <strong>批测运营建议</strong>
                      <ul className="enterprise-list">
                        <li>先用批测识别共性失败样本，再决定是否回流 ai-train。</li>
                        <li>基线模板建议按 capability 持续细化，避免所有能力共用单一阈值。</li>
                        <li>通过批测后应尽快沉淀报告并推进生产验收。</li>
                      </ul>
                    </article>
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
