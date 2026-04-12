import { useEffect, useState } from 'react'
import type {
  RemoteModelItem,
  SingleTestForm,
  TestTaskItem,
  TestTaskDetail,
} from '../types'
import { fetchList, request, statusTone } from '../api'

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

  return (
    <div className="page-container">
      {loading && <p className="info-text">正在加载...</p>}
      {actionMessage && <p className="success-text">{actionMessage}</p>}
      <div className="workspace-panel-grid">
        <div className="workspace-stack">
          <article className="workspace-note-block">
            <div className="section-header">
              <h3>创建单测</h3>
              <span className="badge badge-muted">TT15</span>
            </div>
            <div className="workspace-form-grid">
              <label className="workspace-field">
                能力
                <select
                  value={singleForm.capability_name}
                  onChange={(event) => setSingleForm((current) => ({ ...current, capability_name: event.target.value }))}
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
                  value={singleForm.model_version}
                  onChange={(event) => setSingleForm((current) => ({ ...current, model_version: event.target.value }))}
                >
                  {models
                    .filter((item) => item.capability_name === singleForm.capability_name)
                    .map((item) => (
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
                <input
                  value={singleForm.timeout_seconds}
                  onChange={(event) => setSingleForm((current) => ({ ...current, timeout_seconds: event.target.value }))}
                />
              </label>
              <label className="workspace-field full-span">
                用例名称
                <input value={singleForm.case_name} onChange={(event) => setSingleForm((current) => ({ ...current, case_name: event.target.value }))} />
              </label>
              <label className="workspace-field full-span">
                输入路径
                <input value={singleForm.input_path} onChange={(event) => setSingleForm((current) => ({ ...current, input_path: event.target.value }))} />
              </label>
              <label className="workspace-field full-span">
                期望输出
                <textarea
                  rows={4}
                  value={singleForm.expected_output}
                  onChange={(event) => setSingleForm((current) => ({ ...current, expected_output: event.target.value }))}
                />
              </label>
            </div>
            <div className="button-row">
              <button onClick={() => void handleCreateSingleTest()} type="button">发起单测</button>
            </div>
          </article>
        </div>
        <div className="workspace-stack">
          <article className="workspace-note-block">
            <div className="section-header">
              <h3>单测结果对比</h3>
              {selectedTask && <span className={`status-pill ${statusTone(selectedTask.status)}`}>{selectedTask.status}</span>}
            </div>
            <div className="workspace-list" style={{ marginBottom: 16 }}>
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
            {!selectedTask ? (
              <div className="workspace-empty">请选择测试任务查看单测详情。</div>
            ) : (
              <>
                <div className="workspace-kpi-grid">
                  <article className="workspace-kpi-card">
                    <span>通过</span>
                    <strong>{selectedTask.passed_cases}</strong>
                  </article>
                  <article className="workspace-kpi-card">
                    <span>失败</span>
                    <strong>{selectedTask.failed_cases}</strong>
                  </article>
                  <article className="workspace-kpi-card">
                    <span>实际后端</span>
                    <strong>{selectedTask.execution_backend ?? '-'}</strong>
                  </article>
                </div>
                <div className="workspace-table-wrap">
                  <table className="workspace-table">
                    <thead>
                      <tr>
                        <th>用例</th>
                        <th>结果</th>
                        <th>耗时</th>
                        <th>期望 / 实际</th>
                      </tr>
                    </thead>
                    <tbody>
                      {selectedTask.cases.map((item) => (
                        <tr key={item.case_id}>
                          <td>{item.case_name}</td>
                          <td><span className={`status-pill ${statusTone(item.status)}`}>{item.status}</span></td>
                          <td>{item.duration_ms} ms</td>
                          <td>{item.expected_output ?? '-'} / {item.actual_output ?? '-'}</td>
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
    </div>
  )
}
