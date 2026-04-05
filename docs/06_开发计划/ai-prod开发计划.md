# ai-prod 开发计划

## 1. 模块目标

将当前 ai-prod 从基础版 Python 管理/测试实现，收敛为面向客户交付的 **C++ HTTP + C++ Runtime + 插件模式** 的真实工业运行底座，并保留内部测试/验收外壳。

## 2. 工作分解

| 编号 | 工作项 | 状态 |
| --- | --- | --- |
| P1 | 搭建 ai-prod 服务工程骨架 | 已完成 |
| P2 | 实现能力扫描与资源装载策略 | 已完成 |
| P3 | 实现 license 双层校验 | 已完成 |
| P4 | 实现基础版 runtime 与实例池 | 已完成 |
| P5 | 实现统一推理 API 与测试页面 | 已完成 |
| P6 | 实现 reload/rollback | 已完成 |
| P7 | 实现生产镜像与挂载模板 | 已完成 |
| P8 | 基础版压测、联调与验收 | 已完成 |
| P9 | 引入 C++ HTTP 服务主链路 | 已完成 |
| P10 | 引入 C++ Runtime / 插件管理 / 实例池 / drain 机制 | 已完成 |
| P11 | 收敛 License / 热更新 / 回滚与 ai_platform 参考实现 | 已完成 |
| P12 | 保留并重构 Python/React 测试验收外壳 | 已完成 |
| P13 | 面向客户交付的压测、验收与运行规范固化 | 已完成 |
| P14 | 首轮将 infer 主链路收敛为 C++ 直接执行闭环 | 已完成 |
| P15 | 将 reload/rollback、revision/operation 持久化收敛为 C++ 直接执行闭环 | 已完成 |
| P16 | 将真实插件动态加载与执行收敛为 C++ infer 主链路 | 已完成 |
| P17 | 将启动阶段 bootstrap 首次装载收敛为 C++ 直接执行闭环 | 已完成 |
| P18 | 引入 C++ runtime 显式状态机与切换互斥保护 | 已完成 |
| P19 | 补齐请求级跟踪、RAII 租约与 drain 等待收口 | 已完成 |
| P20 | 深化插件生命周期观测并补齐能力级执行指标 | 已完成 |
| P21 | 补齐插件 warmup/health_check 生命周期钩子与观测 | 已完成 |
| P22 | 补齐统一输入 payload codec 与多格式编解码收口 | 已完成 |
| P23 | 补齐基于 revision 的能力快照持久化与真实回滚恢复 | 已完成 |
| P24 | 完成 Python 验收外壳内化与 C++ 生产主链路去回退收口 | 已完成 |
| P25 | 补齐统一运行时指标聚合与生产验收基线输出 | 已完成 |
| P26 | 补齐 capability 级批处理元数据透传与繁忙拒绝观测 | 已完成 |
| P27 | 补齐基础请求排队、等待超时与调度观测 | 已完成 |
| P28 | 补齐 capability 级排队策略元数据透传与调度配置收口 | 已完成 |
| P29 | 补齐 GPU 插件装载/生命周期失败时的 CPU 自动回退编排与观测 | 已完成 |
| P30 | 补齐请求全生命周期耗时观测与能力级时延聚合 | 已完成 |
| P31 | 补齐请求级 SLA 截止时间控制与 deadline 违约观测 | 已完成 |
| P32 | 补齐结构化审计日志与请求关联字段统一收口 | 已完成 |
| P33 | 补齐 capability 级短时批次聚合与批次调度观测 | 已完成 |
| P34 | 补齐 capability 级运行时编排元数据与全局资源编排诊断 | 已完成 |

## 3. 进度维护要求

每次开发前后更新状态、风险、阶段小结。

## 4. 当前进度更新

### 4.1 已完成

1. 已完成 ai-prod 基础版 FastAPI + SQLite 工程骨架与基础配置。
2. 已完成宿主机挂载优先、镜像基线回退的资源扫描、能力装载与活动版本切换。
3. 已完成标准 license 文件验签、时间窗口/能力范围/版本约束/硬件指纹双层校验与授权状态查询。
4. 已完成基础版 runtime revision、实例池、GPU 优先/CPU 自动回退、统一推理 API、前端测试页、reload/rollback 与运行日志审计。
5. 已完成基础版 Docker、测试与构建校验。

### 4.2 已完成

1. 当前已完成 P9-P34 全量收口，`apps/ai-prod/cpp/` 已成为面向客户交付的 C++ 生产主链路，实现了真实插件执行、bootstrap、reload/rollback、revision/operation 持久化、显式状态机、请求跟踪、批处理、deadline、审计日志与运行时编排诊断。
2. 当前已完成与 ai-license-mgr 的 License / 热更新 / 回滚语义统一：版本约束、`license_tool` 协同、密钥轮转后的运行态校验以及现场交付链路所需的能力范围与版本控制均已在代码与测试层完成对齐。
3. 当前已完成内部验收外壳与交付材料收口：Python backend 仅保留 `/internal/*` 诊断能力，React 前端已补齐能力目录、在线控制台、revision/operation 视图、跨模块导航、共享 workspace 配置与总体联调复审展示。
4. 经再次对照代码、测试、模块设计文档与总体计划核验，当前模块开发计划项已全部完成，后续若继续增强，将转入新一轮增量规划而非当前模块遗留项。

### 4.3 未完成

1. ai-prod 模块开发计划项已全部完成；当前代码、模块设计文档与模块开发计划已完成对齐，后续若继续增强，将转入新一轮增量规划而非当前模块遗留项。

### 4.4 阶段小结

ai-prod 当前已完成 P9-P34：在已完成 P12/P13/P14/P15/P16/P17/P18/P19/P20/P21/P22/P23/P24/P25/P26/P27/P28/P29/P30/P31/P32/P33 的基础上，生产镜像/compose 已切换为“C++ HTTP 对外主入口 + Python backend 仅容器内壳层”的实际交付主链路，且不仅 infer 热路径与启动阶段 bootstrap 已由 C++ 直接完成，请求侧的 runtime 管理也已新增显式状态机、请求级 in-flight 跟踪、RAII 请求租约、能力级执行指标聚合、插件 `warmup` / `health_check` 生命周期钩子、统一输入 `payload codec`、切换互斥保护与 `/api/v1/admin/metrics` 统一运行时指标接口；在已补齐 capability 级 `max_batch_size` / `instance_count` 元数据透传、基础请求排队等待、排队上限、等待超时与排队耗时统计、capability 级 `queue_wait_timeout_ms` / `max_pending_request_count` 调度策略元数据收口、GPU 插件动态库装载/生命周期失败场景下的 CPU 自动回退编排、`lifecycle_elapsed_ms` 端到端时延观测、请求级 `prefer_deadline_ms` SLA 截止时间控制、结构化审计日志与请求关联字段统一收口，以及 capability 级短时批次调度之后，本轮进一步补齐 capability 级运行时编排元数据透传与 `ResourceOrchestrator` 全局资源编排诊断，统一输出 `scheduling_mode`、`backpressure_level`、`recommended_pool_size`、`recommended_max_batch_size` 等 capability 级编排建议，并形成 `/api/v1/admin/catalog` 与 `/api/v1/admin/metrics` 的模块级编排诊断面；同时结合总体计划 R7，对内部 React 验收外壳补齐了标签页式能力目录、在线控制台、revision/operation 视图，以及第二轮跨模块联调导航入口、共享 R7 workspace 配置、公共样式与总体联调复审展示。至此 ai-prod 当前模块设计与开发计划已全部实现完成，模块整体进入已完成状态。
