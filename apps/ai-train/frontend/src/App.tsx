import { useEffect, useMemo, useState } from 'react'
import './App.css'

const todoItems = [
  '补充标注台样本级操作与批量提交能力',
  '接入训练日志实时刷新与执行结果回显',
  '完善模型包内容生成（预处理、阈值、标签、校验文件）',
  '结合训练执行器推进容器化调度联动',
]

type CapabilityItem = {
  capability_name: string
  display_name: string
  dataset_path: string
  dataset_status: string
  source: string
}

type AnnotationTaskItem = {
  task_id: number
  capability_name: string
  task_name: string
  status: string
  sample_total: number
  labeled_count: number
}

type TrainingTaskItem = {
  task_id: number
  capability_name: string
  task_name: string
  status: string
  backend_type: string
  retry_count: number
  workspace_path?: string | null
}

type ModelArtifactItem = {
  artifact_id: number
  capability_name: string
  model_version: string
  backend_type: string
  status: string
}

type ApiListResponse<T> = {
  items: T[]
}

type DashboardData = {
  capabilities: CapabilityItem[]
  annotationTasks: AnnotationTaskItem[]
  trainingTasks: TrainingTaskItem[]
  modelArtifacts: ModelArtifactItem[]
}

const initialData: DashboardData = {
  capabilities: [],
  annotationTasks: [],
  trainingTasks: [],
  modelArtifacts: [],
}

async function fetchList<T>(path: string): Promise<T[]> {
  const apiBaseUrl = import.meta.env.VITE_API_BASE_URL ?? ''
  const response = await fetch(`${apiBaseUrl}${path}`)
  if (!response.ok) {
    throw new Error(`请求失败：${path}`)
  }

  const payload = (await response.json()) as ApiListResponse<T>
  return payload.items
}

