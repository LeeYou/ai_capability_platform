import { useEffect, useState } from 'react'
import { request, fetchList, statusTone } from '../api'
import type {
  KeyPairItem,
  LicensePolicyItem,
  LicenseIssueItem,
} from '../types'

export default function RiskPage() {
  const [keyPairs, setKeyPairs] = useState<KeyPairItem[]>([])
  const [policies, setPolicies] = useState<LicensePolicyItem[]>([])
  const [issues, setIssues] = useState<LicenseIssueItem[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [actionMessage, setActionMessage] = useState<string | null>(null)
  const [selectedKeyPairId, setSelectedKeyPairId] = useState<number | null>(null)
  const [rotateReason, setRotateReason] = useState('例行轮转')
  const [isolateReason, setIsolateReason] = useState('风险隔离')

  async function loadData(): Promise<void> {
    setLoading(true)
    setError(null)
    try {
      const [kp, pol, iss] = await Promise.all([
        fetchList<KeyPairItem>('/api/v1/key-pairs'),
        fetchList<LicensePolicyItem>('/api/v1/license-policies'),
        fetchList<LicenseIssueItem>('/api/v1/license-issues'),
      ])
      setKeyPairs(kp)
      setPolicies(pol)
      setIssues(iss)
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

  async function handleRotateKeyPair(): Promise<void> {
    if (selectedKeyPairId == null) return
    try {
      setActionMessage('正在轮转密钥对...')
      await request(`/api/v1/key-pairs/${selectedKeyPairId}/rotate`, {
        method: 'POST',
        body: JSON.stringify({ reason: rotateReason }),
      })
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

  return (
    <div className="page-container">
      <section className="panel">
        <div className="section-header">
          <div>
            <h2>风险操作工作台</h2>
            <p>围绕密钥轮转、隔离与影响面分析组织风险管控流程。</p>
          </div>
        </div>
        {loading && <p className="info-text">正在加载数据...</p>}
        {error && <p className="error-text">数据加载失败：{error}</p>}
        {actionMessage && <p className="success-text">{actionMessage}</p>}

        <div className="workspace-panel-grid">
          <div className="workspace-stack">
            <article className="workspace-note-block">
              <div className="section-header">
                <h3>高风险操作工作台</h3>
                <span className="badge badge-muted">L17</span>
              </div>
              <div className="workspace-list">
                {keyPairs.map((item) => (
                  <button
                    key={item.key_pair_id}
                    className={`workspace-list-item${selectedKeyPairId === item.key_pair_id ? ' active' : ''}`}
                    onClick={() => setSelectedKeyPairId(item.key_pair_id)}
                    type="button"
                  >
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
                      <strong>{policies.filter((item) => item.key_pair_id === selectedKeyPair.key_pair_id).length}</strong>
                    </article>
                    <article className="workspace-kpi-card">
                      <span>关联签发</span>
                      <strong>{issues.filter((item) => item.key_pair_id === selectedKeyPair.key_pair_id).length}</strong>
                    </article>
                    <article className="workspace-kpi-card">
                      <span>当前状态</span>
                      <strong>{selectedKeyPair.status}</strong>
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
                  <div className="button-row">
                    <button onClick={() => void handleRotateKeyPair()} type="button">执行轮转</button>
                    <button onClick={() => void handleIsolateKeyPair()} type="button">执行隔离</button>
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
