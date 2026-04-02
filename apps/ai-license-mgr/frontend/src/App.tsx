import { useEffect, useMemo, useState } from 'react'
import './App.css'

type CustomerItem = {
  customer_id: number
  customer_code: string
  customer_name: string
  status: string
}

type KeyPairItem = {
  key_pair_id: number
  key_name: string
  algorithm: string
  status: string
}

type LicensePolicyItem = {
  policy_id: number
  policy_name: string
  customer_code: string
  key_name: string
  status: string
}

type LicenseIssueItem = {
  issue_record_id: number
  customer_code: string
  key_name: string
  status: string
  issued_at_cst: string
}

type AuditLogItem = {
  happened_at_cst: string
  action: string
  entity_type: string
  entity_id: string
}

type ApiListResponse<T> = {
  items: T[]
}

type DashboardState = {
  customers: CustomerItem[]
  keyPairs: KeyPairItem[]
  policies: LicensePolicyItem[]
  issues: LicenseIssueItem[]
  auditLogs: AuditLogItem[]
}

const initialState: DashboardState = {
  customers: [],
  keyPairs: [],
  policies: [],
  issues: [],
  auditLogs: [],
}

const roadmapItems = [
  '客户台表单、策略编辑与签发操作页',
  'license 文件下载与校验结果详情展示',
  'builder / prod 模块联调所需的授权查询对接',
  '更丰富的审计筛选与轮转归档能力',
]

async function fetchList<T>(path: string): Promise<ApiListResponse<T>> {
  const apiBaseUrl = import.meta.env.VITE_API_BASE_URL ?? ''
  const response = await fetch(`${apiBaseUrl}${path}`)
  if (!response.ok) {
    throw new Error(`请求失败：${path}`)
  }
  return (await response.json()) as ApiListResponse<T>
}

