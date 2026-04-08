export type R7ModuleId = 'ai-train' | 'ai-test' | 'ai-license-mgr' | 'ai-builder' | 'ai-prod'

type EnvLike = Record<string, string | undefined>

type ModuleDefinition = {
  id: R7ModuleId
  title: string
  envKey: string
  defaultUrl: string
  summary: string
}

export type R7ModuleLink = {
  id: R7ModuleId
  title: string
  url: string
  summary: string
  isCurrent: boolean
}

export type R7ReviewItem = {
  title: string
  status: string
  detail: string
}

const moduleDefinitions: ModuleDefinition[] = [
  {
    id: 'ai-train',
    title: 'ai-train',
    envKey: 'VITE_AI_TRAIN_URL',
    defaultUrl: 'http://127.0.0.1:26000',
    summary: '标注协作、训练回显、模型 manifest',
  },
  {
    id: 'ai-test',
    title: 'ai-test',
    envKey: 'VITE_AI_TEST_URL',
    defaultUrl: 'http://127.0.0.1:26001',
    summary: '测试任务、验收基线、双视角报告',
  },
  {
    id: 'ai-license-mgr',
    title: 'ai-license-mgr',
    envKey: 'VITE_AI_LICENSE_MGR_URL',
    defaultUrl: 'http://127.0.0.1:26002',
    summary: '密钥轮转、策略签发、license_tool',
  },
  {
    id: 'ai-builder',
    title: 'ai-builder',
    envKey: 'VITE_AI_BUILDER_URL',
    defaultUrl: 'http://127.0.0.1:26003',
    summary: '构建任务、delivery_package、归档下载',
  },
  {
    id: 'ai-prod',
    title: 'ai-prod',
    envKey: 'VITE_AI_PROD_URL',
    defaultUrl: 'http://127.0.0.1:26004',
    summary: '能力目录、在线控制台、revision 诊断',
  },
] as const

export const integrationReviewItems = [
  '统一核对五个模块入口是否可访问，并确认关键工作台能进入核心页面。',
  '统一核对模型、授权、构建、运行、验收链路的字段命名与状态表达。',
  '统一核对交付物、验收报告与运行诊断信息在跨模块联调中的跳转与留痕。',
] as const

export const integrationReviewSummary: R7ReviewItem[] = [
  {
    title: '入口联通性',
    status: '已完成',
    detail: '五个业务模块均已具备统一联调入口、当前模块标识与核心工作台落点。',
  },
  {
    title: '导航配置化',
    status: '已完成',
    detail: '跨模块导航、联调清单与复审结论已抽离为共享配置，前端统一消费。',
  },
  {
    title: '总体联调复审',
    status: '已完成',
    detail: '已形成统一复审结论展示，覆盖训练、测试、授权、构建、运行全链路。',
  },
]

export function buildR7Workspace(env: EnvLike, currentModuleId: R7ModuleId): {
  currentModule: ModuleDefinition
  moduleLinks: R7ModuleLink[]
  reviewItems: readonly string[]
  reviewSummary: R7ReviewItem[]
} {
  const currentModule =
    moduleDefinitions.find((item) => item.id === currentModuleId) ?? moduleDefinitions[0]

  return {
    currentModule,
    moduleLinks: moduleDefinitions.map((item) => ({
      id: item.id,
      title: item.title,
      url: env[item.envKey] ?? item.defaultUrl,
      summary: item.summary,
      isCurrent: item.id === currentModuleId,
    })),
    reviewItems: integrationReviewItems,
    reviewSummary: integrationReviewSummary,
  }
}
