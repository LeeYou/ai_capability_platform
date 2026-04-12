import { useEffect, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { request, fetchList, statusTone, taskDeliveryDownloadUrl } from '../api'
import { buildR7Workspace } from '../../../../frontend-common/src/r7Workspace.ts'
import type { BuildTaskItem, BuildTaskDetail } from '../types'

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
    setLoading(true)
    fetchList<BuildTaskItem>('/api/v1/build-tasks')
      .then((tasks) => {
        setBuildTasks(tasks)
        setSelectedTaskId((current) => current ?? tasks[0]?.task_id ?? null)
      })
      .catch(() => {
        /* non-fatal */
      })
      .finally(() => setLoading(false))
  }, [])

  useEffect(() => {
    if (selectedTaskId == null) {
      setSelectedTaskDetail(null)
      return
    }
    setSearchParams({ taskId: String(selectedTaskId) }, { replace: true })
    void request<BuildTaskDetail>(`/api/v1/build-tasks/${selectedTaskId}`).then(setSelectedTaskDetail).catch(() => {
      setSelectedTaskDetail(null)
    })
  }, [selectedTaskId])

  return (
    <div className="page-container">
      <section className="panel">
        {loading && <p className="info-text">正在加载交付包数据...</p>}
        <div className="workspace-panel-grid">
          <div className="workspace-stack">
            <article className="workspace-note-block">
              <div className="section-header">
                <h3>选择构建任务</h3>
                <span className="badge badge-muted">B17-B18</span>
              </div>
              <div className="workspace-list">
                {buildTasks.map((item) => (
                  <button
                    key={item.task_id}
                    className={`workspace-list-item${selectedTaskId === item.task_id ? ' active' : ''}`}
                    onClick={() => setSelectedTaskId(item.task_id)}
                    type="button"
                  >
                    <strong>任务 #{item.task_id} / {item.task_name}</strong>
                    <div className="workspace-meta-row">
                      <span>{item.capability_name}</span>
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
                <h3>delivery_package 目录树</h3>
              </div>
              {!selectedTaskDetail ? (
                <div className="workspace-empty">请选择构建任务查看交付包。</div>
              ) : (
                <>
                  <div className="workspace-action-row">
                    {selectedTaskDetail.delivery_package_archive_path && (
                      <a className="workspace-action-chip" href={taskDeliveryDownloadUrl(selectedTaskDetail.task_id)}>
                        下载 delivery_package
                      </a>
                    )}
                    {workspace.nextModule && (
                      <a className="workspace-action-chip" href={workspace.nextModule.url}>
                        去 {workspace.nextModule.shortTitle}
                      </a>
                    )}
                  </div>
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
                        {selectedTaskDetail.artifacts.map((item) => (
                          <tr key={item.artifact_id}>
                            <td>{item.artifact_type}</td>
                            <td>{item.relative_path}</td>
                            <td>{item.checksum.slice(0, 12)}...</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </>
              )}
            </article>
            <article className="workspace-note-block">
              <h3>manifest / provenance / 校验结果</h3>
              {!selectedTaskDetail?.manifest ? (
                <div className="workspace-empty">当前任务暂无 manifest 信息。</div>
              ) : (
                <pre className="workspace-code-block">{JSON.stringify(selectedTaskDetail.manifest.manifest, null, 2)}</pre>
              )}
            </article>
          </div>
        </div>
      </section>
    </div>
  )
}
