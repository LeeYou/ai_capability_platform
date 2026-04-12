import { useEffect, useState } from 'react'
import type {
  RemoteModelItem,
  BatchTestForm,
  BaselineForm,
  TestTaskItem,
  TestTaskDetail,
  PerformanceBaselineItem,
} from '../types'
import { fetchList, request, statusTone, parseBatchCases } from '../api'

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
  const [batchForm, setBatchForm] = useState<BatchTestForm>(initialBatchForm)
  const [baselineForm, setBaselineForm] = useState<BaselineForm>(initialBaselineForm)
  const [selectedTaskId, setSelectedTaskId] = useState<number | null>(null)
  const [selectedTask, setSelectedTask] = useState<TestTaskDetail | null>(null)
  const [actionMessage, setActionMessage] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

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

  return (
    <div className="page-container">
      {loading && <p className="info-text">正在加载...</p>}
      {actionMessage && <p className="success-text">{actionMessage}</p>}
      <div className="workspace-panel-grid">
        <div className="workspace-stack">
          <article className="workspace-note-block">
            <div className="section-header">
              <h3>批量测试向导</h3>
              <span className="badge badge-muted">TT16</span>
            </div>
            <div className="workspace-form-grid">
              <label className="workspace-field">
                能力
                <select
                  value={batchForm.capability_name}
                  onChange={(event) => setBatchForm((current) => ({ ...current, capability_name: event.target.value }))}
                >
                  {models.map((item) => (
                    <option key={`${item.capability_name}-${item.model_version}`} value={item.capability_name}>
                      {item.capability_name}
                    </option>
                  ))}
                </select>
              </label>
              <label className="workspace-field">
                模型版本
                <select
                  value={batchForm.model_version}
                  onChange={(event) => setBatchForm((current) => ({ ...current, model_version: event.target.value }))}
                >
                  {models
                    .filter((item) => item.capability_name === batchForm.capability_name)
                    .map((item) => (
                      <option key={item.model_version} value={item.model_version}>
                        {item.model_version}
                      </option>
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
                <textarea
                  rows={8}
                  value={batchForm.cases_text}
                  onChange={(event) => setBatchForm((current) => ({ ...current, cases_text: event.target.value }))}
                />
              </label>
            </div>
            <div className="button-row">
              <button onClick={() => void handleCreateBatchTest()} type="button">创建批量测试</button>
            </div>
          </article>
          <article className="workspace-note-block">
            <div className="section-header">
              <h3>验收基线模板</h3>
              <span className="badge badge-muted">TT17</span>
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
            <div className="button-row">
              <button onClick={() => void handleSaveBaseline()} type="button">保存基线</button>
            </div>
          </article>
        </div>
        <div className="workspace-stack">
          <article className="workspace-note-block">
            <h3>批量任务与问题样本</h3>
            <div className="workspace-list">
              {tasks.map((item) => (
                <button
                  key={item.task_id}
                  className={`workspace-list-item${selectedTaskId === item.task_id ? ' active' : ''}`}
                  onClick={() => setSelectedTaskId(item.task_id)}
                  type="button"
                >
                  <strong>任务 #{item.task_id} / {item.task_type}</strong>
                  <div className="workspace-meta-row">
                    <span>{item.capability_name}</span>
                    <span>{item.passed_cases}/{item.total_cases} 通过</span>
                    <span className={`status-pill ${statusTone(item.status)}`}>{item.status}</span>
                  </div>
                </button>
              ))}
            </div>
            {selectedTask && (
              <div className="workspace-table-wrap" style={{ marginTop: 16 }}>
                <table className="workspace-table">
                  <thead>
                    <tr>
                      <th>失败样本</th>
                      <th>输入</th>
                      <th>耗时</th>
                    </tr>
                  </thead>
                  <tbody>
                    {selectedTask.cases
                      .filter((item) => item.status !== 'passed')
                      .map((item) => (
                        <tr key={item.case_id}>
                          <td>{item.case_name}</td>
                          <td>{item.input_path}</td>
                          <td>{item.duration_ms} ms</td>
                        </tr>
                      ))}
                  </tbody>
                </table>
              </div>
            )}
          </article>
        </div>
      </div>
    </div>
  )
}
