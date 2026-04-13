import { useEffect, useMemo, useState } from 'react'
import type {
  AcceptanceForm,
  AcceptanceTaskItem,
  AcceptanceTaskDetail,
} from '../types'
import { fetchList, request, statusTone } from '../api'
import { buildAcceptanceChecklist, buildAcceptanceRiskItems, clampScore, scoreTone } from '../enterprise'

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

  const checklist = useMemo(() => buildAcceptanceChecklist(selectedAcceptance), [selectedAcceptance])
  const readinessScore = clampScore(checklist.filter((item) => item.done).length / Math.max(1, checklist.length) * 100)
  const riskItems = useMemo(() => buildAcceptanceRiskItems(selectedAcceptance), [selectedAcceptance])

  return (
    <div className="page-container">
      {loading && <p className="info-text">正在加载...</p>}
      {actionMessage && <p className="success-text">{actionMessage}</p>}

      <section className="panel">
        <div className="section-header">
          <div>
            <h2>生产验收工作台</h2>
            <p>把 acceptance / pressure 两类脚本统一到一个门禁面板里，形成更贴近企业交付的生产验收页。</p>
          </div>
          <span className="badge">TT20-TT24</span>
        </div>
        <div className="enterprise-hero-grid">
          <article className={`enterprise-score-card tone-${scoreTone(readinessScore)}`}>
            <span>生产验收通过度</span>
            <strong>{readinessScore}</strong>
            <p>综合目标环境、脚本执行、基线校验与可下游消费结论。</p>
          </article>
          <article className="enterprise-note-card">
            <strong>本页重点</strong>
            <p>让验收页兼顾环境配置、公开 API 验收、压测基线和最终推进决策，而不是只展示脚本表格。</p>
          </article>
        </div>
      </section>

      <section className="panel">
        <div className="workspace-panel-grid">
          <div className="workspace-stack">
            <article className="workspace-note-block">
              <div className="section-header">
                <h3>生产验收任务</h3>
                <span className="badge badge-muted">环境 / 验收 / 压测</span>
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
                <label className="workspace-field">
                  设备偏好
                  <select
                    value={acceptanceForm.prefer_device}
                    onChange={(event) =>
                      setAcceptanceForm((current) => ({
                        ...current,
                        prefer_device: event.target.value as AcceptanceForm['prefer_device'],
                      }))
                    }
                  >
                    <option value="auto">auto</option>
                    <option value="gpu">gpu</option>
                    <option value="cpu">cpu</option>
                  </select>
                </label>
                <label className="workspace-field">
                  管理接口校验
                  <select
                    value={acceptanceForm.run_admin_checks ? 'yes' : 'no'}
                    onChange={(event) => setAcceptanceForm((current) => ({ ...current, run_admin_checks: event.target.value === 'yes' }))}
                  >
                    <option value="yes">yes</option>
                    <option value="no">no</option>
                  </select>
                </label>
                <label className="workspace-field full-span">
                  推理载荷
                  <textarea rows={4} value={acceptanceForm.infer_payload} onChange={(event) => setAcceptanceForm((current) => ({ ...current, infer_payload: event.target.value }))} />
                </label>
                <label className="workspace-field">
                  压测请求数
                  <input value={acceptanceForm.pressure_requests} onChange={(event) => setAcceptanceForm((current) => ({ ...current, pressure_requests: event.target.value }))} />
                </label>
                <label className="workspace-field">
                  压测并发
                  <input value={acceptanceForm.pressure_concurrency} onChange={(event) => setAcceptanceForm((current) => ({ ...current, pressure_concurrency: event.target.value }))} />
                </label>
                <label className="workspace-field">
                  最低成功率
                  <input value={acceptanceForm.pressure_min_success_rate} onChange={(event) => setAcceptanceForm((current) => ({ ...current, pressure_min_success_rate: event.target.value }))} />
                </label>
                <label className="workspace-field">
                  P95 阈值
                  <input value={acceptanceForm.pressure_max_p95_ms} onChange={(event) => setAcceptanceForm((current) => ({ ...current, pressure_max_p95_ms: event.target.value }))} />
                </label>
              </div>
              <div className="workspace-action-row">
                <button className="action-button" onClick={() => void handleCreateAcceptanceTask()} type="button">发起生产验收</button>
              </div>
            </article>

            <article className="workspace-note-block">
              <strong>验收门禁</strong>
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
          </div>

          <div className="workspace-stack">
            <article className="workspace-note-block">
              <div className="section-header">
                <h3>验收脚本结果</h3>
                {selectedAcceptance && <span className={`status-pill ${statusTone(selectedAcceptance.status)}`}>{selectedAcceptance.status}</span>}
              </div>
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
              {!selectedAcceptance ? (
                <div className="workspace-empty">请选择验收任务查看详情。</div>
              ) : (
                <>
                  <div className="workspace-kpi-grid">
                    <article className="workspace-kpi-card">
                      <span>通过脚本</span>
                      <strong>{selectedAcceptance.passed_cases}</strong>
                    </article>
                    <article className="workspace-kpi-card">
                      <span>失败脚本</span>
                      <strong>{selectedAcceptance.failed_cases}</strong>
                    </article>
                    <article className="workspace-kpi-card">
                      <span>环境</span>
                      <strong>{selectedAcceptance.prefer_device}</strong>
                    </article>
                    <article className="workspace-kpi-card">
                      <span>报告</span>
                      <strong>{selectedAcceptance.report_id ?? '-'}</strong>
                    </article>
                  </div>
                  <div className="enterprise-two-column">
                    <article className="enterprise-note-card">
                      <strong>风险摘要</strong>
                      <div className="enterprise-stack">
                        {riskItems.map((item) => (
                          <div key={item.title} className={`enterprise-inline-card tone-${item.tone}`}>
                            <strong>{item.title}</strong>
                            <p>{item.detail}</p>
                          </div>
                        ))}
                      </div>
                    </article>
                    <article className="enterprise-note-card">
                      <strong>验收建议</strong>
                      <ul className="enterprise-list">
                        <li>先看 acceptance_check 是否通过公开 API 与管理接口主链路。</li>
                        <li>再看 pressure_smoke 是否满足成功率和延迟阈值。</li>
                        <li>所有脚本通过后，再沉淀报告并推进授权 / 构建。</li>
                      </ul>
                    </article>
                  </div>
                  <div className="workspace-table-wrap">
                    <table className="workspace-table">
                      <thead>
                        <tr>
                          <th>脚本</th>
                          <th>结果</th>
                          <th>耗时</th>
                          <th>基线</th>
                          <th>详情</th>
                        </tr>
                      </thead>
                      <tbody>
                        {selectedAcceptance.script_results.map((item) => (
                          <tr key={item.case_name}>
                            <td>{item.case_name}</td>
                            <td><span className={`status-pill ${item.passed ? 'good' : 'danger'}`}>{item.status}</span></td>
                            <td>{item.duration_ms} ms</td>
                            <td>{item.passed_baseline == null ? '-' : item.passed_baseline ? '通过' : '失败'}</td>
                            <td>{JSON.stringify(item.baseline_comparison ?? item.detail)}</td>
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
