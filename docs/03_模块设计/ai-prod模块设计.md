# ai-prod 模块设计

## 1. 模块目标

建设面向客户交付的真实工业运行底座，采用 **C++ HTTP 服务 + C++ Runtime + Capability 插件模式** 提供高并发 REST 推理服务、License 校验、热更新与回滚能力；同时提供面向内部测试和验收的 Web/UI 交互外壳。

## 2. 模块职责

1. 对外提供高并发 REST API 服务
2. 动态加载能力插件与模型包
3. 执行启动时与推理时双层 license 校验
4. 提供健康检查、能力查询、reload/rollback 管理
5. 提供面向内部测试和验收的 Web/UI 测试外壳

## 3. 逻辑组件

1. C++ HTTP 服务层
2. C++ Runtime 层
3. Capability 插件层
4. 模型包管理层
5. License 校验层
6. 更新与回滚控制器
7. Python/React 测试与验收外壳（内部可选）

## 4. 核心流程

1. 启动时扫描宿主机挂载目录与镜像内置目录
2. 按“挂载优先、镜像回退”策略装载资源
3. 校验 license、plugins registry 与模型 manifest
4. 创建能力实例池并注册能力路由
5. 对外提供高并发推理服务
6. 管理端触发 reload 或 rollback
7. 内部测试页面通过外壳调用生产主服务完成人工验收

## 5. API 设计

1. `/api/v1/health`
2. `/api/v1/capabilities`
3. `/api/v1/license/status`
4. `/api/v1/infer/{capability_name}`
5. `/api/v1/admin/reload`
6. `/api/v1/admin/rollback`
7. `/api/v1/admin/catalog`
8. `/api/v1/admin/metrics`

## 6. 资源管理

1. 模型版本化目录
2. 插件版本化目录
3. 活动版本原子切换
4. 实例池化管理 GPU/CPU 资源
5. 日志与审计目录管理
6. capability 级批处理元数据与实例规模元数据管理
7. 基础请求排队、等待超时与调度观测
8. capability 级排队策略元数据与调度配置管理
9. GPU 插件装载/生命周期失败时的 CPU 自动回退编排与观测
10. 请求全生命周期耗时观测与能力级时延聚合
11. 请求级 SLA 截止时间控制与 deadline 违约观测
12. 结构化审计日志与请求关联字段统一收口
13. capability 级短时批次聚合、批次等待窗口与批次观测管理
14. capability 级运行时编排元数据与全局资源编排诊断管理

## 7. 非功能要求

1. 并发安全
2. GPU 优先、CPU 自动回退
3. 输入格式统一抽象，支持图片、视频、PDF 等
4. 提供结构化日志和审计日志
5. 提供统一运行时指标观测与交付验收基线输出
6. 提供 capability 级 `max_batch_size` / busy reject 等编排观测
7. 在高并发下支持基础请求排队等待与等待超时控制
8. 支持 capability 级排队等待策略配置透传与运行态可观测
9. 支持 GPU 优先、GPU 生命周期失败时自动回退 CPU，并保留回退原因与计数观测
10. 支持请求全生命周期耗时观测，并对 queue / infer / total latency 做统一留痕
11. 支持请求级 SLA 截止时间控制，并暴露 deadline 违约统计
12. 支持结构化审计日志输出，并在关键链路统一保留 request/correlation 字段
13. 支持 capability 级短时批次聚合与批次等待窗口配置透传，并暴露批次形成/超时释放统计
14. 支持 capability 级运行时编排元数据透传，并对多 capability 负载、排队、批次、SLA 风险输出统一编排诊断
15. 支持 x86 与 arm
16. Python 测试外壳不能成为客户生产调用主链路

## 8. 设计决策

1. 生产主服务采用 C++ HTTP 服务。
2. Runtime 采用 C++ 插件化内核，并参考 `ai_platform` 的 Runtime 实现路线。
3. 推理核心保持插件化与标准 C ABI。
4. 生产镜像内置基线资源，同时支持宿主机热更新。
5. Python FastAPI + React 只作为内部测试与验收外壳。

## 9. 整改设计与跟踪

### 9.1 当前整改重点

1. 强化 runtime 对模型包 manifest、插件 manifest、builder 交付物的强校验与强消费。
2. 已完成授权校验稳定诊断字段收敛：Python / C++ runtime 统一输出 `result / code / stage / details`，并与 `license_tool` / SDK 保持一致语义。
3. 为新增能力建立 capability 级接入检查清单，覆盖 ABI、manifest、license、样本输入与运行时装载。

### 9.2 与其他模块的关键契约

1. 必须消费 ai-builder 输出的真实插件产物与交付 manifest，而不是模板化占位产物。
2. 必须消费 ai-train 输出的稳定模型包字段，包括预处理、阈值、标签、版本与交付元数据。
3. 必须与 ai-license-mgr / ai-sdk 共享统一授权规则、统一失败原因与统一诊断字段。

### 9.3 对应整改编号

1. RP-01
2. RP-02
3. RP-03
