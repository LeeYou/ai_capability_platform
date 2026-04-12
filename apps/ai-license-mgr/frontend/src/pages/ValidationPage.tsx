import { useEffect, useState } from 'react'
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

  return (
    <div className="page-container">
      <section className="panel">
        <div className="section-header">
          <div>
            <h2>校验与工具工作台</h2>
            <p>围绕诊断校验与 tool release 组织企业级授权流程。</p>
          </div>
        </div>
        {loading && <p className="info-text">正在加载数据...</p>}
        {error && <p className="error-text">数据加载失败：{error}</p>}
        {actionMessage && <p className="success-text">{actionMessage}</p>}

        <div className="workspace-panel-grid">
          <div className="workspace-stack">
            <article className="workspace-note-block">
              <div className="section-header">
                <h3>签发记录与校验</h3>
                <span className="badge badge-muted">L18-L19</span>
              </div>
              <div className="workspace-list">
                {issues.map((item) => (
                  <button
                    key={item.issue_record_id}
                    className={`workspace-list-item${selectedIssueId === item.issue_record_id ? ' active' : ''}`}
                    onClick={() => setSelectedIssueId(item.issue_record_id)}
                    type="button"
                  >
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
              <div className="button-row">
                <button onClick={() => void handleValidateIssue()} type="button">执行校验</button>
              </div>
            </article>

            <article className="workspace-note-block">
              <div className="section-header">
                <h3>tool release 与诊断材料</h3>
                <span className="badge badge-muted">L18</span>
              </div>
              <div className="button-row">
                <button onClick={() => void handleSyncToolRelease()} type="button">同步默认工具版本</button>
              </div>
              <div className="workspace-list" style={{ marginTop: 16 }}>
                {toolReleases.map((item) => (
                  <div key={item.release_id} className="workspace-list-item">
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
          </div>

          <div className="workspace-stack">
            <article className="workspace-note-block">
              <h3>校验详情与下游动作</h3>
              {lastValidationResult && (
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
                </div>
              )}
              {issueDetail ? (
                <>
                  <div className="workspace-action-row">
                    <a className="workspace-action-chip" href={issueExportUrl(issueDetail.issue_record_id, 'bin')}>导出 license.bin</a>
                    <a className="workspace-action-chip" href={issueExportUrl(issueDetail.issue_record_id, 'pubkey')}>导出 pubkey.pem</a>
                    {workspace.nextModule && (
                      <a className="workspace-action-chip" href={workspace.nextModule.url}>
                        推进到 {workspace.nextModule.shortTitle}
                      </a>
                    )}
                  </div>
                  <pre className="workspace-code-block">{JSON.stringify(issueDetail.payload, null, 2)}</pre>
                </>
              ) : (
                <div className="workspace-empty">请选择签发记录查看详细载荷。</div>
              )}
            </article>

            <article className="workspace-note-block">
              <h3>诊断契约摘要</h3>
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
            </article>
          </div>
        </div>
      </section>
    </div>
  )
}
