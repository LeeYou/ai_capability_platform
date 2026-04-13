import { useEffect, useMemo, useState } from 'react'
import type { CapabilityItem, ModelArtifactItem } from '../types'
import { fetchList, formatDateTime, request, statusTone } from '../api'
import { buildR7Workspace } from '../../../../frontend-common/src/r7Workspace.ts'
import { buildModelChecklist, buildModelComparisonRows, clampScore, pickBestModelArtifact, scoreTone } from '../enterprise'

const workspace = buildR7Workspace(import.meta.env, 'ai-train')

export default function ModelPage() {
  const [modelArtifacts, setModelArtifacts] = useState<ModelArtifactItem[]>([])
  const [capabilities, setCapabilities] = useState<CapabilityItem[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [selectedModelArtifactId, setSelectedModelArtifactId] = useState<number | null>(null)
  const [modelDetail, setModelDetail] = useState<ModelArtifactItem | null>(null)
  const [capabilityFilter, setCapabilityFilter] = useState('all')
  const [statusFilter, setStatusFilter] = useState('all')
  const [compareArtifactId, setCompareArtifactId] = useState<number | null>(null)

  useEffect(() => {
    let cancelled = false
    async function load() {
      try {
        const [items, capabilityItems] = await Promise.all([
          fetchList<ModelArtifactItem>('/api/v1/models'),
          fetchList<CapabilityItem>('/api/v1/capabilities'),
        ])
        if (!cancelled) {
          setModelArtifacts(items)
          setCapabilities(capabilityItems)
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

  const filteredArtifacts = useMemo(
    () =>
      modelArtifacts.filter((item) => {
        if (capabilityFilter !== 'all' && item.capability_name !== capabilityFilter) return false
        if (statusFilter !== 'all' && item.status !== statusFilter) return false
        return true
      }),
    [capabilityFilter, modelArtifacts, statusFilter],
  )

  const summaryCards = useMemo(() => {
    const readyCount = modelArtifacts.filter((item) => item.status === 'ready').length
    const capabilityCount = new Set(modelArtifacts.map((item) => item.capability_name)).size
    return [
      { title: '模型产物', value: modelArtifacts.length, detail: '已登记训练产物' },
      { title: '可送测版本', value: readyCount, detail: '状态为 ready 的版本' },
      { title: '覆盖能力', value: capabilityCount, detail: '已沉淀模型的能力数' },
    ]
  }, [modelArtifacts])
  const modelChecklist = useMemo(() => buildModelChecklist(modelDetail), [modelDetail])
  const modelReadinessScore = clampScore(modelChecklist.filter((item) => item.done).length / Math.max(1, modelChecklist.length) * 100)
  const downstreamTargets = Object.keys(modelDetail?.delivery_metadata ?? {})
  const sameCapabilityArtifacts = useMemo(
    () => modelArtifacts.filter((item) => item.capability_name === modelDetail?.capability_name && item.artifact_id !== modelDetail?.artifact_id),
    [modelArtifacts, modelDetail?.artifact_id, modelDetail?.capability_name],
  )
  const bestArtifactForCapability = useMemo(
    () => pickBestModelArtifact(modelArtifacts.filter((item) => item.capability_name === modelDetail?.capability_name)),
    [modelArtifacts, modelDetail?.capability_name],
  )
  const compareTarget = useMemo(
    () => sameCapabilityArtifacts.find((item) => item.artifact_id === compareArtifactId) ?? sameCapabilityArtifacts[0] ?? null,
    [compareArtifactId, sameCapabilityArtifacts],
  )
  const comparisonRows = useMemo(
    () => (modelDetail && compareTarget ? buildModelComparisonRows(modelDetail, compareTarget) : []),
    [compareTarget, modelDetail],
  )

  return (
    <div className="page-container">
      <section className="panel">
        <div className="section-header">
          <div>
            <h2>模型资产中心</h2>
            <p>集中查看训练导出物、运行契约、交付元数据与送测入口，并强化企业级版本治理。</p>
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
        <div className="enterprise-hero-grid">
          <article className={`enterprise-score-card tone-${scoreTone(modelReadinessScore)}`}>
            <span>版本发布成熟度</span>
            <strong>{modelReadinessScore}</strong>
            <p>综合 manifest、runtime contract、delivery metadata 和 ready 状态计算。</p>
          </article>
          <article className="enterprise-note-card">
            <strong>治理目标</strong>
            <p>让模型页不仅是“文件查看器”，而是训练产物进入验收/打包链路前的发布控制面板。</p>
          </article>
        </div>
      </section>

      <section className="panel">
        <div className="workspace-panel-grid">
          <div className="workspace-stack">
            <article className="workspace-note-block">
              <div className="section-header">
                <h3>模型资产列表</h3>
                <span className="badge badge-muted">T19-T20</span>
              </div>
              <div className="workspace-form-grid">
                <label className="workspace-field">
                  能力筛选
                  <select value={capabilityFilter} onChange={(event) => setCapabilityFilter(event.target.value)}>
                    <option value="all">全部</option>
                    {capabilities.map((item) => (
                      <option key={item.capability_name} value={item.capability_name}>{item.display_name}</option>
                    ))}
                  </select>
                </label>
                <label className="workspace-field">
                  状态筛选
                  <select value={statusFilter} onChange={(event) => setStatusFilter(event.target.value)}>
                    <option value="all">全部</option>
                    <option value="ready">ready</option>
                    <option value="draft">draft</option>
                    <option value="failed">failed</option>
                  </select>
                </label>
              </div>
              {loading && <div className="workspace-empty">正在加载模型资产数据...</div>}
              {error && <p className="error-text">数据加载失败：{error}</p>}
              {!loading && !error && filteredArtifacts.length === 0 && (
                <div className="workspace-empty">暂无符合筛选条件的模型资产。</div>
              )}
              {!loading && !error && filteredArtifacts.length > 0 && (
                <div className="workspace-list">
                  {filteredArtifacts.map((item) => (
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
                      <div className="workspace-meta-row">
                        <span>训练任务 #{item.source_training_task_id}</span>
                        <span>{formatDateTime(item.created_at)}</span>
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
                <h3>模型卡片与交付详情</h3>
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
                      <span>最近更新时间</span>
                      <strong className="kpi-date">{formatDateTime(modelDetail.updated_at)}</strong>
                    </article>
                  </div>
                  <div className="workspace-table-wrap">
                    <table className="workspace-table">
                      <tbody>
                        <tr><th>能力</th><td>{modelDetail.capability_name}</td><th>任务类型</th><td>{modelDetail.task_type}</td></tr>
                        <tr><th>产物目录</th><td colSpan={3}><code>{modelDetail.artifact_path}</code></td></tr>
                        <tr><th>Manifest</th><td colSpan={3}><code>{modelDetail.manifest_path}</code></td></tr>
                        <tr><th>Checksum</th><td colSpan={3}><code>{modelDetail.checksum}</code></td></tr>
                      </tbody>
                    </table>
                  </div>
                  <div className="workspace-action-row">
                    {workspace.nextModule && (
                      <a className="workspace-action-chip" href={workspace.nextModule.url}>
                        送测到 {workspace.nextModule.shortTitle}
                      </a>
                    )}
                    {bestArtifactForCapability && modelDetail.artifact_id === bestArtifactForCapability.artifact_id && (
                      <span className="badge">推荐最佳版本</span>
                    )}
                  </div>
                  <div className="enterprise-two-column">
                    <article className="enterprise-note-card">
                      <strong>发布清单</strong>
                      <ul className="enterprise-checklist">
                        {modelChecklist.map((item) => (
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
                    <article className="enterprise-note-card">
                      <strong>下游投递矩阵</strong>
                      <div className="enterprise-stack">
                        {downstreamTargets.length === 0 && <div className="workspace-empty">当前未声明下游投递目标。</div>}
                        {downstreamTargets.map((item) => (
                          <div key={item} className="enterprise-inline-card tone-good">
                            <strong>{item}</strong>
                            <p>已在 delivery_metadata 中声明。</p>
                          </div>
                        ))}
                      </div>
                    </article>
                  </div>
                  <div className="enterprise-two-column">
                    <article className="enterprise-note-card">
                      <strong>最佳版本判断</strong>
                      {!bestArtifactForCapability ? (
                        <div className="workspace-empty">当前能力暂无可推荐版本。</div>
                      ) : (
                        <div className={`enterprise-inline-card tone-${modelDetail.artifact_id === bestArtifactForCapability.artifact_id ? 'good' : 'warn'}`}>
                          <strong>{bestArtifactForCapability.model_version}</strong>
                          <p>
                            当前能力推荐版本为 #{bestArtifactForCapability.artifact_id}，
                            {modelDetail.artifact_id === bestArtifactForCapability.artifact_id ? '当前选中版本即最佳候选。' : '建议对比后决定是否送测。'}
                          </p>
                        </div>
                      )}
                    </article>
                    <article className="enterprise-note-card">
                      <strong>同能力版本对比</strong>
                      {sameCapabilityArtifacts.length === 0 ? (
                        <div className="workspace-empty">当前能力暂无其它版本可对比。</div>
                      ) : (
                        <>
                          <label className="workspace-field">
                            对比版本
                            <select
                              value={compareTarget ? String(compareTarget.artifact_id) : ''}
                              onChange={(event) => setCompareArtifactId(Number(event.target.value))}
                            >
                              {sameCapabilityArtifacts.map((item) => (
                                <option key={item.artifact_id} value={String(item.artifact_id)}>
                                  #{item.artifact_id} {item.model_version}
                                </option>
                              ))}
                            </select>
                          </label>
                          <div className="workspace-table-wrap">
                            <table className="workspace-table">
                              <thead>
                                <tr>
                                  <th>维度</th>
                                  <th>当前版本</th>
                                  <th>对比版本</th>
                                </tr>
                              </thead>
                              <tbody>
                                {comparisonRows.map((item) => (
                                  <tr key={item.label}>
                                    <td>{item.label}</td>
                                    <td className={item.same ? 'comparison-same' : 'comparison-diff'}><pre className="comparison-pre">{item.current}</pre></td>
                                    <td className={item.same ? 'comparison-same' : 'comparison-diff'}><pre className="comparison-pre">{item.baseline}</pre></td>
                                  </tr>
                                ))}
                              </tbody>
                            </table>
                          </div>
                        </>
                      )}
                    </article>
                  </div>
                  <div className="workspace-stack">
                    <div>
                      <h3>Manifest 预览</h3>
                      <pre className="workspace-code-block">{JSON.stringify(modelDetail.manifest_preview ?? {}, null, 2)}</pre>
                    </div>
                    <div>
                      <h3>运行时契约</h3>
                      <pre className="workspace-code-block">{JSON.stringify(modelDetail.runtime_contract ?? {}, null, 2)}</pre>
                    </div>
                    <div>
                      <h3>交付元数据</h3>
                      <pre className="workspace-code-block">{JSON.stringify(modelDetail.delivery_metadata ?? {}, null, 2)}</pre>
                    </div>
                    <div className="enterprise-note-card">
                      <strong>版本治理建议</strong>
                      <ul className="enterprise-list">
                        <li>优先保证 model_version 与训练任务、交付批次之间一一对应，避免手工覆盖。</li>
                        <li>模型 ready 后应尽快进入 ai-test，减少训练产物滞留。</li>
                        <li>如 runtime_contract 或 delivery_metadata 为空，应视为不可发布版本。</li>
                      </ul>
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
