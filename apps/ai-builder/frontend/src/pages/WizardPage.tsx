import { useEffect, useMemo, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { request } from '../api'
import type {
  CatalogResponse,
  BuildTaskDetail,
  BuildFormState,
  CatalogModelItem,
  LicenseIssueItem,
  PlatformTargetItem,
} from '../types'
import { initialBuildForm } from '../types'
import { buildWizardChecklist, clampScore, scoreTone, summarizeTargets } from '../enterprise'

export default function WizardPage() {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const [catalog, setCatalog] = useState<CatalogResponse>({
    capabilities: [],
    models: [],
    license_issues: [],
    license_policies: [],
    synced_at: null,
  })
  const [allPlatforms, setAllPlatforms] = useState<PlatformTargetItem[]>([])
  const [buildForm, setBuildForm] = useState<BuildFormState>(() => {
    const capName = searchParams.get('capability_name') ?? ''
    const modelVer = searchParams.get('model_version') ?? ''
    return {
      ...initialBuildForm,
      capability_name: capName,
      model_version: modelVer,
      task_name: capName && modelVer ? `${capName}-${modelVer}-delivery` : '',
    }
  })
  const [actionMessage, setActionMessage] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let cancelled = false
    async function load() {
      try {
        const [catalogData, platformData] = await Promise.all([
          request<CatalogResponse>('/api/v1/catalog'),
          request<{ items: PlatformTargetItem[] }>('/api/v1/platform-targets'),
        ])
        if (!cancelled) {
          setCatalog(catalogData)
          setAllPlatforms(platformData.items)
          setBuildForm((current) => ({
            ...current,
            capability_name: current.capability_name || catalogData.models[0]?.capability_name || '',
            model_version: current.model_version || catalogData.models[0]?.model_version || '',
            issue_record_id: current.issue_record_id || String(catalogData.license_issues[0]?.issue_record_id ?? ''),
            requested_targets: current.requested_targets || platformData.items.slice(0, 2).map((item) => item.target_name).join(', '),
          }))
        }
      } catch {
        /* non-fatal */
      } finally {
        if (!cancelled) setLoading(false)
      }
    }
    void load()
    return () => { cancelled = true }
  }, [])

  const selectedModel = useMemo<CatalogModelItem | null>(() => {
    return catalog.models.find((item) => item.capability_name === buildForm.capability_name && item.model_version === buildForm.model_version) ?? null
  }, [buildForm.capability_name, buildForm.model_version, catalog.models])

  const selectedIssue = useMemo<LicenseIssueItem | null>(() => {
    const issueRecordId = Number(buildForm.issue_record_id)
    return catalog.license_issues.find((item) => item.issue_record_id === issueRecordId) ?? null
  }, [buildForm.issue_record_id, catalog.license_issues])

  const requestedTargetNames = buildForm.requested_targets.split(',').map((item) => item.trim()).filter(Boolean)
  const requestedTargets = useMemo(() => summarizeTargets(allPlatforms, requestedTargetNames), [allPlatforms, requestedTargetNames])
  const checklist = useMemo(() => buildWizardChecklist(catalog, buildForm, selectedModel, selectedIssue, requestedTargets), [buildForm, catalog, requestedTargets, selectedIssue, selectedModel])
  const wizardScore = clampScore((checklist.filter((item) => item.done).length / Math.max(1, checklist.length)) * 100)

  async function handleCreateBuildTask(): Promise<void> {
    try {
      setActionMessage('正在创建构建任务...')
      const created = await request<BuildTaskDetail>('/api/v1/build-tasks', {
        method: 'POST',
        body: JSON.stringify({
          task_name: buildForm.task_name,
          capability_name: buildForm.capability_name,
          model_version: buildForm.model_version,
          issue_record_id: Number(buildForm.issue_record_id),
          requested_targets: requestedTargetNames,
          jni_enabled: buildForm.jni_enabled,
        }),
      })
      setActionMessage(`构建任务 #${created.task_id} 已创建`)
      navigate(`/tasks?taskId=${created.task_id}`)
    } catch (loadError) {
      setActionMessage(loadError instanceof Error ? loadError.message : '创建构建任务失败')
    }
  }

  return (
    <div className="page-container">
      <section className="panel">
        <div className="section-header">
          <div>
            <h2>构建向导</h2>
            <p>把模型、授权、平台和 JNI 组合成连续向导，并在提交前给出构建门禁与交付预览。</p>
          </div>
          <span className="badge">B19-B22</span>
        </div>
        {actionMessage && <p className="success-text">{actionMessage}</p>}
        {loading && <p className="info-text">正在加载目录数据...</p>}
        <div className="enterprise-hero-grid">
          <article className={`enterprise-score-card tone-${scoreTone(wizardScore)}`}>
            <span>构建准备度</span>
            <strong>{wizardScore}</strong>
            <p>根据模型、授权、平台目标、目录加载和任务命名五项门禁计算。</p>
          </article>
          <article className="enterprise-note-card">
            <strong>向导目标</strong>
            <p>避免把平台参数、授权和模型选择散落在长表单里，而是在创建前先看到可交付内容、追溯关系和缺口。</p>
          </article>
        </div>
      </section>

      <section className="panel">
        <div className="workspace-panel-grid">
          <div className="workspace-stack">
            <article className="workspace-note-block">
              <div className="section-header">
                <h3>构建输入</h3>
                <span className="badge badge-muted">Wizard</span>
              </div>
              <div className="workspace-form-grid">
                <label className="workspace-field">
                  任务名称
                  <input value={buildForm.task_name} onChange={(event) => setBuildForm((current) => ({ ...current, task_name: event.target.value }))} />
                </label>
                <label className="workspace-field">
                  模型能力
                  <select value={buildForm.capability_name} onChange={(event) => setBuildForm((current) => ({ ...current, capability_name: event.target.value }))}>
                    {catalog.models.map((item) => (
                      <option key={`${item.capability_name}-${item.model_version}`} value={item.capability_name}>{item.capability_name}</option>
                    ))}
                  </select>
                </label>
                <label className="workspace-field">
                  模型版本
                  <select value={buildForm.model_version} onChange={(event) => setBuildForm((current) => ({ ...current, model_version: event.target.value }))}>
                    {catalog.models.filter((item) => item.capability_name === buildForm.capability_name).map((item) => (
                      <option key={item.model_version} value={item.model_version}>{item.model_version}</option>
                    ))}
                  </select>
                </label>
                <label className="workspace-field">
                  授权记录
                  <select value={buildForm.issue_record_id} onChange={(event) => setBuildForm((current) => ({ ...current, issue_record_id: event.target.value }))}>
                    {catalog.license_issues.map((item) => (
                      <option key={item.issue_record_id} value={String(item.issue_record_id)}>#{item.issue_record_id} / {item.customer_code}</option>
                    ))}
                  </select>
                </label>
                <label className="workspace-field full-span">
                  平台目标（逗号分隔）
                  <input value={buildForm.requested_targets} onChange={(event) => setBuildForm((current) => ({ ...current, requested_targets: event.target.value }))} placeholder="linux_x86_64, windows_x86_64" />
                </label>
                <label className="workspace-field">
                  JNI 交付
                  <select value={buildForm.jni_enabled ? 'true' : 'false'} onChange={(event) => setBuildForm((current) => ({ ...current, jni_enabled: event.target.value === 'true' }))}>
                    <option value="false">关闭</option>
                    <option value="true">开启</option>
                  </select>
                </label>
              </div>
              <div className="workspace-action-row">
                <button className="action-button" onClick={() => void handleCreateBuildTask()} type="button">创建构建任务</button>
              </div>
            </article>

            <article className="workspace-note-block">
              <strong>构建门禁</strong>
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
              <h3>交付预览</h3>
              <div className="workspace-kpi-grid">
                <article className="workspace-kpi-card">
                  <span>模型</span>
                  <strong>{selectedModel?.capability_name ?? '-'}</strong>
                </article>
                <article className="workspace-kpi-card">
                  <span>版本</span>
                  <strong>{selectedModel?.model_version ?? '-'}</strong>
                </article>
                <article className="workspace-kpi-card">
                  <span>授权</span>
                  <strong>{selectedIssue ? `#${selectedIssue.issue_record_id}` : '-'}</strong>
                </article>
                <article className="workspace-kpi-card">
                  <span>平台</span>
                  <strong>{requestedTargets.length}</strong>
                </article>
              </div>
              <div className="enterprise-two-column">
                <article className="enterprise-note-card">
                  <strong>模型来源</strong>
                  <p>backend: {selectedModel?.backend_type ?? '-'}</p>
                  <p>manifest: {selectedModel?.manifest_path ?? '-'}</p>
                  <p>checksum: {selectedModel?.checksum ?? '-'}</p>
                </article>
                <article className="enterprise-note-card">
                  <strong>授权来源</strong>
                  <p>issue: {selectedIssue?.issue_record_id ?? '-'}</p>
                  <p>客户: {selectedIssue?.customer_code ?? '-'}</p>
                  <p>能力范围: {selectedIssue?.capability_scope.join(', ') || '*'}</p>
                </article>
              </div>
            </article>

            <article className="workspace-note-block">
              <h3>目标平台与交付内容</h3>
              <div className="workspace-list">
                {requestedTargets.map((item) => (
                  <div key={item.target_name} className="workspace-list-item static-item">
                    <strong>{item.target_name}</strong>
                    <div className="workspace-meta-row">
                      <span>{item.os_name}/{item.arch_name}</span>
                      <span>{item.artifact_format}</span>
                      <span>{item.supports_jni ? '支持 JNI' : '无 JNI'}</span>
                    </div>
                  </div>
                ))}
              </div>
              <ul>
                <li>输出动态库、头文件、示例工程与标准 delivery_package。</li>
                <li>manifest 将记录模型、license、builder_task 的 provenance 关系。</li>
                <li>构建完成后继续到任务工作台检查失败建议，再进入 ai-prod 验收。</li>
              </ul>
            </article>
          </div>
        </div>
      </section>
    </div>
  )
}
