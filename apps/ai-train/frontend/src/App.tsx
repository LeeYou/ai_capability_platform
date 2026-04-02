import './App.css'

const overviewCards = [
  {
    title: '能力与数据集',
    status: '已具备后端能力',
    description: '支持能力注册、数据集绑定、目录同步与数据集状态查询。',
    apis: ['/api/v1/capabilities', '/api/v1/datasets'],
  },
  {
    title: '标注任务',
    status: '已具备后端能力',
    description: '支持标注任务创建、结果提交、状态跟踪与结果文件落盘。',
    apis: ['/api/v1/annotation-tasks', '/api/v1/annotation-tasks/{task_id}/submit'],
  },
  {
    title: '训练任务',
    status: '已具备后端能力',
    description: '支持训练任务创建、状态流转、日志追加与失败重试计数。',
    apis: ['/api/v1/training-tasks', '/api/v1/training-tasks/{task_id}/logs'],
  },
  {
    title: '模型产物',
    status: '已具备后端能力',
    description: '支持模型版本登记、manifest 生成、列表查询与详情查询。',
    apis: ['/api/v1/models', '/api/v1/models/{artifact_id}'],
  },
]

const todoItems = [
  '标注台交互界面与样本级操作能力',
  '训练执行器联动、任务调度与日志实时刷新',
  '完整模型包内容生成（预处理、阈值、标签、校验文件）',
  'CUDA 11.8 训练镜像与容器化交付',
]

function App() {
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

        <section className="panel split">
          <article className="sub-panel">
            <h2>前端骨架目标</h2>
            <p>
              当前阶段先补齐管理台基础布局，后续逐步接入能力列表、标注任务、训练任务和模型产物的真实接口数据。
            </p>
            <ol>
              <li>接入后端查询 API</li>
              <li>建设标注台、训练台、模型管理台页面</li>
              <li>增加状态刷新、错误提示与操作反馈</li>
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
