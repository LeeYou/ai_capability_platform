import { useEffect, useMemo, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { request, fetchList, statusTone, taskDeliveryDownloadUrl } from '../api'
import { buildR7Workspace } from '../../../../frontend-common/src/r7Workspace.ts'
import type { BuildTaskItem, BuildTaskDetail } from '../types'
import { groupArtifacts } from '../enterprise'

const workspace = buildR7Workspace(import.meta.env, 'ai-builder')

export default function PackagePage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const [buildTasks, setBuildTasks] = useState<BuildTaskItem[]>([])
  const [selectedTaskId, setSelectedTaskId] = useState<number | null>(() => {
    const param = searchParams.get('taskId')
    return param ? Number(param) : null
  })
  const [selectedTaskDetail, setSelectedTaskDetail] = useState<BuildTaskDetail | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let cancelled = false
    async function load() {
      try {
        const tasks = await fetchList<BuildTaskItem>('/api/v1/build-tasks')
        if (!cancelled) {
          setBuildTasks(tasks)
          setSelectedTaskId((current) => current ?? tasks[0]?.task_id ?? null)
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

  useEffect(() => {
    if (selectedTaskId == null) return
    let cancelled = false
    setSearchParams({ taskId: String(selectedTaskId) }, { replace: true })
    void request<BuildTaskDetail>(`/api/v1/build-tasks/${selectedTaskId}`).then((d) => {
      if (!cancelled) setSelectedTaskDetail(d)
    }).catch(() => {
      if (!cancelled) setSelectedTaskDetail(null)
    })
    return () => { cancelled = true }
  }, [selectedTaskId, setSearchParams])

  const artifactGroups = useMemo(() => groupArtifacts(selectedTaskDetail?.artifacts ?? []), [selectedTaskDetail?.artifacts])
  const manifestPayload = selectedTaskDetail?.manifest?.manifest ?? null
  const dependencySummary = selectedTaskDetail?.manifest?.dependency_summary ?? null

  return (
    <div className="page-container">
      <section className="panel">
        <div className="section-header">
          <div>
            <h2>交付包资产视图</h2>
            <p>把 delivery_package 从“目录树 + JSON”升级为可交付资产视图，突出目录组成、provenance、校验结果与下游验收动作。</p>
          </div>
          <span className="badge">B19-B22</span>
        </div>
        {loading && <p className="info-text">正在加载交付包数据...</p>}
      </section>

      <section className="panel">
        <div className="workspace-panel-grid">
          <div className="workspace-stack">
            <article className="workspace-note-block">
              <div className="section-header">
                <h3>选择构建任务</h3>
                <span className="badge badge-muted">Package</span>
              </div>
              <div className="workspace-list">
                {buildTasks.map((item) => (
                  <button key={item.task_id} className={`workspace-list-item${selectedTaskId === item.task_id ? ' active' : ''}`} onClick={() => setSelectedTaskId(item.task_id)} type="button">
                    <strong>任务 #{item.task_id} / {item.task_name}</strong>
                    <div className="workspace-meta-row">
                      <span>{item.capability_name}</span>
                      <span>{item.model_version}</span>
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
                <h3>交付资产摘要</h3>
                {selectedTaskDetail && <span className={`status-pill ${statusTone(selectedTaskDetail.status)}`}>{selectedTaskDetail.status}</span>}
              </div>
              {!selectedTaskDetail ? (
                <div className="workspace-empty">请选择构建任务查看交付包。</div>
              ) : (
                <>
                  <div className="workspace-action-row">
                    {selectedTaskDetail.delivery_package_archive_path && (
                      <a className="workspace-action-chip" href={taskDeliveryDownloadUrl(selectedTaskDetail.task_id)}>下载 delivery_package</a>
                    )}
                    {workspace.nextModule && <a className="workspace-action-chip" href={workspace.nextModule.url}>去 {workspace.nextModule.shortTitle}</a>}
                  </div>
                  <div className="workspace-kpi-grid">
                    <article className="workspace-kpi-card">
                      <span>目标数</span>
                      <strong>{selectedTaskDetail.targets.length}</strong>
                    </article>
                    <article className="workspace-kpi-card">
                      <span>产物组</span>
                      <strong>{artifactGroups.length}</strong>
                    </article>
                    <article className="workspace-kpi-card">
                      <span>归档包</span>
                      <strong>{selectedTaskDetail.delivery_package_archive_path ? '已生成' : '待生成'}</strong>
                    </article>
                    <article className="workspace-kpi-card">
                      <span>manifest</span>
                      <strong>{selectedTaskDetail.manifest ? '可追溯' : '缺失'}</strong>
                    </article>
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
            <strong>delivery_package 目录树摘要</strong>
            <div className="workspace-table-wrap">
              <table className="workspace-table">
                <thead>
                  <tr>
                    <th>产物类型</th>
                    <th>数量</th>
                    <th>示例路径</th>
                  </tr>
                </thead>
                <tbody>
                  {artifactGroups.map((item) => (
                    <tr key={item.artifactType}>
                      <td>{item.artifactType}</td>
                      <td>{item.count}</td>
                      <td>{item.samplePaths.join(' / ')}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </article>
          <article className="enterprise-note-card">
            <strong>全量产物路径</strong>
            <div className="workspace-table-wrap">
              <table className="workspace-table">
                <thead>
                  <tr>
                    <th>类型</th>
                    <th>相对路径</th>
                    <th>校验</th>
                  </tr>
                </thead>
                <tbody>
                  {selectedTaskDetail?.artifacts.map((item) => (
                    <tr key={item.artifact_id}>
                      <td>{item.artifact_type}</td>
                      <td>{item.relative_path}</td>
                      <td>{item.checksum.slice(0, 12)}...</td>
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
            <strong>manifest / provenance</strong>
            <pre className="workspace-code-block">{JSON.stringify(manifestPayload, null, 2)}</pre>
          </article>
          <article className="enterprise-note-card">
            <strong>依赖摘要 / 校验结果</strong>
            <pre className="workspace-code-block">{JSON.stringify(dependencySummary, null, 2)}</pre>
          </article>
        </div>
      </section>

      <section className="panel">
        <article className="enterprise-note-card">
          <strong>下一步动作</strong>
          <ul>
            <li>先核对 delivery_package、checksum、manifest 与 provenance 是否同源。</li>
            <li>再将 delivery_package 推进到 {workspace.nextModule?.shortTitle ?? '下游模块'} 做运行验收。</li>
            <li>若任务失败，回到任务治理工作台优先处理失败目标与日志路径。</li>
          </ul>
        </article>
      </section>
    </div>
  )
}
