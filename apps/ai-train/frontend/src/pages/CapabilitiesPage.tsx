import { useEffect, useMemo, useState } from 'react'
import type { CapabilityItem } from '../types'
import { fetchList, formatDateTime, prettyJson, request, statusTone } from '../api'

const initialForm = {
  capability_name: '',
  display_name: '',
  task_type: 'classification',
}

export default function CapabilitiesPage() {
  const [capabilities, setCapabilities] = useState<CapabilityItem[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [actionMessage, setActionMessage] = useState<string | null>(null)
  const [selectedCapabilityName, setSelectedCapabilityName] = useState<string | null>(null)
  const [form, setForm] = useState(initialForm)
  const [editing, setEditing] = useState(false)

  async function loadCapabilities(): Promise<void> {
    setLoading(true)
    setError(null)
    try {
      const items = await fetchList<CapabilityItem>('/api/v1/capabilities')
      setCapabilities(items)
      setSelectedCapabilityName((current) => current ?? items[0]?.capability_name ?? null)
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : '加载数据失败')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    void loadCapabilities()
  }, [])

  const selectedCapability = useMemo(
    () => capabilities.find((item) => item.capability_name === selectedCapabilityName) ?? null,
    [capabilities, selectedCapabilityName],
  )

  const summaryCards = useMemo(() => {
    const taskTypes = new Set(capabilities.map((item) => item.task_type)).size
    const boundCount = capabilities.filter((item) => item.dataset_status === 'ready').length
    return [
      { title: '能力数量', value: capabilities.length, detail: '已接入训练能力目录' },
      { title: '任务类型', value: taskTypes, detail: '覆盖 classification / detection / ocr / structured_extraction' },
      { title: '已绑定数据集', value: boundCount, detail: '具备可直接发起任务的数据能力' },
    ]
  }, [capabilities])

  async function handleSubmit(event: React.FormEvent): Promise<void> {
    event.preventDefault()
    setActionMessage(null)
    try {
      await request('/api/v1/capabilities', {
        method: 'POST',
        body: JSON.stringify(form),
      })
      setActionMessage(editing ? '能力信息已更新' : '能力注册成功')
      setForm(initialForm)
      setEditing(false)
      await loadCapabilities()
      setSelectedCapabilityName(form.capability_name)
    } catch (submitError) {
      setActionMessage(submitError instanceof Error ? submitError.message : '能力保存失败')
    }
  }

  async function handleDelete(capabilityName: string): Promise<void> {
    if (!window.confirm(`确认删除能力 ${capabilityName} 吗？相关任务和模型会一并清理。`)) return
    try {
      await request(`/api/v1/capabilities/${capabilityName}`, { method: 'DELETE' })
      setActionMessage(`能力 ${capabilityName} 已删除`)
      setSelectedCapabilityName(null)
      setForm(initialForm)
      setEditing(false)
      await loadCapabilities()
    } catch (deleteError) {
      setActionMessage(deleteError instanceof Error ? deleteError.message : '删除能力失败')
    }
  }

  function beginEdit(item: CapabilityItem): void {
    setEditing(true)
    setSelectedCapabilityName(item.capability_name)
    setForm({
      capability_name: item.capability_name,
      display_name: item.display_name,
      task_type: item.task_type,
    })
  }

  return (
    <div className="page-container">
      <section className="panel">
        <div className="section-header">
          <div>
            <h2>能力目录管理</h2>
            <p>统一管理能力注册、任务类型、数据集绑定状态与契约预览。</p>
          </div>
          <div className="workspace-action-row">
            <button
              className="action-button"
              type="button"
              onClick={() => {
                setEditing(false)
                setForm(initialForm)
              }}
            >
              新建能力
            </button>
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
                <h3>{editing ? '编辑能力' : '注册能力'}</h3>
                <span className="badge badge-muted">CAP</span>
              </div>
              <form className="workspace-form-grid" onSubmit={(event) => void handleSubmit(event)}>
                <label className="workspace-field">
                  能力标识
                  <input
                    value={form.capability_name}
                    disabled={editing}
                    onChange={(event) => setForm((current) => ({ ...current, capability_name: event.target.value }))}
                    placeholder="如 face_detect"
                  />
                </label>
                <label className="workspace-field">
                  显示名称
                  <input
                    value={form.display_name}
                    onChange={(event) => setForm((current) => ({ ...current, display_name: event.target.value }))}
                    placeholder="如 人脸检测"
                  />
                </label>
                <label className="workspace-field">
                  任务类型
                  <select
                    value={form.task_type}
                    onChange={(event) => setForm((current) => ({ ...current, task_type: event.target.value }))}
                  >
                    <option value="classification">classification</option>
                    <option value="detection">detection</option>
                    <option value="ocr">ocr</option>
                    <option value="structured_extraction">structured_extraction</option>
                  </select>
                </label>
                <div className="workspace-action-row full-span">
                  <button className="action-button" type="submit">{editing ? '保存修改' : '注册能力'}</button>
                </div>
              </form>
              {actionMessage && <p className="info-text">{actionMessage}</p>}
            </article>

            <article className="workspace-note-block">
              <div className="section-header">
                <h3>能力列表</h3>
                <span className="badge badge-muted">{capabilities.length} 项</span>
              </div>
              {loading && <div className="workspace-empty">正在加载能力目录...</div>}
              {error && <p className="error-text">数据加载失败：{error}</p>}
              {!loading && !error && capabilities.length === 0 && (
                <div className="workspace-empty">暂无能力记录。</div>
              )}
              {!loading && !error && capabilities.length > 0 && (
                <div className="workspace-list">
                  {capabilities.map((item) => (
                    <button
                      key={item.capability_name}
                      className={`workspace-list-item${selectedCapabilityName === item.capability_name ? ' active' : ''}`}
                      onClick={() => setSelectedCapabilityName(item.capability_name)}
                      type="button"
                    >
                      <strong>{item.display_name}</strong>
                      <div className="workspace-meta-row">
                        <span>{item.capability_name}</span>
                        <span>{item.task_type}</span>
                        <span className={`status-pill ${statusTone(item.dataset_status)}`}>{item.dataset_status}</span>
                      </div>
                    </button>
                  ))}
                </div>
              )}
            </article>
          </div>

          <div className="workspace-stack">
            <article className="workspace-note-block">
              <div className="section-header">
                <h3>能力详情</h3>
                {selectedCapability && (
                  <div className="workspace-action-row">
                    <button className="action-button" type="button" onClick={() => beginEdit(selectedCapability)}>编辑</button>
                    <button className="action-button danger-button" type="button" onClick={() => void handleDelete(selectedCapability.capability_name)}>删除</button>
                  </div>
                )}
              </div>
              {!selectedCapability ? (
                <div className="workspace-empty">请选择能力查看详情。</div>
              ) : (
                <>
                  <div className="workspace-kpi-grid">
                    <article className="workspace-kpi-card">
                      <span>任务类型</span>
                      <strong>{selectedCapability.task_type}</strong>
                    </article>
                    <article className="workspace-kpi-card">
                      <span>数据集状态</span>
                      <strong>{selectedCapability.dataset_status}</strong>
                    </article>
                    <article className="workspace-kpi-card">
                      <span>最近更新时间</span>
                      <strong className="kpi-date">{formatDateTime(selectedCapability.updated_at)}</strong>
                    </article>
                  </div>
                  <div className="workspace-table-wrap">
                    <table className="workspace-table">
                      <tbody>
                        <tr><th>能力标识</th><td>{selectedCapability.capability_name}</td></tr>
                        <tr><th>显示名称</th><td>{selectedCapability.display_name}</td></tr>
                        <tr><th>数据集路径</th><td><code>{selectedCapability.dataset_path || '-'}</code></td></tr>
                        <tr><th>来源</th><td>{selectedCapability.source}</td></tr>
                        <tr><th>创建时间</th><td>{formatDateTime(selectedCapability.created_at)}</td></tr>
                      </tbody>
                    </table>
                  </div>
                  <div className="workspace-stack">
                    <div>
                      <h4>标注 Schema</h4>
                      <pre className="workspace-code-block">{prettyJson(selectedCapability.annotation_schema)}</pre>
                    </div>
                    <div>
                      <h4>模板契约</h4>
                      <pre className="workspace-code-block">{prettyJson(selectedCapability.template_bundle)}</pre>
                    </div>
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
