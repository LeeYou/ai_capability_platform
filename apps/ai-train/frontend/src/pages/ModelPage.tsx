import { useEffect, useState } from 'react'
import type { ModelArtifactItem } from '../types'
import { request, fetchList, statusTone } from '../api'
import { buildR7Workspace } from '../../../../frontend-common/src/r7Workspace.ts'

const workspace = buildR7Workspace(import.meta.env, 'ai-train')

export default function ModelPage() {
  const [modelArtifacts, setModelArtifacts] = useState<ModelArtifactItem[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [selectedModelArtifactId, setSelectedModelArtifactId] = useState<number | null>(null)
  const [modelDetail, setModelDetail] = useState<ModelArtifactItem | null>(null)

  useEffect(() => {
    let cancelled = false
    async function load() {
      try {
        const items = await fetchList<ModelArtifactItem>('/api/v1/models')
        if (!cancelled) {
          setModelArtifacts(items)
          setSelectedModelArtifactId((current) => current ?? items[0]?.artifact_id ?? null)
        }
      } catch (loadError) {
        if (!cancelled) setError(loadError instanceof Error ? loadError.message : '加载数据失败')
      } finally {
        if (!cancelled) setLoading(false)
      }
    }
    void load()
    return () => { cancelled = true }
  }, [])

  useEffect(() => {
    if (selectedModelArtifactId == null) return
    let cancelled = false
    void request<ModelArtifactItem>(`/api/v1/models/${selectedModelArtifactId}`).then((detail) => {
      if (!cancelled) setModelDetail(detail)
    })
    return () => { cancelled = true }
  }, [selectedModelArtifactId])

  return (
    <div className="page-container">
      {loading && <p className="info-text">正在加载模型资产数据...</p>}
      {error && <p className="error-text">数据加载失败：{error}</p>}
      <div className="workspace-panel-grid">
        <div className="workspace-stack">
          <article className="workspace-note-block">
            <div className="section-header">
              <h3>模型资产列表</h3>
              <span className="badge badge-muted">T19-T20</span>
            </div>
            <div className="workspace-list">
              {modelArtifacts.map((item) => (
                <button
                  key={item.artifact_id}
                  className={`workspace-list-item${selectedModelArtifactId === item.artifact_id ? ' active' : ''}`}
                  onClick={() => setSelectedModelArtifactId(item.artifact_id)}
                  type="button"
                >
                  <strong>{item.capability_name}</strong>
                  <div className="workspace-meta-row">
                    <span>{item.model_version}</span>
                    <span>{item.backend_type}</span>
                    <span className={`status-pill ${statusTone(item.status)}`}>{item.status}</span>
                  </div>
                </button>
              ))}
            </div>
          </article>
        </div>
        <div className="workspace-stack">
          <article className="workspace-note-block">
            <div className="section-header">
              <h3>模型卡片与送测动作</h3>
              {modelDetail && <span className={`status-pill ${statusTone(modelDetail.status)}`}>{modelDetail.status}</span>}
            </div>
            {!modelDetail ? (
              <div className="workspace-empty">请选择模型查看详情。</div>
            ) : (
              <>
                <div className="workspace-kpi-grid">
                  <article className="workspace-kpi-card">
                    <span>模型版本</span>
                    <strong>{modelDetail.model_version}</strong>
                  </article>
                  <article className="workspace-kpi-card">
                    <span>来源训练任务</span>
                    <strong>{modelDetail.source_training_task_id}</strong>
                  </article>
                  <article className="workspace-kpi-card">
                    <span>后端</span>
                    <strong>{modelDetail.backend_type}</strong>
                  </article>
                </div>
                <div className="workspace-action-row">
                  {workspace.nextModule && (
                    <a className="workspace-action-chip" href={workspace.nextModule.url}>
                      送测到 {workspace.nextModule.shortTitle}
                    </a>
                  )}
                </div>
                <pre className="workspace-code-block">{JSON.stringify(modelDetail.manifest_preview ?? {}, null, 2)}</pre>
                <pre className="workspace-code-block">{JSON.stringify(modelDetail.runtime_contract ?? {}, null, 2)}</pre>
                <pre className="workspace-code-block">{JSON.stringify(modelDetail.delivery_metadata ?? {}, null, 2)}</pre>
              </>
            )}
          </article>
        </div>
      </div>
    </div>
  )
}
