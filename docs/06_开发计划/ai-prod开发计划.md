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
9. 当前已完成 P11：在 C++ 侧新增标准 license 文件直读、quick check、手动/自动 reload，并让 infer 与管理切换接口接入 license 校验；同时在 Python runtime 的 bootstrap / infer / reload / rollback 路径补齐按能力/版本维度的二次 license 校验与审计日志。后续已进一步与 ai-license-mgr 对齐版本约束语义，统一支持 `allowed_versions`、`prefix`、`min_version`、`max_version` 与缺失产品版本拒绝语义。
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
20. 当前已完成 P21：C++ 插件执行层已补齐可选 `warmup` / `health_check` 生命周期钩子装载与执行，生命周期状态、时间戳与失败信息会并入 capability 级 `execution_metrics`，并通过 `/api/v1/admin/catalog` 暴露，进一步收敛插件装载后的可观测性与自检能力。
21. 当前已完成 P22：C++ 侧已新增统一输入 `payload codec`，对 `image / video / pdf` 请求补齐 base64 解码与格式校验，并将解码后的统一 payload 直接送入插件执行链路；推理结果与审计日志同时补齐 `input_metadata`，进一步收口多格式输入的 C++ 运行时处理能力。
22. 当前已完成 P23：reload / bootstrap 会把能力级模型目录、插件目录、插件文件、manifest 元数据持久化到 revision 明细；rollback 会优先恢复目标 revision 持久化的具体资源路径与版本，而不是仅按能力名重扫当前目录，Python 内部验收外壳也已对齐相同行为，并补齐“升级到新版本后回滚恢复旧版本”的 C++ / Python 测试覆盖。
23. 当前已完成 P24：Python backend 生命周期不再执行 runtime bootstrap，也不再暴露公开 `/api/v1/*` 生产运行接口，仅保留 `/internal/*` 诊断查询能力；C++ 生产主链路对 health / capabilities / infer 不再回退 Python backend，当 runtime snapshot 不可用时直接返回生产态错误，前端开发代理与页面调用也已显式拆分 C++ runtime API 与 Python internal API。
24. 当前已完成 P25：C++ 生产主链路已新增 `/api/v1/admin/metrics` 统一运行时指标接口，按 endpoint 聚合请求量、成功/失败数、状态码分布与近期延迟分位，同时输出实例池利用率、能力级执行汇总与 uptime；内部验收前端、验收脚本与压测脚本也已对齐接入该指标输出，进一步固化交付阶段的观测与基线留痕。
25. 当前已完成 P26：C++ / Python 资源扫描、revision 明细与 runtime snapshot 已补齐 capability 级 `max_batch_size` / `instance_count` 元数据透传，C++ 插件执行初始化会按能力配置传入真实 `max_batch_size`，实例池繁忙拒绝次数也已纳入 `/api/v1/admin/catalog` 与 `/api/v1/admin/metrics` 观测；内部验收页面与验收脚本同步暴露该类编排元数据，进一步向更完整的 Runtime 编排收口迈进。
26. 当前已完成 P27：C++ 实例池已补齐基础请求排队等待、排队上限、等待超时与排队耗时统计；`/api/v1/infer/{capability_name}` 在实例槽位繁忙时会优先进入短时等待而非直接失败，并将 `queue_wait_ms`、`pending_request_count`、`queued_request_count`、`queue_timeout_count` 等调度观测同步输出到 `/api/v1/admin/catalog`、`/api/v1/admin/metrics`、验收脚本与内部验收页面，进一步收口面向工业运行时的基础调度能力。
27. 当前已完成 P28：C++ / Python 资源扫描、revision 明细、runtime snapshot 与 capability catalog 已补齐 capability 级 `queue_wait_timeout_ms` / `max_pending_request_count` 调度策略元数据透传；`/api/v1/infer/{capability_name}`、`/api/v1/admin/catalog`、`/api/v1/admin/metrics`、内部验收页面与验收脚本现可同步暴露能力级排队策略配置与运行态排队观测，进一步让运行时调度行为具备 capability 级精细化收口能力。
28. 当前已完成 P29：当 capability 配置允许 `gpu/cpu` 双模式时，若 GPU 插件在动态库装载、初始化、预热或 `health_check` 生命周期阶段失败，C++ infer 主链路现会自动回退到 CPU 绑定继续执行，并把 `requested_device` / `executed_device`、`fallback_applied`、`fallback_reason` 以及 capability 级 fallback 计数同步暴露到 infer 返回、catalog、metrics、运行日志与审计日志，进一步补齐 GPU 优先、CPU 自动回退在真实生命周期失败场景下的运行时编排闭环。
29. 当前已完成 P30：C++ infer 主链路现已补齐请求全生命周期耗时观测，在 infer 返回、运行日志与审计日志中统一输出 `lifecycle_elapsed_ms`，并在 capability 级 `execution_metrics` 中新增 `avg/min/max_lifecycle_time_ms` 聚合指标；同时 active request 诊断继续基于请求注册时间输出 `elapsed_ms`，进一步把 queue wait、插件 infer 与端到端请求时延统一收口到同一组运行态观测面。
30. 当前已完成 P31：C++ infer 主链路现已支持请求级 `prefer_deadline_ms` SLA 截止时间参数，会在排队等待阶段与进入插件执行前做 deadline enforcement，并在 infer 返回、catalog active request、metrics、运行日志与审计日志中统一暴露 `deadline_ms` / `sla_status` / deadline 违约计数；同时 runtime metrics 已补齐 endpoint 级 `sla_tracked_requests`、`deadline_exceeded_requests` 及 pool 级 `deadline_exceeded_count`，进一步让运行时对交互型请求的时限约束具备基础收口能力。
31. 当前已完成 P32：C++ 侧已新增独立 `AuditLogger` 组件，替换 `http_server.cpp` 内散落的原始审计日志写入逻辑；infer / bootstrap / reload / rollback / license reload 等关键链路现统一输出结构化审计日志，并补齐 `status`、`request_id`、`correlation_id`、`elapsed_ms`、`error_message` 等标准字段，同时保留原有 Python 审计日志顶层 schema，进一步让运行时诊断、合规留痕与请求关联字段具备统一收口能力。
32. 当前已完成 P33：C++ 侧已新增 capability 级 `RequestBatcher`，在 `max_batch_size` 与 `batch_wait_timeout_ms` 配置生效时，可对同能力请求做短时批次聚合，并由批次 leader 统一借用实例槽位后顺序执行同批请求；runtime resource scanner / revision 明细 / snapshot / catalog / metrics 现已补齐 `batch_wait_timeout_ms` 配置透传，并统一暴露 `formed_batch_count`、`timeout_flush_count`、`full_flush_count`、`batched_request_count`、`pending_batch_request_count` 等批次调度观测，进一步让运行时在不改动插件 ABI 的前提下具备 capability 级短时批次编排能力。

