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
| P9 | 引入 C++ HTTP 服务主链路 | 进行中 |
| P10 | 引入 C++ Runtime / 插件管理 / 实例池 / drain 机制 | 已完成 |
| P11 | 收敛 License / 热更新 / 回滚与 ai_platform 参考实现 | 已完成 |
| P12 | 保留并重构 Python/React 测试验收外壳 | 未开始 |
| P13 | 面向客户交付的压测、验收与运行规范固化 | 未开始 |

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

### 4.3 未完成

1. C++ HTTP 主服务尚未完全替换当前仓库的 ai-prod 主链路，当前虽已完成 P10 范围内的 catalog / pool / drain / reload 编排，但实际推理执行仍主要由 Python runtime 承担，P9 仍需继续收口。
2. Python 测试页尚未转型为仅服务内部人工验收的交互外壳。
3. 面向客户交付的性能、稳定性、更新回滚规范尚未完全固化。

### 4.4 阶段小结

ai-prod 当前已完成 P11：在保持现有 Python runtime 可用的前提下，C++ 侧已补齐标准 license 文件直读、状态查询、能力 quick check、手动/自动 license reload，以及 infer 与管理切换接口上的 license 前置校验；同时 Python runtime 的 bootstrap / infer / reload / rollback 路径也已补齐按能力范围与版本约束的二次 license 校验，并为状态查询、推理拒绝、reload/rollback 拒绝补齐审计日志。当前已完成本地编译、单测、后端回归与端到端 smoke 验证，后续将转入 P9 主链路收口与 P12 测试验收外壳改造。
