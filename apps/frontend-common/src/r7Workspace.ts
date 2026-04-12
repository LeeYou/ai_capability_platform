export type R7ModuleId = 'ai-train' | 'ai-test' | 'ai-license-mgr' | 'ai-builder' | 'ai-prod'

type EnvLike = Record<string, string | undefined>

type ModuleDefinition = {
  id: R7ModuleId
  title: string
  shortTitle: string
  envKey: string
  defaultUrl: string
  summary: string
  stageLabel: string
  nextModuleId?: R7ModuleId
}

export type R7ModuleLink = {
  id: R7ModuleId
  title: string
  shortTitle: string
  url: string
  summary: string
  stageLabel: string
  isCurrent: boolean
}

export type R7ReviewItem = {
  title: string
  status: string
  detail: string
}

export type WorkflowStep = {
  order: number
  label: string
  url: string
  summary: string
  moduleId: R7ModuleId
  isCurrent: boolean
}

const moduleDefinitions: ModuleDefinition[] = [
  {
    id: 'ai-train',
    title: 'ai-train 研发训练台',
    shortTitle: '训练台',
    envKey: 'VITE_AI_TRAIN_URL',
    defaultUrl: 'http://127.0.0.1:26000',
    summary: '数据集、标注、训练执行、模型资产',
    stageLabel: '标注 / 训练',
    nextModuleId: 'ai-test',
  },
  {
    id: 'ai-test',
    title: 'ai-test 测试评估台',
    shortTitle: '测试台',
    envKey: 'VITE_AI_TEST_URL',
    defaultUrl: 'http://127.0.0.1:26001',
    summary: '单测、批测、验收、报告与证据链',
    stageLabel: '测试 / 验收',
    nextModuleId: 'ai-license-mgr',
  },
  {
    id: 'ai-license-mgr',
    title: 'ai-license-mgr 授权签发台',
    shortTitle: '授权台',
    envKey: 'VITE_AI_LICENSE_MGR_URL',
    defaultUrl: 'http://127.0.0.1:26002',
    summary: '客户、密钥、策略、签发、校验与 tool release',
    stageLabel: '授权 / 商业化',
    nextModuleId: 'ai-builder',
  },
  {
    id: 'ai-builder',
    title: 'ai-builder 交付构建台',
    shortTitle: '构建台',
    envKey: 'VITE_AI_BUILDER_URL',
    defaultUrl: 'http://127.0.0.1:26003',
    summary: '推理库构建、delivery_package、SDK 与产物校验',
    stageLabel: '推理 / 构建',
    nextModuleId: 'ai-prod',
  },
  {
    id: 'ai-prod',
    title: 'ai-prod 运行控制台',
    shortTitle: '运行台',
    envKey: 'VITE_AI_PROD_URL',
    defaultUrl: 'http://127.0.0.1:26004',
    summary: '在线验证、版本控制、监控诊断与运行验收',
    stageLabel: '生产 / 验收',
  },
] as const

export const integrationReviewItems = [
  '统一核对五个模块入口是否可访问，并确认关键工作台能进入核心页面。',
  '统一核对模型、授权、构建、运行、验收链路的字段命名与状态表达。',
  '统一核对交付物、验收报告与运行诊断信息在跨模块联调中的跳转与留痕。',
] as const

export const integrationReviewSummary: R7ReviewItem[] = [
  {
    title: '统一工作台壳层',
    status: '进行中',
    detail: 'R15 正在推进统一门户感、统一导航和统一状态表达，减少各模块页面割裂感。',
  },
  {
    title: '跨模块对象跳转',
    status: '进行中',
    detail: '训练模型、测试结论、授权记录、构建产物与运行版本正在收口为连续对象链路。',
  },
  {
    title: '企业级体验收口',
    status: '进行中',
    detail: '重点围绕工作台布局、风险操作确认、日志与诊断可行动性持续改造。',
  },
]

function resolveModuleLink(env: EnvLike, definition: ModuleDefinition, currentModuleId: R7ModuleId): R7ModuleLink {
  return {
    id: definition.id,
    title: definition.title,
    shortTitle: definition.shortTitle,
    url: env[definition.envKey] ?? definition.defaultUrl,
    summary: definition.summary,
    stageLabel: definition.stageLabel,
    isCurrent: definition.id === currentModuleId,
  }
}

export function buildR7Workspace(env: EnvLike, currentModuleId: R7ModuleId): {
  currentModule: ModuleDefinition
  moduleLinks: R7ModuleLink[]
  reviewItems: readonly string[]
  reviewSummary: R7ReviewItem[]
  workflowSteps: WorkflowStep[]
  nextModule: R7ModuleLink | null
} {
  const currentModule =
    moduleDefinitions.find((item) => item.id === currentModuleId) ?? moduleDefinitions[0]

  const moduleLinks = moduleDefinitions.map((item) => resolveModuleLink(env, item, currentModuleId))
  const nextModule =
    currentModule.nextModuleId == null
      ? null
      : moduleLinks.find((item) => item.id === currentModule.nextModuleId) ?? null

  return {
    currentModule,
    moduleLinks,
    reviewItems: integrationReviewItems,
    reviewSummary: integrationReviewSummary,
    workflowSteps: moduleLinks.map((item, index) => ({
      order: index + 1,
      label: item.stageLabel,
      url: item.url,
      summary: item.summary,
      moduleId: item.id,
      isCurrent: item.id === currentModuleId,
    })),
    nextModule,
  }
}
