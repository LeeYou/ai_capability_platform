import { useEffect, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { request, fetchList, statusTone, targetDownloadUrl } from '../api'
import type { BuildTaskItem, BuildTaskDetail } from '../types'

export default function TasksPage() {
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
        {loading && <p className="info-text">正在加载构建任务...</p>}
        <div className="workspace-panel-grid">
          <div className="workspace-stack">
            <article className="workspace-note-block">
              <div className="section-header">
                <h3>构建任务队列</h3>
                <span className="badge badge-muted">B16</span>
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
                      <span>{item.model_version}</span>
                      <span>{item.requested_targets.join(', ') || '未指定'}</span>
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
                <h3>阶段状态与实时日志</h3>
                {selectedTaskDetail && <span className={`status-pill ${statusTone(selectedTaskDetail.status)}`}>{selectedTaskDetail.status}</span>}
              </div>
              {!selectedTaskDetail ? (
                <div className="workspace-empty">请选择构建任务查看详细内容。</div>
              ) : (
                <>
                  <div className="workspace-kpi-grid">
                    <article className="workspace-kpi-card">
                      <span>目标数</span>
                      <strong>{selectedTaskDetail.targets.length}</strong>
                    </article>
                    <article className="workspace-kpi-card">
                      <span>产物数</span>
                      <strong>{selectedTaskDetail.artifacts.length}</strong>
                    </article>
                    <article className="workspace-kpi-card">
                      <span>JNI</span>
                      <strong>{selectedTaskDetail.jni_enabled ? '开启' : '关闭'}</strong>
                    </article>
                  </div>
                  <pre className="workspace-code-block">{selectedTaskDetail.log_path}</pre>
                  <div className="workspace-table-wrap">
                    <table className="workspace-table">
                      <thead>
                        <tr>
                          <th>目标</th>
                          <th>状态</th>
                          <th>输出</th>
                          <th>操作</th>
                        </tr>
                      </thead>
                      <tbody>
                        {selectedTaskDetail.targets.map((item) => (
                          <tr key={item.target_id}>
                            <td>{item.target_name}</td>
                            <td><span className={`status-pill ${statusTone(item.status)}`}>{item.status}</span></td>
                            <td>{item.binary_path}</td>
                            <td><a href={targetDownloadUrl(item.target_id)}>下载归档</a></td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
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
