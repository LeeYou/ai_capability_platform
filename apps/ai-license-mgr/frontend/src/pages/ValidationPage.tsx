import { useEffect, useMemo, useState } from 'react'
import { request, fetchList, statusTone, issueExportUrl, toolExportUrl } from '../api'
import { buildR7Workspace } from '../../../../frontend-common/src/r7Workspace.ts'
import type {
  LicenseIssueItem,
  LicenseIssueDetail,
  LicenseToolReleaseItem,
  ValidateLicenseResult,
  ValidationContract,
  ValidationVectors,
  ValidationFormState,
} from '../types'
import { buildIssueComparison, buildValidationChecklist, clampScore, scoreTone } from '../enterprise'

const workspace = buildR7Workspace(import.meta.env, 'ai-license-mgr')

const initialValidationForm: ValidationFormState = {
  hardware_fingerprint: '',
  capability_name: '',
  product_version: '',
  operating_system: 'linux',
  operating_system_version: '',
  system_architecture: '',
}

export default function ValidationPage() {
  const [issues, setIssues] = useState<LicenseIssueItem[]>([])
  const [toolReleases, setToolReleases] = useState<LicenseToolReleaseItem[]>([])
  const [validationContract, setValidationContract] = useState<ValidationContract | null>(null)
  const [validationVectors, setValidationVectors] = useState<ValidationVectors | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [actionMessage, setActionMessage] = useState<string | null>(null)
  const [selectedIssueId, setSelectedIssueId] = useState<number | null>(null)
  const [issueDetail, setIssueDetail] = useState<LicenseIssueDetail | null>(null)
  const [validationForm, setValidationForm] = useState<ValidationFormState>(initialValidationForm)
  const [lastValidationResult, setLastValidationResult] = useState<ValidateLicenseResult | null>(null)

  async function loadData(): Promise<void> {
    setLoading(true)
    setError(null)
    try {
      const [iss, tr, vc, vv] = await Promise.all([
        fetchList<LicenseIssueItem>('/api/v1/license-issues'),
        fetchList<LicenseToolReleaseItem>('/api/v1/tool-releases'),
        request<ValidationContract>('/api/v1/license-validation/contract'),
        request<ValidationVectors>('/api/v1/license-validation/vectors'),
      ])
      setIssues(iss)
      setToolReleases(tr)
      setValidationContract(vc)
      setValidationVectors(vv)
      setSelectedIssueId((current) => current ?? iss[0]?.issue_record_id ?? null)
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : '加载失败')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    void loadData()
  }, [])

  useEffect(() => {
    if (selectedIssueId == null) {
      setIssueDetail(null)
      return
    }
    void request<LicenseIssueDetail>(`/api/v1/license-issues/${selectedIssueId}`).then(setIssueDetail).catch(() => {
      setIssueDetail(null)
    })
  }, [selectedIssueId])

  async function handleValidateIssue(): Promise<void> {
    if (selectedIssueId == null) return
    try {
      setActionMessage('正在执行授权校验...')
      const result = await request<ValidateLicenseResult>(`/api/v1/license-issues/${selectedIssueId}/validate`, {
        method: 'POST',
        body: JSON.stringify({
          hardware_fingerprint: validationForm.hardware_fingerprint || null,
          capability_name: validationForm.capability_name || null,
          product_version: validationForm.product_version || null,
          operating_system: validationForm.operating_system || null,
          operating_system_version: validationForm.operating_system_version || null,
          system_architecture: validationForm.system_architecture || null,
        }),
      })
      setLastValidationResult(result)
      setActionMessage(`校验完成：${result.code}`)
      await loadData()
    } catch (loadError) {
      setActionMessage(loadError instanceof Error ? loadError.message : '校验失败')
    }
  }

  async function handleSyncToolRelease(): Promise<void> {
    try {
      setActionMessage('正在同步默认 license_tool...')
      await request('/api/v1/tool-releases/sync-default', { method: 'POST' })
      setActionMessage('默认工具版本已同步')
      await loadData()
    } catch (loadError) {
      setActionMessage(loadError instanceof Error ? loadError.message : '同步工具失败')
    }
  }

  const linkedPolicy = issueDetail ? null : null
  const comparisonRows = useMemo(() => (issueDetail ? buildIssueComparison(issueDetail, linkedPolicy) : []), [issueDetail, linkedPolicy])
  const checklist = useMemo(() => buildValidationChecklist({
    issueDetail,
    result: lastValidationResult,
    contract: validationContract,
    vectors: validationVectors,
    tools: toolReleases,
  }), [issueDetail, lastValidationResult, toolReleases, validationContract, validationVectors])
  const validationScore = clampScore((checklist.filter((item) => item.done).length / Math.max(1, checklist.length)) * 100)

  return (
    <div className="page-container">
      <section className="panel">
        <div className="section-header">
          <div>
            <h2>校验与工具工作台</h2>
            <p>突出稳定 result / code / stage / details，并把 diagnostics、vectors、tool release 组合成同一契约工作台。</p>
          </div>
          <span className="badge">L20-L24</span>
        </div>
        {loading && <p className="info-text">正在加载数据...</p>}
        {error && <p className="error-text">数据加载失败：{error}</p>}
        {actionMessage && <p className="success-text">{actionMessage}</p>}
        <div className="enterprise-hero-grid">
          <article className={`enterprise-score-card tone-${scoreTone(validationScore)}`}>
            <span>校验工作台完整度</span>
            <strong>{validationScore}</strong>
            <p>根据签发记录、稳定结果、契约、向量和工具版本五项门禁计算。</p>
          </article>
          <article className="enterprise-note-card">
            <strong>工作台目标</strong>
            <p>让授权校验不再停留在“返回一句提示文本”，而是把稳定字段、契约和导出物一起做成可交付的诊断面板。</p>
          </article>
        </div>
      </section>

      <section className="panel">
        <div className="workspace-panel-grid">
          <div className="workspace-stack">
            <article className="workspace-note-block">
              <div className="section-header">
                <h3>签发记录与校验</h3>
                <span className="badge badge-muted">Validation</span>
              </div>
              <div className="workspace-list">
                {issues.map((item) => (
                  <button key={item.issue_record_id} className={`workspace-list-item${selectedIssueId === item.issue_record_id ? ' active' : ''}`} onClick={() => setSelectedIssueId(item.issue_record_id)} type="button">
                    <strong>签发 #{item.issue_record_id}</strong>
                    <div className="workspace-meta-row">
                      <span>{item.customer_code}</span>
                      <span>{item.application_name}</span>
                      <span className={`status-pill ${statusTone(item.status)}`}>{item.status}</span>
                    </div>
                  </button>
                ))}
              </div>
              <div className="workspace-form-grid" style={{ marginTop: 16 }}>
                <label className="workspace-field">
                  指纹
                  <input value={validationForm.hardware_fingerprint} onChange={(event) => setValidationForm((current) => ({ ...current, hardware_fingerprint: event.target.value }))} />
                </label>
                <label className="workspace-field">
                  能力
                  <input value={validationForm.capability_name} onChange={(event) => setValidationForm((current) => ({ ...current, capability_name: event.target.value }))} />
                </label>
                <label className="workspace-field">
                  产品版本
                  <input value={validationForm.product_version} onChange={(event) => setValidationForm((current) => ({ ...current, product_version: event.target.value }))} />
                </label>
                <label className="workspace-field">
                  OS
                  <input value={validationForm.operating_system} onChange={(event) => setValidationForm((current) => ({ ...current, operating_system: event.target.value }))} />
                </label>
                <label className="workspace-field">
                  OS 版本
                  <input value={validationForm.operating_system_version} onChange={(event) => setValidationForm((current) => ({ ...current, operating_system_version: event.target.value }))} />
                </label>
                <label className="workspace-field">
                  架构
                  <input value={validationForm.system_architecture} onChange={(event) => setValidationForm((current) => ({ ...current, system_architecture: event.target.value }))} />
                </label>
              </div>
              <div className="workspace-action-row">
                <button className="action-button" onClick={() => void handleValidateIssue()} type="button">执行校验</button>
              </div>
            </article>

            <article className="workspace-note-block">
              <strong>校验门禁</strong>
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
              <h3>稳定结果字段</h3>
              {lastValidationResult ? (
                <>
                  <div className="workspace-kpi-grid">
                    <article className="workspace-kpi-card">
                      <span>结果码</span>
                      <strong>{lastValidationResult.code}</strong>
                    </article>
                    <article className="workspace-kpi-card">
                      <span>阶段</span>
                      <strong>{lastValidationResult.stage}</strong>
                    </article>
                    <article className="workspace-kpi-card">
                      <span>结论</span>
                      <strong>{lastValidationResult.valid ? '通过' : '拒绝'}</strong>
                    </article>
                    <article className="workspace-kpi-card">
                      <span>契约版本</span>
                      <strong>{lastValidationResult.diagnostics_version}</strong>
                    </article>
                  </div>
                  <div className="enterprise-two-column">
                    <article className="enterprise-note-card">
                      <strong>details</strong>
                      <pre className="workspace-code-block">{JSON.stringify(lastValidationResult.details, null, 2)}</pre>
                    </article>
                    <article className="enterprise-note-card">
                      <strong>reason</strong>
                      <p>{lastValidationResult.reason}</p>
                      <p>checked_at: {lastValidationResult.checked_at_cst}</p>
                    </article>
                  </div>
                </>
              ) : (
                <div className="workspace-empty">执行一次校验后可查看稳定字段。</div>
              )}
            </article>

            <article className="workspace-note-block">
              <h3>签发载荷与导出</h3>
              {issueDetail ? (
                <>
                  <div className="workspace-action-row">
                    <a className="workspace-action-chip" href={issueExportUrl(issueDetail.issue_record_id, 'bin')}>导出 license.bin</a>
                    <a className="workspace-action-chip" href={issueExportUrl(issueDetail.issue_record_id, 'pubkey')}>导出 pubkey.pem</a>
                    {workspace.nextModule && (
                      <a className="workspace-action-chip" href={workspace.nextModule.url}>推进到 {workspace.nextModule.shortTitle}</a>
                    )}
                  </div>
                  <pre className="workspace-code-block">{JSON.stringify(issueDetail.payload, null, 2)}</pre>
                </>
              ) : (
                <div className="workspace-empty">请选择签发记录查看详细载荷。</div>
              )}
            </article>
          </div>
        </div>
      </section>

      <section className="panel">
        <div className="enterprise-two-column">
          <article className="enterprise-note-card">
            <strong>契约摘要</strong>
            <div className="workspace-kpi-grid">
              <article className="workspace-kpi-card">
                <span>字段数</span>
                <strong>{Object.keys(validationContract?.fields ?? {}).length}</strong>
              </article>
              <article className="workspace-kpi-card">
                <span>结果码数</span>
                <strong>{Object.keys(validationContract?.code_catalog ?? {}).length}</strong>
              </article>
              <article className="workspace-kpi-card">
                <span>测试向量</span>
                <strong>{validationVectors?.license_validation_vectors.length ?? 0}</strong>
              </article>
            </div>
            <pre className="workspace-code-block">{JSON.stringify(validationContract, null, 2)}</pre>
          </article>
          <article className="enterprise-note-card">
            <strong>签发与策略对照</strong>
            {comparisonRows.length === 0 ? (
              <div className="workspace-empty">当前仅展示签发载荷视角。</div>
            ) : (
              <div className="workspace-table-wrap">
                <table className="workspace-table">
                  <thead>
                    <tr>
                      <th>维度</th>
                      <th>签发记录</th>
                      <th>策略基线</th>
                    </tr>
                  </thead>
                  <tbody>
                    {comparisonRows.map((item) => (
                      <tr key={item.label}>
                        <td>{item.label}</td>
                        <td className={item.same ? 'comparison-same' : 'comparison-diff'}>{item.current}</td>
                        <td className={item.same ? 'comparison-same' : 'comparison-diff'}>{item.baseline}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </article>
        </div>
      </section>

      <section className="panel">
        <div className="enterprise-two-column">
          <article className="enterprise-note-card">
            <div className="section-header">
              <strong>tool release</strong>
              <button className="action-button" onClick={() => void handleSyncToolRelease()} type="button">同步默认工具版本</button>
            </div>
            <div className="workspace-list">
              {toolReleases.map((item) => (
                <div key={item.release_id} className="workspace-list-item static-item">
                  <strong>{item.tool_name} / {item.version}</strong>
                  <div className="workspace-meta-row">
                    <span className={`status-pill ${statusTone(item.status)}`}>{item.status}</span>
                    <a href={toolExportUrl(item.release_id, 'archive')}>归档</a>
                    <a href={toolExportUrl(item.release_id, 'diagnostics')}>诊断</a>
                    <a href={toolExportUrl(item.release_id, 'vectors')}>向量</a>
                  </div>
                </div>
              ))}
            </div>
          </article>
          <article className="enterprise-note-card">
            <strong>向量快照</strong>
            <pre className="workspace-code-block">{JSON.stringify(validationVectors, null, 2)}</pre>
          </article>
        </div>
      </section>
    </div>
  )
}
