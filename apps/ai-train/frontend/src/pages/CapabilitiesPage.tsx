import { useEffect, useState } from 'react'
import type { CapabilityItem } from '../types'
import { fetchList, request, statusTone } from '../api'

export default function CapabilitiesPage() {
  const [capabilities, setCapabilities] = useState<CapabilityItem[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [actionMessage, setActionMessage] = useState<string | null>(null)

  const [capabilityName, setCapabilityName] = useState('')
  const [displayName, setDisplayName] = useState('')
  const [taskType, setTaskType] = useState('classification')

  async function loadCapabilities(): Promise<void> {
    setLoading(true)
    setError(null)
    try {
      const items = await fetchList<CapabilityItem>('/api/v1/capabilities')
      setCapabilities(items)
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : '加载数据失败')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    void loadCapabilities()
  }, [])

  async function handleSubmit(event: React.FormEvent): Promise<void> {
    event.preventDefault()
    setActionMessage(null)
    try {
      await request<CapabilityItem>('/api/v1/capabilities', {
        method: 'POST',
        body: JSON.stringify({
          capability_name: capabilityName,
          display_name: displayName,
          task_type: taskType,
        }),
      })
      setActionMessage('能力注册成功')
      setCapabilityName('')
      setDisplayName('')
      setTaskType('classification')
      await loadCapabilities()
    } catch (submitError) {
      setActionMessage(submitError instanceof Error ? submitError.message : '能力注册失败')
    }
  }

  return (
    <div className="page-container">
      <section className="panel">
        <div className="section-header">
          <div>
            <h2>能力目录管理</h2>
            <p>注册、查看和管理 AI 能力目录。</p>
          </div>
          <span className="badge">CAP</span>
        </div>

        <form onSubmit={(e) => void handleSubmit(e)}>
          <div className="workspace-field">
            <label className="workspace-label">能力标识</label>
            <input
              className="workspace-input"
              value={capabilityName}
              onChange={(e) => setCapabilityName(e.target.value)}
              placeholder="能力标识，如 face_detect"
            />
          </div>
          <div className="workspace-field">
            <label className="workspace-label">显示名称</label>
            <input
              className="workspace-input"
              value={displayName}
              onChange={(e) => setDisplayName(e.target.value)}
              placeholder="显示名称"
            />
          </div>
          <div className="workspace-field">
            <label className="workspace-label">任务类型</label>
            <select
              className="workspace-select"
              value={taskType}
              onChange={(e) => setTaskType(e.target.value)}
            >
              <option value="classification">classification</option>
              <option value="detection">detection</option>
              <option value="ocr">ocr</option>
              <option value="structured_extraction">structured_extraction</option>
            </select>
          </div>
          <button type="submit" className="workspace-btn">注册能力</button>
        </form>

        {actionMessage && <p className="info-text">{actionMessage}</p>}
      </section>

      <section className="panel">
        {loading && <p className="info-text">正在加载能力目录数据...</p>}
        {error && <p className="error-text">数据加载失败：{error}</p>}
        {!loading && !error && capabilities.length === 0 && (
          <p className="info-text">暂无能力记录。</p>
        )}
        {!loading && !error && capabilities.length > 0 && (
          <div className="workspace-table-wrap">
            <table className="workspace-table">
              <thead>
                <tr>
                  <th>能力标识</th>
                  <th>显示名称</th>
                  <th>任务类型</th>
                  <th>数据集状态</th>
                  <th>来源</th>
                </tr>
              </thead>
              <tbody>
                {capabilities.map((item) => (
                  <tr key={item.capability_name}>
                    <td>{item.capability_name}</td>
                    <td>{item.display_name}</td>
                    <td>{item.task_type}</td>
                    <td><span className={`status-pill ${statusTone(item.dataset_status)}`}>{item.dataset_status}</span></td>
                    <td>{item.source}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  )
}
