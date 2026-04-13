import { useEffect, useMemo, useState } from 'react'
import { request, fetchList, statusTone } from '../api'
import type {
  AuditLogItem,
  KeyPairItem,
  LicensePolicyItem,
  LicenseIssueItem,
  RotateKeyPairResponse,
} from '../types'
import { buildAuditRiskItems, buildRiskChecklist, clampScore, scoreTone } from '../enterprise'

export default function RiskPage() {
  const [keyPairs, setKeyPairs] = useState<KeyPairItem[]>([])
  const [policies, setPolicies] = useState<LicensePolicyItem[]>([])
  const [issues, setIssues] = useState<LicenseIssueItem[]>([])
  const [auditLogs, setAuditLogs] = useState<AuditLogItem[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [actionMessage, setActionMessage] = useState<string | null>(null)
  const [selectedKeyPairId, setSelectedKeyPairId] = useState<number | null>(null)
  const [rotateReason, setRotateReason] = useState('例行轮转')
  const [isolateReason, setIsolateReason] = useState('风险隔离')
  const [lastRotateResult, setLastRotateResult] = useState<RotateKeyPairResponse | null>(null)

  async function loadData(): Promise<void> {
    setLoading(true)
    setError(null)
    try {
      const [kp, pol, iss, logs] = await Promise.all([
        fetchList<KeyPairItem>('/api/v1/key-pairs'),
        fetchList<LicensePolicyItem>('/api/v1/license-policies'),
        fetchList<LicenseIssueItem>('/api/v1/license-issues'),
        fetchList<AuditLogItem>('/api/v1/audit-logs?limit=20'),
      ])
      setKeyPairs(kp)
      setPolicies(pol)
      setIssues(iss)
      setAuditLogs(logs)
      setSelectedKeyPairId((current) => current ?? kp[0]?.key_pair_id ?? null)
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : '加载失败')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    void loadData()
  }, [])

  const selectedKeyPair = keyPairs.find((item) => item.key_pair_id === selectedKeyPairId) ?? null
  const relatedPolicies = policies.filter((item) => item.key_pair_id === selectedKeyPairId)
  const relatedIssues = issues.filter((item) => item.key_pair_id === selectedKeyPairId)
  const relatedLogs = auditLogs.filter((item) => item.entity_type.includes('key') || item.detail.key_pair_id === selectedKeyPairId)

  async function handleRotateKeyPair(): Promise<void> {
    if (selectedKeyPairId == null) return
    try {
      setActionMessage('正在轮转密钥对...')
      const result = await request<RotateKeyPairResponse>(`/api/v1/key-pairs/${selectedKeyPairId}/rotate`, {
        method: 'POST',
        body: JSON.stringify({ reason: rotateReason }),
      })
      setLastRotateResult(result)
      setActionMessage('密钥轮转完成')
      await loadData()
    } catch (loadError) {
      setActionMessage(loadError instanceof Error ? loadError.message : '轮转失败')
    }
  }

  async function handleIsolateKeyPair(): Promise<void> {
    if (selectedKeyPairId == null) return
    try {
      setActionMessage('正在隔离密钥对...')
      await request(`/api/v1/key-pairs/${selectedKeyPairId}/isolate`, {
        method: 'POST',
        body: JSON.stringify({ reason: isolateReason }),
      })
      setActionMessage('密钥已隔离')
      await loadData()
    } catch (loadError) {
      setActionMessage(loadError instanceof Error ? loadError.message : '隔离失败')
    }
  }

  const checklist = useMemo(() => buildRiskChecklist(selectedKeyPair, relatedPolicies, relatedIssues), [relatedIssues, relatedPolicies, selectedKeyPair])
  const riskScore = clampScore((checklist.filter((item) => item.done).length / Math.max(1, checklist.length)) * 100)
  const auditRiskItems = useMemo(() => buildAuditRiskItems(relatedLogs), [relatedLogs])

  return (
    <div className="page-container">
      <section className="panel">
        <div className="section-header">
          <div>
            <h2>风险操作工作台</h2>
            <p>围绕轮转、隔离、影响面评估和审计确认，收口高风险授权动作。</p>
          </div>
          <span className="badge">L20-L24</span>
        </div>
        {loading && <p className="info-text">正在加载数据...</p>}
        {error && <p className="error-text">数据加载失败：{error}</p>}
        {actionMessage && <p className="success-text">{actionMessage}</p>}
        <div className="enterprise-hero-grid">
          <article className={`enterprise-score-card tone-${scoreTone(riskScore)}`}>
            <span>风险确认完整度</span>
            <strong>{riskScore}</strong>
            <p>根据风险对象选择、策略/签发影响面和当前隔离结论综合计算。</p>
          </article>
          <article className="enterprise-note-card">
            <strong>高风险动作原则</strong>
            <p>轮转、隔离前必须先看到影响策略、签发记录和审计证据，避免交付链路在无感知情况下失效。</p>
          </article>
        </div>
      </section>

      <section className="panel">
        <div className="workspace-panel-grid">
          <div className="workspace-stack">
            <article className="workspace-note-block">
              <div className="section-header">
                <h3>高风险对象列表</h3>
                <span className="badge badge-muted">Key Pairs</span>
              </div>
              <div className="workspace-list">
                {keyPairs.map((item) => (
                  <button key={item.key_pair_id} className={`workspace-list-item${selectedKeyPairId === item.key_pair_id ? ' active' : ''}`} onClick={() => setSelectedKeyPairId(item.key_pair_id)} type="button">
                    <strong>{item.key_name}</strong>
                    <div className="workspace-meta-row">
                      <span>版本 {item.rotation_version}</span>
                      <span>{item.algorithm}</span>
                      <span className={`status-pill ${statusTone(item.status)}`}>{item.status}</span>
                    </div>
                  </button>
                ))}
              </div>
            </article>
          </div>
          <div className="workspace-stack">
            <article className="workspace-note-block">
              <h3>影响面与确认说明</h3>
              {!selectedKeyPair ? (
                <div className="workspace-empty">请选择密钥对查看影响范围。</div>
              ) : (
                <>
                  <div className="workspace-kpi-grid">
                    <article className="workspace-kpi-card">
                      <span>关联策略</span>
                      <strong>{relatedPolicies.length}</strong>
                    </article>
                    <article className="workspace-kpi-card">
                      <span>关联签发</span>
                      <strong>{relatedIssues.length}</strong>
                    </article>
                    <article className="workspace-kpi-card">
                      <span>轮转版本</span>
                      <strong>{selectedKeyPair.rotation_version}</strong>
                    </article>
                    <article className="workspace-kpi-card">
                      <span>当前状态</span>
                      <strong>{selectedKeyPair.status}</strong>
                    </article>
                  </div>
                  <div className="enterprise-two-column">
                    <article className="enterprise-note-card">
                      <strong>高风险门禁</strong>
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
                    <article className="enterprise-note-card">
                      <strong>审计风险摘要</strong>
                      <div className="enterprise-stack">
                        {auditRiskItems.map((item) => (
                          <div key={item.title} className={`enterprise-inline-card tone-${item.tone}`}>
                            <strong>{item.title}</strong>
                            <p>{item.detail}</p>
                          </div>
                        ))}
                      </div>
                    </article>
                  </div>
                  <div className="workspace-form-grid" style={{ marginTop: 16 }}>
                    <label className="workspace-field">
                      轮转说明
                      <input value={rotateReason} onChange={(event) => setRotateReason(event.target.value)} />
                    </label>
                    <label className="workspace-field">
                      隔离说明
                      <input value={isolateReason} onChange={(event) => setIsolateReason(event.target.value)} />
                    </label>
                  </div>
                  <div className="workspace-action-row">
                    <button className="action-button" onClick={() => void handleRotateKeyPair()} type="button">执行轮转</button>
                    <button className="action-button danger-button" onClick={() => void handleIsolateKeyPair()} type="button">执行隔离</button>
                  </div>
                </>
              )}
            </article>
          </div>
        </div>
      </section>

      <section className="panel">
        <div className="enterprise-two-column">
          <article className="enterprise-note-card">
            <strong>关联策略</strong>
            <div className="workspace-table-wrap">
              <table className="workspace-table">
                <thead>
                  <tr>
                    <th>策略</th>
                    <th>客户</th>
                    <th>应用</th>
                    <th>状态</th>
                  </tr>
                </thead>
                <tbody>
                  {relatedPolicies.map((item) => (
                    <tr key={item.policy_id}>
                      <td>{item.policy_name}</td>
                      <td>{item.customer_code}</td>
                      <td>{item.application_name}</td>
                      <td><span className={`status-pill ${statusTone(item.status)}`}>{item.status}</span></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </article>
          <article className="enterprise-note-card">
            <strong>关联签发记录</strong>
            <div className="workspace-table-wrap">
              <table className="workspace-table">
                <thead>
                  <tr>
                    <th>签发ID</th>
                    <th>客户</th>
                    <th>应用</th>
                    <th>状态</th>
                  </tr>
                </thead>
                <tbody>
                  {relatedIssues.map((item) => (
                    <tr key={item.issue_record_id}>
                      <td>{item.issue_record_id}</td>
                      <td>{item.customer_code}</td>
                      <td>{item.application_name}</td>
                      <td><span className={`status-pill ${statusTone(item.status)}`}>{item.status}</span></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </article>
        </div>
      </section>

      <section className="panel">
        <div className="enterprise-two-column">
          <article className="enterprise-note-card">
            <strong>最近审计留痕</strong>
            <div className="workspace-table-wrap">
              <table className="workspace-table">
                <thead>
                  <tr>
                    <th>时间</th>
                    <th>动作</th>
                    <th>实体</th>
                  </tr>
                </thead>
                <tbody>
                  {relatedLogs.map((item) => (
                    <tr key={`${item.happened_at_cst}-${item.entity_id}`}>
                      <td>{item.happened_at_cst}</td>
                      <td>{item.action}</td>
                      <td>{item.entity_type} / {item.entity_id}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </article>
          <article className="enterprise-note-card">
            <strong>轮转结果摘要</strong>
            {!lastRotateResult ? (
              <div className="workspace-empty">尚未执行轮转。</div>
            ) : (
              <>
                <div className="workspace-kpi-grid">
                  <article className="workspace-kpi-card">
                    <span>原密钥</span>
                    <strong>{lastRotateResult.source_key_pair.key_name}</strong>
                  </article>
                  <article className="workspace-kpi-card">
                    <span>新密钥</span>
                    <strong>{lastRotateResult.new_key_pair.key_name}</strong>
                  </article>
                  <article className="workspace-kpi-card">
                    <span>迁移策略</span>
                    <strong>{lastRotateResult.migrated_policy_ids.length}</strong>
                  </article>
                </div>
                <pre className="workspace-code-block">{JSON.stringify(lastRotateResult, null, 2)}</pre>
              </>
            )}
          </article>
        </div>
      </section>
    </div>
  )
}