function App() {
  const [data, setData] = useState<DashboardData>(initialData)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false

    async function loadDashboard(): Promise<void> {
      try {
        setLoading(true)
        setError(null)
        const [capabilities, annotationTasks, trainingTasks, modelArtifacts] =
          await Promise.all([
            fetchList<CapabilityItem>('/api/v1/capabilities'),
            fetchList<AnnotationTaskItem>('/api/v1/annotation-tasks'),
            fetchList<TrainingTaskItem>('/api/v1/training-tasks'),
            fetchList<ModelArtifactItem>('/api/v1/models'),
          ])

        if (!cancelled) {
          setData({
            capabilities,
            annotationTasks,
            trainingTasks,
            modelArtifacts,
          })
        }
      } catch (loadError) {
        if (!cancelled) {
          setError(loadError instanceof Error ? loadError.message : '加载数据失败')
        }
      } finally {
        if (!cancelled) {
          setLoading(false)
        }
      }
    }

    void loadDashboard()

    return () => {
      cancelled = true
    }
  }, [])

  const overviewCards = useMemo(
    () => [
      {
        title: '能力与数据集',
        status: `${data.capabilities.length} 个能力`,
        description: '能力注册、数据集绑定与状态同步已接入管理台。',
        apis: ['/api/v1/capabilities', '/api/v1/datasets'],
      },
      {
        title: '标注任务',
        status: `${data.annotationTasks.length} 个任务`,
        description: '展示标注任务状态、样本数量与当前完成进度。',
        apis: ['/api/v1/annotation-tasks', '/api/v1/annotation-tasks/{task_id}/submit'],
      },
      {
        title: '训练任务',
        status: `${data.trainingTasks.length} 个任务`,
        description: '展示训练任务状态、重试次数与工作区准备情况。',
        apis: ['/api/v1/training-tasks', '/api/v1/training-tasks/{task_id}/prepare'],
      },
      {
        title: '模型产物',
        status: `${data.modelArtifacts.length} 个版本`,
        description: '展示模型登记结果、版本信息与发布状态。',
        apis: ['/api/v1/models', '/api/v1/models/{artifact_id}'],
      },
    ],
    [data],
  )

  return (
    <div className="page">
      <header className="hero">
        <div>
          <p className="eyebrow">北京爱知之星科技股份有限公司（Agile Star）</p>
          <h1>ai-train 管理台</h1>
          <p className="hero-text">
            面向能力训练全生命周期的统一管理界面，当前已落地能力注册、数据集绑定、标注任务、
            训练任务与模型登记基础链路。
          </p>
        </div>
        <div className="hero-panel">
          <div>
            <span className="label">服务版本</span>
            <strong>v0.1.0</strong>
          </div>
          <div>
            <span className="label">默认端口</span>
            <strong>26000</strong>
          </div>
          <div>
            <span className="label">技术栈</span>
            <strong>React + TypeScript + Vite</strong>
          </div>
        </div>
      </header>

      <main className="content">
        <section className="panel">
          <div className="section-header">
            <h2>当前能力概览</h2>
            <span className="badge">第二轮持续推进中</span>
          </div>
          {loading && <p className="info-text">正在从 ai-train 后端加载最新概览数据...</p>}
          {error && <p className="error-text">数据加载失败：{error}</p>}
          <div className="card-grid">
            {overviewCards.map((card) => (
              <article key={card.title} className="card">
                <div className="card-header">
                  <h3>{card.title}</h3>
                  <span>{card.status}</span>
                </div>
                <p>{card.description}</p>
                <ul>
                  {card.apis.map((api) => (
                    <li key={api}>
                      <code>{api}</code>
                    </li>
                  ))}
                </ul>
              </article>
            ))}
          </div>
        </section>

        <section className="panel">
          <div className="section-header">
            <h2>管理台实时数据</h2>
            <span className="badge badge-muted">接口驱动</span>
          </div>
          <div className="data-grid">
            <article className="sub-panel">
              <h3>能力列表</h3>
              <div className="table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th>能力</th>
                      <th>数据集状态</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.capabilities.map((item) => (
                      <tr key={item.capability_name}>
                        <td>{item.display_name}</td>
                        <td>{item.dataset_status}</td>
                      </tr>
                    ))}
                    {data.capabilities.length === 0 && (
                      <tr>
                        <td colSpan={2}>暂无能力数据</td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            </article>

            <article className="sub-panel">
              <h3>标注任务</h3>
              <div className="table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th>任务</th>
                      <th>状态</th>
                      <th>进度</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.annotationTasks.map((item) => (
                      <tr key={item.task_id}>
                        <td>{item.task_name}</td>
                        <td>{item.status}</td>
                        <td>
                          {item.labeled_count}/{item.sample_total}
                        </td>
                      </tr>
                    ))}
                    {data.annotationTasks.length === 0 && (
                      <tr>
                        <td colSpan={3}>暂无标注任务</td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            </article>

            <article className="sub-panel">
              <h3>训练任务</h3>
              <div className="table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th>任务</th>
                      <th>状态</th>
                      <th>重试</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.trainingTasks.map((item) => (
                      <tr key={item.task_id}>
                        <td>{item.task_name}</td>
                        <td>{item.status}</td>
                        <td>{item.retry_count}</td>
                      </tr>
                    ))}
                    {data.trainingTasks.length === 0 && (
                      <tr>
                        <td colSpan={3}>暂无训练任务</td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            </article>

            <article className="sub-panel">
              <h3>模型产物</h3>
              <div className="table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th>能力</th>
                      <th>版本</th>
                      <th>状态</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.modelArtifacts.map((item) => (
                      <tr key={item.artifact_id}>
                        <td>{item.capability_name}</td>
                        <td>{item.model_version}</td>
                        <td>{item.status}</td>
                      </tr>
                    ))}
                    {data.modelArtifacts.length === 0 && (
                      <tr>
                        <td colSpan={3}>暂无模型产物</td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            </article>
          </div>
        </section>

        <section className="panel split">
          <article className="sub-panel">
            <h2>前端骨架目标</h2>
            <p>
              当前阶段已接入能力、标注任务、训练任务和模型产物的真实查询接口，后续继续补齐创建、提交、状态变更等交互操作。
            </p>
            <ol>
              <li>建设标注台、训练台、模型管理台独立页面</li>
              <li>增加状态刷新、错误提示与操作反馈</li>
              <li>补充表单提交与任务编排操作</li>
            </ol>
          </article>

          <article className="sub-panel">
            <h2>后续待办</h2>
            <ul className="todo-list">
              {todoItems.map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ul>
          </article>
        </section>
      </main>
    </div>
  )
}

export default App
