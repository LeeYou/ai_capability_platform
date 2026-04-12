import { useEffect, useState } from 'react'
import type { DashboardState, InferResponse } from '../types'
import { initialState, loadDashboard, runInfer } from '../api'

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

  const selectedCapabilityDetail = dashboard.capabilities.find((item) => item.capability_name === selectedCapability) ?? null

  async function handleInfer(): Promise<void> {
    if (!selectedCapability) {
      setActionMessage('请先选择能力。')
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
        {loading && <p className="info-text">正在加载...</p>}
        {error && <p className="error-text">数据加载失败：{error}</p>}
        {actionMessage && <p className="success-text">{actionMessage}</p>}
        <div className="workspace-panel-grid">
          <div className="workspace-stack">
            <article className="workspace-note-block">
              <div className="section-header">
                <h3>在线验证</h3>
                <span className="badge badge-muted">P42</span>
              </div>
              <div className="workspace-form-grid">
                <label className="workspace-field">
                  能力
                  <select value={selectedCapability} onChange={(event) => setSelectedCapability(event.target.value)}>
                    {dashboard.capabilities.map((item) => (
                      <option key={item.capability_name} value={item.capability_name}>
                        {item.capability_name}
                      </option>
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
              <div className="button-row">
                <button onClick={() => void handleInfer()} type="button">执行在线验证</button>
              </div>
            </article>
          </div>
          <div className="workspace-stack">
            <article className="workspace-note-block">
              <h3>验证结果</h3>
              {selectedCapabilityDetail && (
                <div className="workspace-kpi-grid">
                  <article className="workspace-kpi-card">
                    <span>能力</span>
                    <strong>{selectedCapabilityDetail.capability_name}</strong>
                  </article>
                  <article className="workspace-kpi-card">
                    <span>当前 revision</span>
                    <strong>{selectedCapabilityDetail.revision_id ?? '-'}</strong>
                  </article>
                </div>
              )}
              <pre className="workspace-code-block">{JSON.stringify(inferResult ?? {}, null, 2)}</pre>
            </article>
          </div>
        </div>
      </section>
    </div>
  )
}
