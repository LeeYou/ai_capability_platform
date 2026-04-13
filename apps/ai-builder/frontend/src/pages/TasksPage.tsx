import { useEffect, useMemo, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { request, fetchList, statusTone, targetDownloadUrl } from '../api'
import type { BuildTaskItem, BuildTaskDetail } from '../types'
import { buildTaskChecklist, buildTaskRiskItems, clampScore, scoreTone } from '../enterprise'

export default function TasksPage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const [buildTasks, setBuildTasks] = useState<BuildTaskItem[]>([])
  const [selectedTaskId, setSelectedTaskId] = useState<number | null>(() => {
    const param = searchParams.get('taskId')
    return param ? Number(param) : null
  })
  const [selectedTaskDetail, setSelectedTaskDetail] = useState<BuildTaskDetail | null>(null)
  const [loading, setLoading] = useState(true)
  const [statusFilter, setStatusFilter] = useState('all')

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

  const filteredTasks = buildTasks.filter((item) => statusFilter === 'all' ? true : item.status === statusFilter)
  const checklist = useMemo(() => buildTaskChecklist(selectedTaskDetail), [selectedTaskDetail])
  const taskScore = clampScore((checklist.filter((item) => item.done).length / Math.max(1, checklist.length)) * 100)
  const riskItems = useMemo(() => buildTaskRiskItems(selectedTaskDetail), [selectedTaskDetail])

  return (
    <div className="page-container">
      <section className="panel">
        <div className="section-header">
          <div>
            <h2>任务治理工作台</h2>
            <p>把构建任务从列表页升级为队列治理、阶段摘要、失败建议和目标/产物联动工作台。</p>
          </div>
          <span className="badge">B19-B22</span>
        </div>
        {loading && <p className="info-text">正在加载构建任务...</p>}
        <div className="enterprise-hero-grid">
          <article className={`enterprise-score-card tone-${scoreTone(taskScore)}`}>
            <span>当前任务完成度</span>
            <strong>{taskScore}</strong>
            <p>根据目标、产物、manifest、交付包和终态五项门禁计算。</p>
          </article>
          <article className="enterprise-note-card">
            <strong>队列筛选</strong>
            <label className="workspace-field enterprise-search-field">
              任务状态
              <select value={statusFilter} onChange={(event) => setStatusFilter(event.target.value)}>
                <option value="all">全部</option>
                <option value="completed">completed</option>
                <option value="failed">failed</option>
                <option value="created">created</option>
              </select>
            </label>
          </article>
        </div>
      </section>

      <section className="panel">
        <div className="workspace-panel-grid">
          <div className="workspace-stack">
            <article className="workspace-note-block">
              <div className="section-header">
                <h3>构建任务队列</h3>
                <span className="badge badge-muted">Tasks</span>
              </div>
              <div className="workspace-list">
                {filteredTasks.map((item) => (
                  <button key={item.task_id} className={`workspace-list-item${selectedTaskId === item.task_id ? ' active' : ''}`} onClick={() => setSelectedTaskId(item.task_id)} type="button">
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
                <h3>阶段状态与失败建议</h3>
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
                    <article className="workspace-kpi-card">
                      <span>delivery_package</span>
                      <strong>{selectedTaskDetail.delivery_package_archive_path ? '已生成' : '待生成'}</strong>
                    </article>
                  </div>
                  <div className="enterprise-two-column">
                    <article className="enterprise-note-card">
                      <strong>任务门禁</strong>
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
                      <strong>风险摘要</strong>
                      <div className="enterprise-stack">
                        {riskItems.map((item) => (
                          <div key={item.title} className={`enterprise-inline-card tone-${item.tone}`}>
                            <strong>{item.title}</strong>
                            <p>{item.detail}</p>
                          </div>
                        ))}
                      </div>
                    </article>
                  </div>
                  <pre className="workspace-code-block">{selectedTaskDetail.log_path}</pre>
                </>
              )}
            </article>
          </div>
        </div>
      </section>

      <section className="panel">
        <div className="enterprise-two-column">
          <article className="enterprise-note-card">
            <strong>构建目标</strong>
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
                  {selectedTaskDetail?.targets.map((item) => (
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
          </article>
          <article className="enterprise-note-card">
            <strong>产物联动</strong>
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
    </div>
  )
}
