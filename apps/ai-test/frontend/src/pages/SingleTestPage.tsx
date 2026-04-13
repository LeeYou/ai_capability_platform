import { useEffect, useMemo, useState } from 'react'
import type {
  RemoteModelItem,
  SingleTestForm,
  TestTaskItem,
  TestTaskDetail,
} from '../types'
import { fetchList, request, statusTone } from '../api'
import { averageDuration, buildCaseRiskItems, buildModelVersionComparison, buildSingleChecklist, clampScore, scoreTone } from '../enterprise'

const initialSingleForm: SingleTestForm = {
  capability_name: '',
  model_version: '',
  requested_backend: 'auto',
  timeout_seconds: '30',
  case_name: '单张样例验证',
  input_path: '/data/ai_capability_platform/datasets/demo/input.json',
  expected_output: '',
}

export function SingleTestPage() {
  const [models, setModels] = useState<RemoteModelItem[]>([])
  const [tasks, setTasks] = useState<TestTaskItem[]>([])
  const [singleForm, setSingleForm] = useState<SingleTestForm>(initialSingleForm)
  const [selectedTaskId, setSelectedTaskId] = useState<number | null>(null)
  const [selectedTask, setSelectedTask] = useState<TestTaskDetail | null>(null)
  const [actionMessage, setActionMessage] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [compareTaskId, setCompareTaskId] = useState<number | null>(null)

  async function loadData(): Promise<void> {
    setLoading(true)
    try {
      const [modelsRes, tasksRes] = await Promise.all([
        fetchList<RemoteModelItem>('/api/v1/remote-models'),
        fetchList<TestTaskItem>('/api/v1/test-tasks'),
      ])
      setModels(modelsRes.items)
      setTasks(tasksRes.items)
      setSelectedTaskId((current) => current ?? tasksRes.items[0]?.task_id ?? null)
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
    setSingleForm((current) => ({
      ...current,
      capability_name: current.capability_name || firstModel.capability_name,
      model_version: current.model_version || firstModel.model_version,
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

  async function handleCreateSingleTest(): Promise<void> {
    try {
      setActionMessage('正在创建单测任务...')
      const created = await request<TestTaskDetail>('/api/v1/single-tests', {
        method: 'POST',
        body: JSON.stringify({
          capability_name: singleForm.capability_name,
          model_version: singleForm.model_version,
          requested_backend: singleForm.requested_backend,
          timeout_seconds: Number(singleForm.timeout_seconds),
          case: {
            case_name: singleForm.case_name,
            input_path: singleForm.input_path,
            expected_output: singleForm.expected_output || undefined,
          },
        }),
      })
      setSelectedTaskId(created.task_id)
      setActionMessage(`单测任务 #${created.task_id} 已创建`)
      await loadData()
    } catch (loadError) {
      setActionMessage(loadError instanceof Error ? loadError.message : '创建单测失败')
    }
  }

  const filteredModels = useMemo(
    () => models.filter((item) => item.capability_name === singleForm.capability_name),
    [models, singleForm.capability_name],
  )
  const selectedModel = useMemo(
    () => models.find((item) => item.capability_name === singleForm.capability_name && item.model_version === singleForm.model_version) ?? null,
    [models, singleForm.capability_name, singleForm.model_version],
  )
  const comparableTasks = useMemo(
    () =>
      tasks.filter(
        (item) =>
          selectedTask != null &&
          item.capability_name === selectedTask.capability_name &&
          item.task_id !== selectedTask.task_id &&
          item.task_type === 'single',
      ),
    [selectedTask, tasks],
  )
  const compareTask = useMemo(
    () => comparableTasks.find((item) => item.task_id === compareTaskId) ?? comparableTasks[0] ?? null,
    [comparableTasks, compareTaskId],
  )
  const comparisonRows = useMemo(
    () => (selectedTask && compareTask ? buildModelVersionComparison(selectedTask, compareTask) : []),
    [compareTask, selectedTask],
  )
  const checklist = useMemo(() => buildSingleChecklist(selectedTask, compareTask), [compareTask, selectedTask])
  const readinessScore = clampScore(checklist.filter((item) => item.done).length / Math.max(1, checklist.length) * 100)
  const caseRisks = useMemo(() => buildCaseRiskItems(selectedTask?.cases ?? []), [selectedTask?.cases])
  const currentCase = selectedTask?.cases[0] ?? null
  const averageMs = averageDuration(selectedTask?.cases ?? [])

  return (
    <div className="page-container">
      {loading && <p className="info-text">正在加载...</p>}
      {actionMessage && <p className="success-text">{actionMessage}</p>}

      <section className="panel">
        <div className="section-header">
          <div>
            <h2>单样本测试工作台</h2>
            <p>按“选择能力 → 配置样本 → 执行诊断 → 历史版本对比”的方式，拉齐参考工程的单样本测试与版本对比结构。</p>
          </div>
          <span className="badge">TT20-TT24</span>
        </div>
        <div className="enterprise-hero-grid">
          <article className={`enterprise-score-card tone-${scoreTone(readinessScore)}`}>
            <span>单测诊断成熟度</span>
            <strong>{readinessScore}</strong>
            <p>综合模型绑定、结果产出、问题定位与版本对比四个门禁。</p>
          </article>
          <article className="enterprise-note-card">
            <strong>本页重点</strong>
            <p>让单测页面不只是“发起一次请求”，而是对单样本结果做结构化诊断，并具备版本对比入口。</p>
          </article>
        </div>
      </section>

      <section className="panel">
        <div className="workspace-panel-grid">
          <div className="workspace-stack">
            <article className="workspace-note-block">
              <div className="section-header">
                <h3>单测向导</h3>
                <span className="badge badge-muted">能力 / 模型 / 样本</span>
              </div>
              <div className="workspace-form-grid">
                <label className="workspace-field">
                  能力
                  <select
                    value={singleForm.capability_name}
                    onChange={(event) => setSingleForm((current) => ({
                      ...current,
                      capability_name: event.target.value,
                      model_version: models.find((item) => item.capability_name === event.target.value)?.model_version ?? '',
                    }))}
                  >
                    {Array.from(new Set(models.map((item) => item.capability_name))).map((item) => (
                      <option key={item} value={item}>
                        {item}
                      </option>
                    ))}
                  </select>
                </label>
                <label className="workspace-field">
                  模型版本
                  <select
                    value={singleForm.model_version}
                    onChange={(event) => setSingleForm((current) => ({ ...current, model_version: event.target.value }))}
                  >
                    {filteredModels.map((item) => (
                      <option key={item.model_version} value={item.model_version}>
                        {item.model_version}
                      </option>
                    ))}
                  </select>
                </label>
                <label className="workspace-field">
                  执行后端
                  <select
                    value={singleForm.requested_backend}
                    onChange={(event) =>
                      setSingleForm((current) => ({
                        ...current,
                        requested_backend: event.target.value as SingleTestForm['requested_backend'],
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
                  <input value={singleForm.timeout_seconds} onChange={(event) => setSingleForm((current) => ({ ...current, timeout_seconds: event.target.value }))} />
                </label>
                <label className="workspace-field full-span">
                  用例名称
                  <input value={singleForm.case_name} onChange={(event) => setSingleForm((current) => ({ ...current, case_name: event.target.value }))} />
                </label>
                <label className="workspace-field full-span">
                  输入路径 / 数据集样本
                  <input value={singleForm.input_path} onChange={(event) => setSingleForm((current) => ({ ...current, input_path: event.target.value }))} />
                </label>
                <label className="workspace-field full-span">
                  期望输出
                  <textarea rows={4} value={singleForm.expected_output} onChange={(event) => setSingleForm((current) => ({ ...current, expected_output: event.target.value }))} />
                </label>
              </div>
              <div className="workspace-action-row">
                <button className="action-button" onClick={() => void handleCreateSingleTest()} type="button">发起单测</button>
              </div>
            </article>

            <article className="workspace-note-block">
              <div className="section-header">
                <h3>模型元数据</h3>
                <span className={`status-pill ${statusTone(selectedModel?.status ?? 'unknown')}`}>{selectedModel?.status ?? 'unknown'}</span>
              </div>
              {!selectedModel ? (
                <div className="workspace-empty">当前未匹配到模型元数据。</div>
              ) : (
                <div className="workspace-table-wrap">
                  <table className="workspace-table">
                    <tbody>
                      <tr><th>能力</th><td>{selectedModel.capability_name}</td><th>任务类型</th><td>{selectedModel.task_type ?? 'unknown'}</td></tr>
                      <tr><th>版本</th><td>{selectedModel.model_version}</td><th>训练任务</th><td>{selectedModel.source_training_task_id}</td></tr>
                      <tr><th>模型目录</th><td colSpan={3}><code>{selectedModel.artifact_path}</code></td></tr>
                      <tr><th>Manifest</th><td colSpan={3}><code>{selectedModel.manifest_path}</code></td></tr>
                    </tbody>
                  </table>
                </div>
              )}
            </article>
          </div>

          <div className="workspace-stack">
            <article className="workspace-note-block">
              <div className="section-header">
                <h3>单测任务与结果诊断</h3>
                {selectedTask && <span className={`status-pill ${statusTone(selectedTask.status)}`}>{selectedTask.status}</span>}
              </div>
              <div className="workspace-list" style={{ marginBottom: 16 }}>
                {tasks.filter((item) => item.task_type === 'single').map((item) => (
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
                <div className="workspace-empty">请选择测试任务查看详情。</div>
              ) : (
                <>
                  <div className="workspace-kpi-grid">
                    <article className="workspace-kpi-card">
                      <span>通过率</span>
                      <strong>{Math.round((selectedTask.passed_cases / Math.max(1, selectedTask.total_cases)) * 100)}%</strong>
                    </article>
                    <article className="workspace-kpi-card">
                      <span>平均耗时</span>
                      <strong>{averageMs} ms</strong>
                    </article>
                    <article className="workspace-kpi-card">
                      <span>实际后端</span>
                      <strong>{selectedTask.execution_backend ?? '-'}</strong>
                    </article>
                    <article className="workspace-kpi-card">
                      <span>报告</span>
                      <strong>{selectedTask.report_id ?? '-'}</strong>
                    </article>
                  </div>
                  <div className="enterprise-two-column">
                    <article className="enterprise-note-card">
                      <strong>单测门禁</strong>
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
                      <strong>风险摘要</strong>
                      <div className="enterprise-stack">
                        {caseRisks.map((item) => (
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
                          <th>用例</th>
                          <th>结果</th>
                          <th>耗时</th>
                          <th>得分</th>
                          <th>期望 / 实际</th>
                        </tr>
                      </thead>
                      <tbody>
                        {selectedTask.cases.map((item) => (
                          <tr key={item.case_id}>
                            <td>{item.case_name}</td>
                            <td><span className={`status-pill ${statusTone(item.status)}`}>{item.status}</span></td>
                            <td>{item.duration_ms} ms</td>
                            <td>{item.score.toFixed(4)}</td>
                            <td>{item.expected_output ?? '-'} / {item.actual_output ?? '-'}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                  {currentCase && (
                    <div className="enterprise-two-column">
                      <article className="enterprise-note-card">
                        <strong>当前样本结构化结果</strong>
                        <pre className="workspace-code-block">{JSON.stringify(currentCase.raw_output ?? {}, null, 2)}</pre>
                      </article>
                      <article className="enterprise-note-card">
                        <strong>问题定位建议</strong>
                        <ul className="enterprise-list">
                          <li>优先核对 expected_output 与 actual_output 是否存在标签/结构不一致。</li>
                          <li>若 provider 或 backend 发生变化，应与历史版本对比后再确认是否回归。</li>
                          <li>失败样本可进一步回流到 ai-train 做标注修正或训练重跑。</li>
                        </ul>
                      </article>
                    </div>
                  )}
                </>
              )}
            </article>

            <article className="workspace-note-block">
              <div className="section-header">
                <h3>版本对比</h3>
                <span className="badge badge-muted">参考工程版本对比能力</span>
              </div>
              {!selectedTask || comparableTasks.length === 0 ? (
                <div className="workspace-empty">当前暂无同能力历史单测任务可用于版本对比。</div>
              ) : (
                <>
                  <label className="workspace-field">
                    对比任务
                    <select value={compareTask ? String(compareTask.task_id) : ''} onChange={(event) => setCompareTaskId(Number(event.target.value))}>
                      {comparableTasks.map((item) => (
                        <option key={item.task_id} value={String(item.task_id)}>
                          #{item.task_id} / {item.model_version}
                        </option>
                      ))}
                    </select>
                  </label>
                  <div className="workspace-table-wrap">
                    <table className="workspace-table">
                      <thead>
                        <tr>
                          <th>维度</th>
                          <th>当前任务</th>
                          <th>对比任务</th>
                        </tr>
                      </thead>
                      <tbody>
                        {comparisonRows.map((item) => (
                          <tr key={item.label}>
                            <td>{item.label}</td>
                            <td className={item.same ? 'comparison-same' : 'comparison-diff'}>{item.current}</td>
                            <td className={item.same ? 'comparison-same' : 'comparison-diff'}>{item.baseline}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
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
