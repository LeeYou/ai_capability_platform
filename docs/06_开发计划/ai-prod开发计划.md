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

## 3. 进度维护要求

每次开发前后更新状态、风险、阶段小结。

## 4. 当前进度更新

### 4.1 已完成

1. 已完成 ai-prod 基础版 FastAPI + SQLite 工程骨架与基础配置。
2. 已完成宿主机挂载优先、镜像基线回退的资源扫描、能力装载与活动版本切换。
3. 已完成标准 license 文件验签、时间窗口/能力范围/版本约束/硬件指纹双层校验与授权状态查询。
4. 已完成基础版 runtime revision、实例池、GPU 优先/CPU 自动回退、统一推理 API、前端测试页、reload/rollback 与运行日志审计。
5. 已完成基础版 Docker、测试与构建校验。

### 4.2 进行中

1. 当前阶段已开始 P9 第一轮实施，先引入可编译、可启动、可代理现有 Python 接口的 C++ HTTP 服务骨架。
2. 当前阶段已明确 ai-prod 的基础版实现不是最终形态，后续继续收敛到 C++ HTTP + C++ Runtime 的真实运行底座。
3. 本轮已新增 `apps/ai-prod/cpp/` 工程、环境变量配置解析、核心 API 代理路由与基础 CTest 校验。
4. 当前继续推进 P9 第二轮实施，已开始将 C++ 路由层拆分为独立服务类，并补齐设计文档要求的 rollback 管理路由适配。
5. 当前继续推进 P9 第三轮实施，已为 health/capabilities/license 查询接口引入基于 runtime snapshot 的 C++ 直接响应，并保留自动降级转发。
6. 当前已启动 P10 首轮实施，在 C++ 侧新增 capability catalog 与轻量实例池骨架，并提供 `/api/v1/admin/catalog` 诊断接口。
7. 当前继续推进 P10 第二轮实施，已让 infer 路由接入 capability catalog 与轻量实例池借还流程，并补齐未知能力/池繁忙保护。
8. 当前已完成 P10 第三轮实施，在 C++ 侧为 reload/rollback 接入实例池 drain 编排、切换等待与切换后 catalog/pool 刷新。
9. 当前已完成 P11：在 C++ 侧新增标准 license 文件直读、quick check、手动/自动 reload，并让 infer 与管理切换接口接入 license 校验；同时在 Python runtime 的 bootstrap / infer / reload / rollback 路径补齐按能力/版本维度的二次 license 校验与审计日志。
10. 当前已完成 P12：将 Python/React 测试验收外壳的内部查询接口拆分到 `/internal/*`，前端显式标记为内部验收外壳，并让 Vite 开发代理直连 Python 后端；同时移除 C++ 生产主链路对 revision / operation 等内部查询接口的转发暴露。
11. 当前已完成 P13：补齐 ai-prod 面向客户交付的默认环境模板、公共 API 验收脚本、基础并发压测脚本与运行规范文档，并在 Makefile / 运维文档中固化标准入口。
12. 当前已完成 P9 收口：生产镜像与 docker-compose 已切换为“C++ HTTP 对外 26004 + Python backend 仅容器内 26014”的双进程主链路，C++ HTTP 正式成为交付主入口。
13. 当前已完成 P14：在 runtime snapshot 可用时，`/api/v1/infer/{capability_name}` 已由 C++ 直接完成请求解析、license quick check、设备选择、实例池借还、结果生成与基础日志审计，仅在 snapshot 不可用时回退到 Python backend。
14. 当前已完成 P15：`/api/v1/admin/reload` 与 `/api/v1/admin/rollback` 已由 C++ 直接完成资源扫描、revision/operation SQLite 持久化、runtime snapshot 重写与 catalog/pool 刷新，仅保留 Python 作为内部测试验收外壳与兼容壳层。
15. 当前已完成 P16：C++ infer 主链路已接入真实插件动态加载、按实例槽位初始化与执行，runtime snapshot / capability catalog 已补齐 `model_root`、`binary_path` 元数据，默认由 C++ 直接调用插件返回结果，仅在 snapshot 不可用时回退 Python backend。
16. 当前已完成 P17：当 runtime snapshot 缺失或不可用时，C++ 服务在启动阶段已可直接完成资源扫描、license quick check、bootstrap revision/operation SQLite 持久化与 runtime snapshot 初始写入，并在首启后立即刷新 catalog/pool 进入可服务状态。
17. 当前已完成 P18：C++ 侧已新增 runtime 显式状态机，覆盖 `bootstrapping / ready / draining / transitioning / error` 状态流转，并为 reload/rollback 增加切换互斥保护；`/api/v1/admin/catalog` 现可输出运行时状态与错误信息，避免并发管理操作造成状态竞争。
18. 当前已完成 P19：C++ infer 主链路已新增请求级 in-flight 跟踪与 RAII 请求租约，`/api/v1/admin/catalog` 可输出 active request 详情，reload/rollback drain 阶段会等待活动请求清空后再切换，进一步收口请求生命周期与切换安全。
19. 当前已完成 P20：C++ 插件执行层已补齐能力级执行指标聚合与插件信息快照，`/api/v1/admin/catalog` 可输出 capability 级 `execution_metrics` 与 `plugin_info`，用于观测请求量、成功/失败次数、推理耗时及当前插件元数据。

### 4.3 未完成

1. C++ 已完成 infer、启动 bootstrap、显式状态机、请求级跟踪、能力级执行观测与 reload/rollback 管理闭环，但插件生命周期管理深化、以及更完整的运行时版本切换仍未完全替换 Python runtime，真实 C++ Runtime 的最终收口仍未完成。

### 4.4 阶段小结

ai-prod 当前已完成 P9-P20：在已完成 P12/P13/P14/P15/P16/P17/P18/P19 的基础上，生产镜像/compose 已切换为“C++ HTTP 对外主入口 + Python backend 仅容器内壳层”的实际交付主链路，且不仅 infer 热路径与启动阶段 bootstrap 已由 C++ 直接完成，请求侧的 runtime 管理也已新增显式状态机、请求级 in-flight 跟踪、RAII 请求租约、能力级执行指标聚合与切换互斥保护，可稳定覆盖 `bootstrapping / ready / draining / transitioning / error` 状态流转，并通过 `/api/v1/admin/catalog` 暴露运行时状态、错误信息、active request 详情以及 capability 级 `execution_metrics` / `plugin_info`。当前后续重点继续转向插件生命周期深化与最终 C++ Runtime 替换。
