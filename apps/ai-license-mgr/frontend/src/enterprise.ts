import type {
  AuditLogItem,
  CustomerItem,
  DashboardState,
  KeyPairItem,
  LicenseIssueDetail,
  LicenseIssueItem,
  LicensePolicyItem,
  LicenseToolReleaseItem,
  ValidateLicenseResult,
  ValidationContract,
  ValidationVectors,
} from './types'

export type EnterpriseTone = 'good' | 'warn' | 'danger' | 'neutral'

export type EnterpriseChecklistItem = {
  label: string
  detail: string
  done: boolean
}

export type EnterpriseStageCard = {
  title: string
  score: number
  count: number
  detail: string
  tone: EnterpriseTone
}

export type EnterpriseRiskItem = {
  title: string
  detail: string
  tone: EnterpriseTone
}

export type EnterpriseComparisonRow = {
  label: string
  current: string
  baseline: string
  same: boolean
}

export type CustomerPortfolioItem = {
  customer: CustomerItem
  policyCount: number
  issueCount: number
  activeIssueCount: number
  applications: string[]
}

/** Returns the first valid timestamp from the fallback list, or Number.NEGATIVE_INFINITY when none are valid. */
function getRecordTimestamp(...values: Array<string | null | undefined>): number {
  for (const value of values) {
    if (!value) continue
    const timestamp = new Date(value).getTime()
    if (!Number.isNaN(timestamp)) return timestamp
  }
  return Number.NEGATIVE_INFINITY
}

export function clampScore(value: number): number {
  return Math.max(0, Math.min(100, Math.round(value)))
}

export function scoreTone(score: number): EnterpriseTone {
  if (score >= 85) return 'good'
  if (score >= 60) return 'warn'
  return 'danger'
}

export function daysUntil(value?: string | null): number | null {
  if (!value) return null
  const timestamp = new Date(value).getTime()
  if (Number.isNaN(timestamp)) return null
  return Math.floor((timestamp - Date.now()) / 1000 / 60 / 60 / 24)
}

export function stringifyComparableValue(value: unknown): string {
  if (typeof value === 'string') return value
  if (value == null) return '-'
  return JSON.stringify(value, null, 2)
}

export function buildOverviewInsights(dashboard: DashboardState): {
  overallScore: number
  stageCards: EnterpriseStageCard[]
  risks: EnterpriseRiskItem[]
  actions: string[]
  expiringPolicies: LicensePolicyItem[]
} {
  const activeKeys = dashboard.keyPairs.filter((item) => item.status === 'active').length
  const activeIssues = dashboard.issues.filter((item) => item.status === 'issued' || item.status === 'valid').length
  const readyTools = dashboard.toolReleases.filter((item) => item.status === 'ready').length
  const expiringPolicies = dashboard.policies
    .filter((item) => {
      const remaining = daysUntil(item.expire_at_cst)
      return remaining != null && remaining <= 30
    })
    .sort((left, right) => getRecordTimestamp(left.expire_at_cst) - getRecordTimestamp(right.expire_at_cst))
    .slice(0, 5)

  const customerScore = dashboard.customers.length === 0 ? 0 : 100
  const keyScore = dashboard.keyPairs.length === 0 ? 0 : (activeKeys / dashboard.keyPairs.length) * 100
  const issueScore = dashboard.issues.length === 0 ? 0 : (activeIssues / dashboard.issues.length) * 100
  const toolScore = dashboard.toolReleases.length === 0 ? 0 : (readyTools / dashboard.toolReleases.length) * 100
  const overallScore = clampScore(customerScore * 0.2 + keyScore * 0.3 + issueScore * 0.3 + toolScore * 0.2)

  return {
    overallScore,
    stageCards: [
      {
        title: '客户就绪',
        score: clampScore(customerScore),
        count: dashboard.customers.length,
        detail: `${dashboard.customers.length} 个客户对象已纳入授权台`,
        tone: scoreTone(customerScore),
      },
      {
        title: '密钥健康',
        score: clampScore(keyScore),
        count: activeKeys,
        detail: `${activeKeys}/${dashboard.keyPairs.length || 0} 个密钥可签发`,
        tone: scoreTone(keyScore),
      },
      {
        title: '签发闭环',
        score: clampScore(issueScore),
        count: activeIssues,
        detail: `${activeIssues}/${dashboard.issues.length || 0} 条记录有效`,
        tone: scoreTone(issueScore),
      },
      {
        title: '工具契约',
        score: clampScore(toolScore),
        count: readyTools,
        detail: `${readyTools}/${dashboard.toolReleases.length || 0} 个工具版本 ready`,
        tone: scoreTone(toolScore),
      },
    ],
    risks: [
      {
        title: '即将到期',
        detail: expiringPolicies.length > 0 ? `${expiringPolicies.length} 条策略 30 天内到期` : '当前无 30 天内到期策略',
        tone: expiringPolicies.length > 0 ? 'warn' : 'good',
      },
      {
        title: '隔离密钥',
        detail: dashboard.keyPairs.some((item) => item.status === 'isolated') ? '存在已隔离密钥，需要核对影响面' : '当前无已隔离密钥',
        tone: dashboard.keyPairs.some((item) => item.status === 'isolated') ? 'danger' : 'good',
      },
      {
        title: '校验契约',
        detail: dashboard.validationContract == null ? '尚未加载诊断契约' : `稳定结果码 ${Object.keys(dashboard.validationContract.code_catalog).length} 个`,
        tone: dashboard.validationContract == null ? 'warn' : 'good',
      },
    ],
    actions: [
      '先完成客户、密钥、策略、签发的连续闭环，再进入校验与导出。',
      '高风险密钥操作前先核对关联策略、签发记录和审计留痕。',
      '签发通过后将 license.bin / pubkey / tool bundle 明确推进到 ai-builder。',
    ],
    expiringPolicies,
  }
}

