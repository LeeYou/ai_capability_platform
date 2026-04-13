import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { request, fetchList, statusTone } from '../api'
import type {
  CustomerItem,
  KeyPairItem,
  LicensePolicyItem,
  LicenseIssueItem,
  LicenseToolReleaseItem,
  AuditLogItem,
  ValidationContract,
  ValidationVectors,
  DashboardState,
} from '../types'
import { buildOverviewInsights, pickBestToolRelease } from '../enterprise'

const initialState: DashboardState = {
  customers: [],
  keyPairs: [],
  policies: [],
  issues: [],
  toolReleases: [],
  auditLogs: [],
  validationContract: null,
  validationVectors: null,
}

export default function OverviewPage() {
  const navigate = useNavigate()
  const [dashboard, setDashboard] = useState<DashboardState>(initialState)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  async function loadDashboard(): Promise<void> {
    setLoading(true)
    setError(null)
    try {
      const [customers, keyPairs, policies, issues, toolReleases, auditLogs, validationContract, validationVectors] = await Promise.all([
        fetchList<CustomerItem>('/api/v1/customers'),
        fetchList<KeyPairItem>('/api/v1/key-pairs'),
        fetchList<LicensePolicyItem>('/api/v1/license-policies'),
        fetchList<LicenseIssueItem>('/api/v1/license-issues'),
        fetchList<LicenseToolReleaseItem>('/api/v1/tool-releases'),
        fetchList<AuditLogItem>('/api/v1/audit-logs?limit=8'),
        request<ValidationContract>('/api/v1/license-validation/contract'),
        request<ValidationVectors>('/api/v1/license-validation/vectors'),
      ])
      setDashboard({ customers, keyPairs, policies, issues, toolReleases, auditLogs, validationContract, validationVectors })
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : '加载失败')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    void loadDashboard()
  }, [])

  const overviewInsights = useMemo(() => buildOverviewInsights(dashboard), [dashboard])
  const bestTool = useMemo(() => pickBestToolRelease(dashboard.toolReleases), [dashboard.toolReleases])
  const isolatedKeys = dashboard.keyPairs.filter((item) => item.status === 'isolated').slice(0, 4)
  const latestIssues = dashboard.issues.slice(0, 5)

  return (
    <div className="page-container">
      <section className="panel">
        <div className="section-header">
          <div>
            <h2>授权中枢首页</h2>
            <p>先拉齐参考授权平台的“客户 / 授权生成 / 授权列表 / 到期提醒 / 密钥管理”结构，再升级为企业级授权决策首页。</p>
          </div>
          <span className="badge">L20-L24</span>
        </div>
        {loading && <p className="info-text">正在加载授权工作台数据...</p>}
        {error && <p className="error-text">数据加载失败：{error}</p>}
        <div className="enterprise-hero-grid">
          <article className={`enterprise-score-card tone-${overviewInsights.stageCards[0]?.tone ?? 'neutral'}`}>
            <span>授权体系健康度</span>
            <strong>{overviewInsights.overallScore}</strong>
            <p>综合客户、密钥、签发与工具契约四段链路得出。</p>
          </article>
          <article className="enterprise-note-card">
            <strong>首页定位</strong>
            <p>让交付工程师先看到“哪些策略快到期、哪些密钥有风险、哪些签发能推进到构建”，而不是分散到多个列表页里查找。</p>
            <div className="workspace-action-row">
              <button className="action-button" onClick={() => navigate('/issuance')} type="button">进入连续签发</button>
              <button className="action-button" onClick={() => navigate('/risk')} type="button">查看风险操作</button>
              <button className="action-button" onClick={() => navigate('/validation')} type="button">校验与导出</button>
            </div>
          </article>
        </div>
        <div className="enterprise-stage-grid">
          {overviewInsights.stageCards.map((item) => (
            <article key={item.title} className={`enterprise-stage-card tone-${item.tone}`}>
              <span>{item.title}</span>
              <strong>{item.score}</strong>
              <p>{item.detail}</p>
              <small>当前对象：{item.count}</small>
            </article>
          ))}
        </div>
      </section>

      <section className="panel">
        <div className="enterprise-two-column">
          <article className="enterprise-note-card">
            <strong>30 天内到期策略</strong>
            {overviewInsights.expiringPolicies.length === 0 ? (
              <div className="workspace-empty">当前无 30 天内到期策略。</div>
            ) : (
              <div className="workspace-list">
                {overviewInsights.expiringPolicies.map((item) => (
                  <button key={item.policy_id} className="workspace-list-item" onClick={() => navigate('/policies')} type="button">
                    <strong>{item.policy_name}</strong>
                    <div className="workspace-meta-row">
                      <span>{item.customer_code}</span>
                      <span>{item.application_name}</span>
                      <span className={`status-pill ${statusTone(item.status)}`}>{item.status}</span>
                    </div>
                  </button>
                ))}
              </div>
            )}
          </article>
          <article className="enterprise-note-card">
            <strong>高风险密钥</strong>
            {isolatedKeys.length === 0 ? (
              <div className="workspace-empty">当前无已隔离密钥。</div>
            ) : (
              <div className="workspace-list">
                {isolatedKeys.map((item) => (
                  <button key={item.key_pair_id} className="workspace-list-item" onClick={() => navigate('/risk')} type="button">
                    <strong>{item.key_name}</strong>
                    <div className="workspace-meta-row">
                      <span>轮转版本 {item.rotation_version}</span>
                      <span>{item.status_reason ?? '无备注'}</span>
                      <span className={`status-pill ${statusTone(item.status)}`}>{item.status}</span>
                    </div>
                  </button>
                ))}
              </div>
            )}
          </article>
        </div>
      </section>

      <section className="panel">
        <div className="workspace-summary-grid">
          <article className="workspace-summary-card">
            <h3>最近签发记录</h3>
            <div className="workspace-list">
              {latestIssues.map((item) => (
                <button key={item.issue_record_id} className="workspace-list-item" onClick={() => navigate('/validation')} type="button">
                  <strong>签发 #{item.issue_record_id}</strong>
                  <div className="workspace-meta-row">
                    <span>{item.customer_code}</span>
                    <span>{item.application_name}</span>
                    <span className={`status-pill ${statusTone(item.status)}`}>{item.status}</span>
                  </div>
                </button>
              ))}
            </div>
          </article>
          <article className="workspace-summary-card">
            <h3>工具与诊断契约</h3>
            <ul>
              <li>当前工具版本：{bestTool ? `${bestTool.tool_name} / ${bestTool.version}` : '尚无工具版本'}</li>
              <li>稳定结果码：{Object.keys(dashboard.validationContract?.code_catalog ?? {}).length} 个</li>
              <li>校验向量：{dashboard.validationVectors?.license_validation_vectors.length ?? 0} 条</li>
            </ul>
          </article>
          <article className="workspace-summary-card">
            <h3>当前推荐动作</h3>
            <ul>
              {overviewInsights.actions.map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ul>
          </article>
        </div>
      </section>

      <section className="panel">
        <div className="enterprise-two-column">
          <div className="enterprise-stack">
            {overviewInsights.risks.map((item) => (
              <article key={item.title} className={`enterprise-note-card tone-${item.tone}`}>
                <strong>{item.title}</strong>
                <p>{item.detail}</p>
              </article>
            ))}
          </div>
          <article className="enterprise-note-card">
            <strong>最近审计留痕</strong>
            <div className="workspace-table-wrap">
              <table className="workspace-table">
                <thead>
                  <tr>
                    <th>时间</th>
                    <th>动作</th>
                    <th>实体</th>
                  </tr>
                </thead>
                <tbody>
                  {dashboard.auditLogs.map((item) => (
                    <tr key={`${item.happened_at_cst}-${item.entity_id}`}>
                      <td>{item.happened_at_cst}</td>
                      <td>{item.action}</td>
                      <td>{item.entity_type} / {item.entity_id}</td>
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
