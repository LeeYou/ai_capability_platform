import { useEffect, useMemo, useState } from 'react'
import type { DatasetItem, CapabilityItem } from '../types'
import { fetchList, formatDateTime, formatFileSize, request, statusTone } from '../api'

const initialForm = {
  capability_name: '',
  dataset_path: '',
  dataset_status: 'ready',
}

export default function DatasetsPage() {
  const [datasets, setDatasets] = useState<DatasetItem[]>([])
  const [capabilities, setCapabilities] = useState<CapabilityItem[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [actionMessage, setActionMessage] = useState<string | null>(null)
  const [form, setForm] = useState(initialForm)

  async function load(): Promise<void> {
    setLoading(true)
    setError(null)
    try {
      const [datasetItems, capabilityItems] = await Promise.all([
        fetchList<DatasetItem>('/api/v1/datasets'),
        fetchList<CapabilityItem>('/api/v1/capabilities'),
      ])
      setDatasets(datasetItems)
      setCapabilities(capabilityItems)
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : '加载数据失败')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    void load()
  }, [])

  const summaryCards = useMemo(() => {
    const readyCount = datasets.filter((item) => item.dataset_status === 'ready').length
    const missingCount = datasets.filter((item) => item.dataset_status === 'missing').length
    const totalFiles = datasets.reduce((sum, item) => sum + (item.file_count ?? 0), 0)
    const totalSize = datasets.reduce((sum, item) => sum + (item.total_size_bytes ?? 0), 0)
    return [
      { title: '数据集绑定', value: datasets.length, detail: '能力到目录的绑定关系' },
      { title: '可用数据集', value: readyCount, detail: '当前状态 ready 的数据集' },
      { title: '缺失数据集', value: missingCount, detail: '目录不存在或不可用的数据集' },
      { title: '文件总量', value: `${totalFiles}`, detail: `累计 ${formatFileSize(totalSize)}` },
    ]
  }, [datasets])

  async function handleSubmit(event: React.FormEvent): Promise<void> {
    event.preventDefault()
    setActionMessage(null)
    try {
      await request('/api/v1/dataset-bindings', {
        method: 'POST',
        body: JSON.stringify(form),
      })
      setActionMessage('数据集绑定已更新')
      setForm(initialForm)
      await load()
    } catch (submitError) {
      setActionMessage(submitError instanceof Error ? submitError.message : '绑定失败')
    }
  }

  return (
    <div className="page-container">
      <section className="panel">
        <div className="section-header">
          <div>
            <h2>数据集管理</h2>
            <p>统一维护训练集绑定关系、目录健康度与容量信息。</p>
          </div>
          <div className="workspace-action-row">
            <button className="action-button" type="button" onClick={() => void load()}>刷新数据</button>
          </div>
        </div>
        <div className="workspace-highlight-grid">
          {summaryCards.map((item) => (
            <article key={item.title} className="workspace-highlight-card">
              <span>{item.title}</span>
              <strong>{item.value}</strong>
              <span>{item.detail}</span>
            </article>
          ))}
        </div>
      </section>

      <section className="panel">
        <div className="workspace-panel-grid">
          <div className="workspace-stack">
            <article className="workspace-note-block">
              <div className="section-header">
                <h3>绑定数据集</h3>
                <span className="badge badge-muted">DS</span>
              </div>
              <form className="workspace-form-grid" onSubmit={(event) => void handleSubmit(event)}>
                <label className="workspace-field">
                  目标能力
                  <select
                    value={form.capability_name}
                    onChange={(event) => setForm((current) => ({ ...current, capability_name: event.target.value }))}
                  >
                    <option value="">请选择能力</option>
                    {capabilities.map((item) => (
                      <option key={item.capability_name} value={item.capability_name}>
                        {item.display_name} ({item.capability_name})
                      </option>
                    ))}
                  </select>
                </label>
                <label className="workspace-field">
                  数据集目录
                  <input
                    value={form.dataset_path}
                    onChange={(event) => setForm((current) => ({ ...current, dataset_path: event.target.value }))}
                    placeholder="相对 datasets 根目录，如 face_detect/trainset"
                  />
                </label>
                <label className="workspace-field">
                  数据集状态
                  <select
                    value={form.dataset_status}
                    onChange={(event) => setForm((current) => ({ ...current, dataset_status: event.target.value }))}
                  >
                    <option value="ready">ready</option>
                    <option value="staging">staging</option>
                    <option value="missing">missing</option>
                  </select>
                </label>
                <div className="workspace-action-row full-span">
                  <button className="action-button" type="submit">保存绑定</button>
                </div>
              </form>
              {actionMessage && <p className="info-text">{actionMessage}</p>}
            </article>
          </div>

          <div className="workspace-stack">
            <article className="workspace-note-block">
              <div className="section-header">
                <h3>数据集资产视图</h3>
                <span className="badge badge-muted">{datasets.length} 项</span>
              </div>
              {loading && <div className="workspace-empty">正在加载数据集数据...</div>}
              {error && <p className="error-text">数据加载失败：{error}</p>}
              {!loading && !error && datasets.length === 0 && (
                <div className="workspace-empty">暂无数据集绑定记录。</div>
              )}
              {!loading && !error && datasets.length > 0 && (
                <div className="workspace-table-wrap">
                  <table className="workspace-table">
                    <thead>
                      <tr>
                        <th>能力</th>
                        <th>路径</th>
                        <th>状态</th>
                        <th>文件数</th>
                        <th>大小</th>
                        <th>最后更新</th>
                        <th>来源</th>
                      </tr>
                    </thead>
                    <tbody>
                      {datasets.map((item) => (
                        <tr key={`${item.capability_name}-${item.dataset_path}`}>
                          <td>{item.capability_name}</td>
                          <td><code>{item.dataset_path}</code></td>
                          <td><span className={`status-pill ${statusTone(item.dataset_status)}`}>{item.dataset_status}</span></td>
                          <td>{item.file_count ?? 0}</td>
                          <td>{formatFileSize(item.total_size_bytes)}</td>
                          <td>{formatDateTime(item.last_modified)}</td>
                          <td>{item.source}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </article>
          </div>
        </div>
      </section>
    </div>
  )
}