export function buildIssuanceChecklist(params: {
  customers: CustomerItem[]
  keyPairs: KeyPairItem[]
  policies: LicensePolicyItem[]
  selectedPolicy: LicensePolicyItem | null
  issues: LicenseIssueItem[]
}): EnterpriseChecklistItem[] {
  const { customers, keyPairs, policies, selectedPolicy, issues } = params
  return [
    {
      label: '客户已准备',
      detail: `${customers.length} 个客户可用`,
      done: customers.length > 0,
    },
    {
      label: '密钥可签发',
      detail: `${keyPairs.filter((item) => item.status === 'active').length} 个 active 密钥`,
      done: keyPairs.some((item) => item.status === 'active'),
    },
    {
      label: '策略已选定',
      detail: selectedPolicy ? `${selectedPolicy.policy_name} / ${selectedPolicy.customer_code}` : '尚未选择策略',
      done: selectedPolicy != null,
    },
    {
      label: '已有签发记录',
      detail: `${issues.length} 条签发记录`,
      done: issues.length > 0,
    },
    {
      label: '策略池已建立',
      detail: `${policies.length} 条策略`,
      done: policies.length > 0,
    },
  ]
}

export function buildRiskChecklist(selectedKeyPair: KeyPairItem | null, relatedPolicies: LicensePolicyItem[], relatedIssues: LicenseIssueItem[]): EnterpriseChecklistItem[] {
  if (!selectedKeyPair) return []
  return [
    {
      label: '已选中风险对象',
      detail: `${selectedKeyPair.key_name} / ${selectedKeyPair.status}`,
      done: true,
    },
    {
      label: '影响策略已统计',
      detail: `${relatedPolicies.length} 条关联策略`,
      done: true,
    },
    {
      label: '影响签发已统计',
      detail: `${relatedIssues.length} 条关联签发`,
      done: true,
    },
    {
      label: '已具备风险结论',
      detail: selectedKeyPair.status === 'isolated' ? '当前已处于隔离态' : '当前仍处于可签发态',
      done: selectedKeyPair.status === 'isolated',
    },
  ]
}

export function buildValidationChecklist(params: {
  issueDetail: LicenseIssueDetail | null
  result: ValidateLicenseResult | null
  contract: ValidationContract | null
  vectors: ValidationVectors | null
  tools: LicenseToolReleaseItem[]
}): EnterpriseChecklistItem[] {
  return [
    {
      label: '已选定签发记录',
      detail: params.issueDetail ? `#${params.issueDetail.issue_record_id} / ${params.issueDetail.customer_code}` : '尚未选择签发记录',
      done: params.issueDetail != null,
    },
    {
      label: '稳定校验结果可用',
      detail: params.result ? `${params.result.code} / ${params.result.stage}` : '尚未执行校验',
      done: params.result != null,
    },
    {
      label: '诊断契约已加载',
      detail: params.contract ? `${Object.keys(params.contract.code_catalog).length} 个结果码` : '尚未加载 contract',
      done: params.contract != null,
    },
    {
      label: '测试向量已加载',
      detail: params.vectors ? `${params.vectors.license_validation_vectors.length} 条 license 向量` : '尚未加载 vectors',
      done: params.vectors != null,
    },
    {
      label: '工具版本已准备',
      detail: `${params.tools.filter((item) => item.status === 'ready').length} 个 ready 工具`,
      done: params.tools.some((item) => item.status === 'ready'),
    },
  ]
}

