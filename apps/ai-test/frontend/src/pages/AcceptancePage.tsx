import { useEffect, useState } from 'react'
import type {
  AcceptanceForm,
  AcceptanceTaskItem,
  AcceptanceTaskDetail,
} from '../types'
import { fetchList, request, statusTone } from '../api'

const initialAcceptanceForm: AcceptanceForm = {
  image_uri: 'agilestar/ai-prod:latest',
  target_base_url: 'http://127.0.0.1:26004',
  capability_name: '',
  input_type: 'json',
  infer_payload: '{"image":"demo"}',
  prefer_device: 'auto',
  acceptance_timeout_seconds: '20',
  run_admin_checks: true,
  pressure_requests: '32',
  pressure_concurrency: '8',
  pressure_timeout_seconds: '10',
  pressure_min_success_rate: '1',
  pressure_max_p95_ms: '5000',
}

export function AcceptancePage() {
  const [acceptanceTasks, setAcceptanceTasks] = useState<AcceptanceTaskItem[]>([])
  const [acceptanceForm, setAcceptanceForm] = useState<AcceptanceForm>(initialAcceptanceForm)
  const [selectedAcceptanceId, setSelectedAcceptanceId] = useState<number | null>(null)
  const [selectedAcceptance, setSelectedAcceptance] = useState<AcceptanceTaskDetail | null>(null)
  const [actionMessage, setActionMessage] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  async function loadData(): Promise<void> {
    setLoading(true)
    try {
      const res = await fetchList<AcceptanceTaskItem>('/api/v1/acceptance-tasks')
      setAcceptanceTasks(res.items)
      setSelectedAcceptanceId((current) => current ?? res.items[0]?.acceptance_task_id ?? null)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    void loadData()
  }, [])

  useEffect(() => {
    if (selectedAcceptanceId == null) {
      setSelectedAcceptance(null)
      return
    }
    void request<AcceptanceTaskDetail>(`/api/v1/acceptance-tasks/${selectedAcceptanceId}`)
      .then(setSelectedAcceptance)
      .catch(() => {
        setSelectedAcceptance(null)
      })
  }, [selectedAcceptanceId])

  async function handleCreateAcceptanceTask(): Promise<void> {
    try {
      setActionMessage('正在创建生产验收任务...')
      const created = await request<AcceptanceTaskDetail>('/api/v1/acceptance-tasks', {
        method: 'POST',
        body: JSON.stringify({
          image_uri: acceptanceForm.image_uri,
          target_base_url: acceptanceForm.target_base_url,
          capability_name: acceptanceForm.capability_name || null,
          input_type: acceptanceForm.input_type,
          infer_payload: acceptanceForm.infer_payload,
          prefer_device: acceptanceForm.prefer_device,
          acceptance_timeout_seconds: Number(acceptanceForm.acceptance_timeout_seconds),
          run_admin_checks: acceptanceForm.run_admin_checks,
          pressure_requests: Number(acceptanceForm.pressure_requests),
          pressure_concurrency: Number(acceptanceForm.pressure_concurrency),
          pressure_timeout_seconds: Number(acceptanceForm.pressure_timeout_seconds),
          pressure_min_success_rate: Number(acceptanceForm.pressure_min_success_rate),
          pressure_max_p95_ms: Number(acceptanceForm.pressure_max_p95_ms),
        }),
      })
      setSelectedAcceptanceId(created.acceptance_task_id)
      setActionMessage(`验收任务 #${created.acceptance_task_id} 已创建`)
      await loadData()
    } catch (loadError) {
      setActionMessage(loadError instanceof Error ? loadError.message : '创建验收任务失败')
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
              <h3>生产验收任务</h3>
              <span className="badge badge-muted">TT17</span>
            </div>
            <div className="workspace-form-grid">
              <label className="workspace-field">
                镜像
                <input value={acceptanceForm.image_uri} onChange={(event) => setAcceptanceForm((current) => ({ ...current, image_uri: event.target.value }))} />
              </label>
              <label className="workspace-field">
                目标地址
                <input value={acceptanceForm.target_base_url} onChange={(event) => setAcceptanceForm((current) => ({ ...current, target_base_url: event.target.value }))} />
              </label>
              <label className="workspace-field">
                能力
                <input value={acceptanceForm.capability_name} onChange={(event) => setAcceptanceForm((current) => ({ ...current, capability_name: event.target.value }))} />
              </label>
              <label className="workspace-field">
                输入类型
                <select
                  value={acceptanceForm.input_type}
                  onChange={(event) =>
                    setAcceptanceForm((current) => ({
                      ...current,
                      input_type: event.target.value as AcceptanceForm['input_type'],
                    }))
                  }
                >
                  <option value="json">json</option>
                  <option value="image">image</option>
                  <option value="video">video</option>
                  <option value="pdf">pdf</option>
                </select>
              </label>
              <label className="workspace-field full-span">
                推理载荷
                <textarea rows={4} value={acceptanceForm.infer_payload} onChange={(event) => setAcceptanceForm((current) => ({ ...current, infer_payload: event.target.value }))} />
              </label>
            </div>
            <div className="button-row">
              <button onClick={() => void handleCreateAcceptanceTask()} type="button">发起生产验收</button>
            </div>
          </article>
        </div>
        <div className="workspace-stack">
          <article className="workspace-note-block">
            <h3>验收脚本结果</h3>
            <div className="workspace-list">
              {acceptanceTasks.map((item) => (
                <button
                  key={item.acceptance_task_id}
                  className={`workspace-list-item${selectedAcceptanceId === item.acceptance_task_id ? ' active' : ''}`}
                  onClick={() => setSelectedAcceptanceId(item.acceptance_task_id)}
                  type="button"
                >
                  <strong>验收 #{item.acceptance_task_id}</strong>
                  <div className="workspace-meta-row">
                    <span>{item.image_uri}</span>
                    <span>{item.passed_cases}/{item.total_cases} 通过</span>
                    <span className={`status-pill ${statusTone(item.status)}`}>{item.status}</span>
                  </div>
                </button>
              ))}
            </div>
            {selectedAcceptance && (
              <div className="workspace-table-wrap" style={{ marginTop: 16 }}>
                <table className="workspace-table">
                  <thead>
                    <tr>
                      <th>脚本</th>
                      <th>结果</th>
                      <th>耗时</th>
                      <th>基线</th>
                    </tr>
                  </thead>
                  <tbody>
                    {selectedAcceptance.script_results.map((item) => (
                      <tr key={item.case_name}>
                        <td>{item.case_name}</td>
                        <td><span className={`status-pill ${item.passed ? 'good' : 'danger'}`}>{item.status}</span></td>
                        <td>{item.duration_ms} ms</td>
                        <td>{item.passed_baseline == null ? '-' : item.passed_baseline ? '通过' : '失败'}</td>
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
