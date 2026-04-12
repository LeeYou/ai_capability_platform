import { useEffect, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { request, fetchList } from '../api'
import type {
  CatalogResponse,
  BuildTaskDetail,
  BuildFormState,
  BuildTaskItem,
} from '../types'
import { initialBuildForm } from '../types'

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
    setLoading(true)
    Promise.all([
      request<CatalogResponse>('/api/v1/catalog'),
      fetchList<BuildTaskItem>('/api/v1/build-tasks'),
    ])
      .then(([catalogData]) => {
        setCatalog(catalogData)
        setBuildForm((current) => ({
          ...current,
          capability_name: current.capability_name || catalogData.models[0]?.capability_name || '',
          model_version: current.model_version || catalogData.models[0]?.model_version || '',
          issue_record_id: current.issue_record_id || String(catalogData.license_issues[0]?.issue_record_id ?? ''),
        }))
      })
      .catch(() => {
        /* catalog load errors are non-fatal for wizard */
      })
      .finally(() => setLoading(false))
  }, [])

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
          requested_targets: buildForm.requested_targets
            .split(',')
            .map((item) => item.trim())
            .filter(Boolean),
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
        {actionMessage && <p className="success-text">{actionMessage}</p>}
        {loading && <p className="info-text">正在加载目录数据...</p>}
        <div className="workspace-panel-grid">
          <div className="workspace-stack">
            <article className="workspace-note-block">
              <div className="section-header">
                <h3>构建向导</h3>
                <span className="badge badge-muted">B15</span>
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
                      <option key={`${item.capability_name}-${item.model_version}`} value={item.capability_name}>
                        {item.capability_name}
                      </option>
                    ))}
                  </select>
                </label>
                <label className="workspace-field">
                  模型版本
                  <select value={buildForm.model_version} onChange={(event) => setBuildForm((current) => ({ ...current, model_version: event.target.value }))}>
                    {catalog.models
                      .filter((item) => item.capability_name === buildForm.capability_name)
                      .map((item) => (
                        <option key={item.model_version} value={item.model_version}>
                          {item.model_version}
                        </option>
                      ))}
                  </select>
                </label>
                <label className="workspace-field">
                  授权记录
                  <select value={buildForm.issue_record_id} onChange={(event) => setBuildForm((current) => ({ ...current, issue_record_id: event.target.value }))}>
                    {catalog.license_issues.map((item) => (
                      <option key={item.issue_record_id} value={String(item.issue_record_id)}>
                        #{item.issue_record_id} / {item.customer_code}
                      </option>
                    ))}
                  </select>
                </label>
                <label className="workspace-field full-span">
                  平台目标（逗号分隔）
                  <input value={buildForm.requested_targets} onChange={(event) => setBuildForm((current) => ({ ...current, requested_targets: event.target.value }))} placeholder="linux_x86_64, windows_x86_64" />
                </label>
                <label className="workspace-field">
                  JNI 交付
                  <select
                    value={buildForm.jni_enabled ? 'true' : 'false'}
                    onChange={(event) => setBuildForm((current) => ({ ...current, jni_enabled: event.target.value === 'true' }))}
                  >
                    <option value="false">关闭</option>
                    <option value="true">开启</option>
                  </select>
                </label>
              </div>
              <div className="button-row">
                <button onClick={() => void handleCreateBuildTask()} type="button">创建构建任务</button>
              </div>
            </article>
          </div>
          <div className="workspace-stack">
            <article className="workspace-note-block">
              <h3>交付预览</h3>
              <div className="workspace-kpi-grid">
                <article className="workspace-kpi-card">
                  <span>模型</span>
                  <strong>{buildForm.capability_name || '-'}</strong>
                </article>
                <article className="workspace-kpi-card">
                  <span>版本</span>
                  <strong>{buildForm.model_version || '-'}</strong>
                </article>
                <article className="workspace-kpi-card">
                  <span>授权</span>
                  <strong>{buildForm.issue_record_id || '-'}</strong>
                </article>
              </div>
              <ul>
                <li>输出动态库、头文件、示例工程与标准 delivery_package。</li>
                <li>任务级 manifest 将记录 provenance、依赖摘要与校验链路。</li>
                <li>构建完成后直接进入 ai-prod 运行验收。</li>
              </ul>
            </article>
          </div>
        </div>
      </section>
    </div>
  )
}