export function buildCustomerPortfolio(customers: CustomerItem[], policies: LicensePolicyItem[], issues: LicenseIssueItem[]): CustomerPortfolioItem[] {
  return customers.map((customer) => {
    const customerPolicies = policies.filter((item) => item.customer_id === customer.customer_id)
    const customerIssues = issues.filter((item) => item.customer_id === customer.customer_id)
    return {
      customer,
      policyCount: customerPolicies.length,
      issueCount: customerIssues.length,
      activeIssueCount: customerIssues.filter((item) => item.status === 'issued' || item.status === 'valid').length,
      applications: Array.from(new Set(customerIssues.map((item) => item.application_name))).slice(0, 4),
    }
  })
}

export function buildPolicyRiskItems(policy: LicensePolicyItem, issues: LicenseIssueItem[], keyPairs: KeyPairItem[]): EnterpriseRiskItem[] {
  const remainingDays = daysUntil(policy.expire_at_cst)
  const issueCount = issues.filter((item) => item.policy_id === policy.policy_id).length
  const keyPair = keyPairs.find((item) => item.key_pair_id === policy.key_pair_id)
  return [
    {
      title: '到期窗口',
      detail: remainingDays == null ? '无法计算' : `${remainingDays} 天`,
      tone: remainingDays != null && remainingDays <= 30 ? 'warn' : 'good',
    },
    {
      title: '关联签发',
      detail: `${issueCount} 条签发记录`,
      tone: issueCount > 0 ? 'good' : 'warn',
    },
    {
      title: '密钥状态',
      detail: keyPair ? `${keyPair.key_name} / ${keyPair.status}` : '密钥不存在',
      tone: keyPair == null ? 'danger' : keyPair.status === 'isolated' ? 'danger' : 'good',
    },
  ]
}

export function buildAuditRiskItems(auditLogs: AuditLogItem[]): EnterpriseRiskItem[] {
  const rotateCount = auditLogs.filter((item) => item.action.includes('rotate')).length
  const isolateCount = auditLogs.filter((item) => item.action.includes('isolate')).length
  const issueCount = auditLogs.filter((item) => item.action.includes('issue')).length
  return [
    {
      title: '轮转留痕',
      detail: `${rotateCount} 条`,
      tone: rotateCount > 0 ? 'warn' : 'neutral',
    },
    {
      title: '隔离留痕',
      detail: `${isolateCount} 条`,
      tone: isolateCount > 0 ? 'danger' : 'good',
    },
    {
      title: '签发留痕',
      detail: `${issueCount} 条`,
      tone: issueCount > 0 ? 'good' : 'neutral',
    },
  ]
}

export function buildIssueComparison(issue: LicenseIssueItem, policy: LicensePolicyItem | null): EnterpriseComparisonRow[] {
  return [
    {
      label: '客户',
      current: issue.customer_code,
      baseline: policy?.customer_code ?? '-',
      same: issue.customer_code === policy?.customer_code,
    },
    {
      label: '应用名',
      current: issue.application_name,
      baseline: policy?.application_name ?? '-',
      same: issue.application_name === policy?.application_name,
    },
    {
      label: '操作系统',
      current: issue.operating_system,
      baseline: policy?.operating_system ?? '-',
      same: issue.operating_system === policy?.operating_system,
    },
    {
      label: '系统架构',
      current: issue.system_architecture ?? '-',
      baseline: policy?.system_architecture ?? '-',
      same: issue.system_architecture === policy?.system_architecture,
    },
    {
      label: '能力范围',
      current: issue.capability_scope.join(', '),
      baseline: policy?.capability_scope.join(', ') ?? '-',
      same: JSON.stringify(issue.capability_scope) === JSON.stringify(policy?.capability_scope ?? []),
    },
  ]
}

export function pickBestToolRelease(items: LicenseToolReleaseItem[]): LicenseToolReleaseItem | null {
  if (items.length === 0) return null
  return [...items].sort((left, right) => {
    const leftReady = left.status === 'ready' ? 1 : 0
    const rightReady = right.status === 'ready' ? 1 : 0
    if (leftReady !== rightReady) return rightReady - leftReady
    return right.release_id - left.release_id
  })[0]
}

