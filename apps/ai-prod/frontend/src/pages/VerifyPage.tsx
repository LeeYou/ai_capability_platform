import { useEffect, useMemo, useState } from 'react'
import type { DashboardState, InferResponse } from '../types'
import { initialState, loadDashboard, runInfer } from '../api'
import { buildVerifyChecklist, clampScore, scoreTone } from '../enterprise'

export default function VerifyPage() {
  const [dashboard, setDashboard] = useState<DashboardState>(initialState)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [selectedCapability, setSelectedCapability] = useState('')
  const [preferDevice, setPreferDevice] = useState<'auto' | 'gpu' | 'cpu'>('auto')
  const [payload, setPayload] = useState('{"image":"demo"}')
  const [inputType, setInputType] = useState<'json' | 'image' | 'video' | 'pdf'>('json')
  const [inferResult, setInferResult] = useState<InferResponse | null>(null)
  const [actionMessage, setActionMessage] = useState<string | null>(null)

  async function refresh(): Promise<void> {
    try {
      setLoading(true)
      setError(null)
      const data = await loadDashboard()
      setDashboard(data)
      setSelectedCapability((current) => current || data.capabilities[0]?.capability_name || '')
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : '加载失败')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    void refresh()
  }, [])

  const selectedCapabilityDetail = useMemo(
    () => dashboard.capabilities.find((item) => item.capability_name === selectedCapability) ?? null,
    [dashboard.capabilities, selectedCapability],
  )

  const jsonPayloadValid = useMemo(() => {
    if (inputType !== 'json') return payload.trim().length > 0
    try {
      JSON.parse(payload)
      return true
    } catch {
      return false
    }
  }, [inputType, payload])

  const checklist = useMemo(
    () => buildVerifyChecklist({
      selectedCapability: selectedCapabilityDetail,
      payload,
      inputType,
      licenseStatus: dashboard.licenseStatus,
      inferResult,
      jsonPayloadValid,
    }),
    [dashboard.licenseStatus, inferResult, inputType, jsonPayloadValid, payload, selectedCapabilityDetail],
  )
  const verifyScore = clampScore((checklist.filter((item) => item.done).length / Math.max(1, checklist.length)) * 100)

  async function handleInfer(): Promise<void> {
    if (!selectedCapability) {
      setActionMessage('请先选择能力。')
      return
    }
    if (!jsonPayloadValid) {
      setActionMessage('当前输入载荷不可执行，请先修正。')
      return
    }
    try {
      setActionMessage('正在执行在线验证...')
      const result = await runInfer(selectedCapability, inputType, payload, preferDevice)
      setInferResult(result)
      setActionMessage(`推理完成，请求 ID：${result.request_id}`)
      await refresh()
    } catch (loadError) {
      setActionMessage(loadError instanceof Error ? loadError.message : '推理失败')
    }
  }

  return (
    <div className="page-container">
      <section className="panel">
        <div className="section-header">
          <div>
            <h2>在线验证工作台</h2>
            <p>在真实运行态下关联当前 revision、授权状态、设备偏好和能力上下文，形成可留痕的在线验证入口。</p>
          </div>
          <span className="badge">P45-P49</span>
        </div>
        {loading && <p className="info-text">正在加载...</p>}
        {error && <p className="error-text">数据加载失败：{error}</p>}
        {actionMessage && <p className="success-text">{actionMessage}</p>}
        <div className="enterprise-hero-grid">
          <article className={`enterprise-score-card tone-${scoreTone(verifyScore)}`}>
            <span>验证准备度</span>
            <strong>{verifyScore}</strong>
            <p>根据能力、载荷、授权和结果留痕四项门禁计算。</p>
          </article>
          <article className="enterprise-note-card">
            <strong>控制台边界</strong>
            <p>这里是内部运行确认入口，不是客户业务页面；每次验证都要能关联 revision、license 和能力元数据。</p>
          </article>
        </div>
      </section>

      <section className="panel">
        <div className="workspace-panel-grid">
          <div className="workspace-stack">
            <article className="workspace-note-block">
              <div className="section-header">
                <h3>验证输入</h3>
                <span className="badge badge-muted">Verify</span>
              </div>
              <div className="workspace-form-grid">
                <label className="workspace-field">
                  能力
                  <select value={selectedCapability} onChange={(event) => setSelectedCapability(event.target.value)}>
                    {dashboard.capabilities.map((item) => (
                      <option key={item.capability_name} value={item.capability_name}>{item.capability_name}</option>
                    ))}
                  </select>
                </label>
                <label className="workspace-field">
                  输入类型
                  <select value={inputType} onChange={(event) => setInputType(event.target.value as typeof inputType)}>
                    <option value="json">json</option>
                    <option value="image">image</option>
                    <option value="video">video</option>
                    <option value="pdf">pdf</option>
                  </select>
                </label>
                <label className="workspace-field">
                  设备偏好
                  <select value={preferDevice} onChange={(event) => setPreferDevice(event.target.value as typeof preferDevice)}>
                    <option value="auto">auto</option>
                    <option value="gpu">gpu</option>
                    <option value="cpu">cpu</option>
                  </select>
                </label>
                <label className="workspace-field full-span">
                  推理载荷
                  <textarea rows={6} value={payload} onChange={(event) => setPayload(event.target.value)} />
                </label>
              </div>
              <div className="workspace-action-row">
                <button className="action-button" onClick={() => void handleInfer()} type="button">执行在线验证</button>
              </div>
            </article>

            <article className="workspace-note-block">
              <strong>验证门禁</strong>
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
              <h3>运行上下文</h3>
              <div className="workspace-kpi-grid">
                <article className="workspace-kpi-card">
                  <span>能力</span>
                  <strong>{selectedCapabilityDetail?.capability_name ?? '-'}</strong>
                </article>
                <article className="workspace-kpi-card">
                  <span>revision</span>
                  <strong>{selectedCapabilityDetail?.revision_id ?? '-'}</strong>
                </article>
                <article className="workspace-kpi-card">
                  <span>设备模式</span>
                  <strong>{selectedCapabilityDetail?.device_mode ?? '-'}</strong>
                </article>
                <article className="workspace-kpi-card">
                  <span>授权</span>
                  <strong>{dashboard.licenseStatus?.code ?? '-'}</strong>
                </article>
              </div>
              <div className="enterprise-two-column">
                <article className="enterprise-note-card">
                  <strong>能力上下文</strong>
                  <p>版本：{selectedCapabilityDetail?.model_version ?? '-'}</p>
                  <p>插件目标：{selectedCapabilityDetail?.plugin_target ?? '-'}</p>
                  <p>后端：{selectedCapabilityDetail?.backend_type ?? '-'}</p>
                </article>
                <article className="enterprise-note-card">
                  <strong>授权上下文</strong>
                  <p>结果码：{dashboard.licenseStatus?.code ?? '-'}</p>
                  <p>阶段：{dashboard.licenseStatus?.stage ?? '-'}</p>
                  <p>客户：{dashboard.licenseStatus?.customer_code ?? '-'}</p>
                </article>
              </div>
            </article>

            <article className="workspace-note-block">
              <h3>验证结果与留痕</h3>
              <div className="workspace-kpi-grid">
                <article className="workspace-kpi-card">
                  <span>请求 ID</span>
                  <strong>{inferResult?.request_id ?? '-'}</strong>
                </article>
                <article className="workspace-kpi-card">
                  <span>执行设备</span>
                  <strong>{inferResult?.device ?? preferDevice}</strong>
                </article>
                <article className="workspace-kpi-card">
                  <span>运行 revision</span>
                  <strong>{inferResult?.runtime_revision_id ?? selectedCapabilityDetail?.revision_id ?? '-'}</strong>
                </article>
                <article className="workspace-kpi-card">
                  <span>授权结果</span>
                  <strong>{inferResult ? (inferResult.license_valid ? 'valid' : 'denied') : '-'}</strong>
                </article>
              </div>
              <pre className="workspace-code-block">{JSON.stringify(inferResult ?? {}, null, 2)}</pre>
            </article>
          </div>
        </div>
      </section>
    </div>
  )
}