function App() {
  const [dashboard, setDashboard] = useState<DashboardState>(initialState)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false

    async function loadDashboard(): Promise<void> {
      try {
        setLoading(true)
        setError(null)
        const [customers, keyPairs, policies, issues, auditLogs] = await Promise.all([
          fetchList<CustomerItem>('/api/v1/customers'),
          fetchList<KeyPairItem>('/api/v1/key-pairs'),
          fetchList<LicensePolicyItem>('/api/v1/license-policies'),
          fetchList<LicenseIssueItem>('/api/v1/license-issues'),
          fetchList<AuditLogItem>('/api/v1/audit-logs?limit=5'),
        ])
        if (!cancelled) {
          setDashboard({
            customers: customers.items,
            keyPairs: keyPairs.items,
            policies: policies.items,
            issues: issues.items,
            auditLogs: auditLogs.items,
          })
        }
      } catch (loadError) {
        if (!cancelled) {
          setError(loadError instanceof Error ? loadError.message : '加载失败')
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
        title: '客户',
        count: dashboard.customers.length,
        description: '维护客户主体信息，支撑授权对象管理。',
      },
      {
        title: '密钥对',
        count: dashboard.keyPairs.length,
        description: '采用成熟密码学库生成 ed25519 密钥对并控制落盘权限。',
      },
      {
        title: '授权策略',
        count: dashboard.policies.length,
        description: '覆盖时间、硬件指纹、能力范围与版本约束。',
      },
      {
        title: '签发记录',
        count: dashboard.issues.length,
        description: '支持 license.bin 与 pubkey.pem 生成、追溯与导出。',
      },
    ],
    [dashboard],
  )

  return (
    <div className="page">
      <header className="hero">
        <div className="hero-text">
          <p className="eyebrow">北京爱知之星科技股份有限公司（Agile Star）</p>
          <h1>ai-license-mgr 管理台</h1>
          <p>
            面向客户、密钥、授权策略与签发记录的统一授权管理子系统，当前已具备 license
            生成、校验、导出与审计日志基础能力。
          </p>
        </div>
        <div className="hero-panel">
          <div>
            <span className="label">服务端口</span>
            <strong>26002</strong>
          </div>
          <div>
            <span className="label">技术栈</span>
            <strong>FastAPI + React + Vite</strong>
          </div>
          <div>
            <span className="label">标准文件</span>
            <strong>license.bin / pubkey.pem</strong>
          </div>
        </div>
      </header>

      <main className="content">
        <section className="panel">
          <div className="section-header">
            <h2>当前概览</h2>
            <span className="badge">ai-license-mgr 首轮实现中</span>
          </div>
          {loading && <p className="info-text">正在加载 ai-license-mgr 当前数据...</p>}
          {error && <p className="error-text">数据加载失败：{error}</p>}
          <div className="card-grid">
            {overviewCards.map((card) => (
              <article key={card.title} className="card">
                <h3>{card.title}</h3>
                <strong>{card.count}</strong>
                <p>{card.description}</p>
              </article>
            ))}
          </div>
        </section>

        <section className="panel">
          <div className="section-header">
            <h2>实时数据看板</h2>
            <span className="badge badge-muted">接口驱动</span>
          </div>
          <div className="table-grid">
            <article className="sub-panel">
              <h3>客户</h3>
              <table>
                <thead>
                  <tr>
                    <th>编码</th>
                    <th>名称</th>
                    <th>状态</th>
                  </tr>
                </thead>
                <tbody>
                  {dashboard.customers.map((item) => (
                    <tr key={item.customer_id}>
                      <td>{item.customer_code}</td>
                      <td>{item.customer_name}</td>
                      <td>{item.status}</td>
                    </tr>
                  ))}
                  {dashboard.customers.length === 0 && (
                    <tr>
                      <td colSpan={3}>暂无客户</td>
                    </tr>
                  )}
                </tbody>
              </table>
            </article>

            <article className="sub-panel">
              <h3>密钥对</h3>
              <table>
                <thead>
                  <tr>
                    <th>名称</th>
                    <th>算法</th>
                    <th>状态</th>
                  </tr>
                </thead>
                <tbody>
                  {dashboard.keyPairs.map((item) => (
                    <tr key={item.key_pair_id}>
                      <td>{item.key_name}</td>
                      <td>{item.algorithm}</td>
                      <td>{item.status}</td>
                    </tr>
                  ))}
                  {dashboard.keyPairs.length === 0 && (
                    <tr>
                      <td colSpan={3}>暂无密钥对</td>
                    </tr>
                  )}
                </tbody>
              </table>
            </article>

            <article className="sub-panel">
              <h3>授权策略</h3>
              <table>
                <thead>
                  <tr>
                    <th>策略</th>
                    <th>客户</th>
                    <th>密钥</th>
                  </tr>
                </thead>
                <tbody>
                  {dashboard.policies.map((item) => (
                    <tr key={item.policy_id}>
                      <td>{item.policy_name}</td>
                      <td>{item.customer_code}</td>
                      <td>{item.key_name}</td>
                    </tr>
                  ))}
                  {dashboard.policies.length === 0 && (
                    <tr>
                      <td colSpan={3}>暂无授权策略</td>
                    </tr>
                  )}
                </tbody>
              </table>
            </article>

            <article className="sub-panel">
              <h3>签发记录</h3>
              <table>
                <thead>
                  <tr>
                    <th>客户</th>
                    <th>密钥</th>
                    <th>状态</th>
                  </tr>
                </thead>
                <tbody>
                  {dashboard.issues.map((item) => (
                    <tr key={item.issue_record_id}>
                      <td>{item.customer_code}</td>
                      <td>{item.key_name}</td>
                      <td>{item.status}</td>
                    </tr>
                  ))}
                  {dashboard.issues.length === 0 && (
                    <tr>
                      <td colSpan={3}>暂无签发记录</td>
                    </tr>
                  )}
                </tbody>
              </table>
            </article>
          </div>
        </section>

        <section className="panel split">
          <article className="sub-panel">
            <h2>最近审计日志</h2>
            <ul>
              {dashboard.auditLogs.length === 0 && <li>暂无审计记录</li>}
              {dashboard.auditLogs.map((item) => (
                <li key={`${item.entity_type}-${item.entity_id}-${item.happened_at_cst}`}>
                  {item.happened_at_cst} / {item.action} / {item.entity_type} #{item.entity_id}
                </li>
              ))}
            </ul>
          </article>
          <article className="sub-panel">
            <h2>后续增强方向</h2>
            <ul>
              {roadmapItems.map((item) => (
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