### 4.3 未完成

1. C++ 已完成 infer、启动 bootstrap、显式状态机、请求级跟踪、能力级执行观测、插件 lifecycle hook、统一输入 payload codec、基于 revision 的真实回滚恢复、Python 验收外壳内化、统一运行时指标聚合、capability 级批处理元数据透传与繁忙拒绝观测、基础请求排队等待与调度观测、capability 级排队策略元数据透传、GPU 生命周期失败场景下的 CPU 自动回退编排与观测、请求全生命周期耗时观测与能力级时延聚合、请求级 SLA 截止时间控制与 deadline 违约观测、结构化审计日志与请求关联字段统一收口，以及 capability 级短时批次聚合与批次调度观测收口，但更完整的 Runtime 编排与最终运行时内核收口仍未完成。

### 4.4 阶段小结

ai-prod 当前已完成 P9-P33：在已完成 P12/P13/P14/P15/P16/P17/P18/P19/P20/P21/P22/P23/P24/P25/P26/P27/P28/P29/P30/P31/P32 的基础上，生产镜像/compose 已切换为“C++ HTTP 对外主入口 + Python backend 仅容器内壳层”的实际交付主链路，且不仅 infer 热路径与启动阶段 bootstrap 已由 C++ 直接完成，请求侧的 runtime 管理也已新增显式状态机、请求级 in-flight 跟踪、RAII 请求租约、能力级执行指标聚合、插件 `warmup` / `health_check` 生命周期钩子、统一输入 `payload codec`、切换互斥保护与 `/api/v1/admin/metrics` 统一运行时指标接口；在已补齐 capability 级 `max_batch_size` / `instance_count` 元数据透传、基础请求排队等待、排队上限、等待超时与排队耗时统计、capability 级 `queue_wait_timeout_ms` / `max_pending_request_count` 调度策略元数据收口、GPU 插件动态库装载/生命周期失败场景下的 CPU 自动回退编排、`lifecycle_elapsed_ms` 端到端时延观测、请求级 `prefer_deadline_ms` SLA 截止时间控制，以及结构化审计日志与请求关联字段统一收口之后，本轮进一步补齐 capability 级 `RequestBatcher`、`batch_wait_timeout_ms` 配置透传、短时批次聚合与批次 leader 顺序执行编排，以及 formed/full/timeout batch 统计，让运行时对高频短请求具备更完整的 capability 级短时批次调度能力。当前后续重点继续转向更完整的 Runtime 编排与最终运行时内核收口。
