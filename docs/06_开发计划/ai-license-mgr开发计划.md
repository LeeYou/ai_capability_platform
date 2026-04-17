# ai-license-mgr 开发计划

## 1. 模块目标

持续完善客户、密钥、license 管理与签发能力，并统一授权规则、授权工具与运行底座校验逻辑。

## 2. 工作分解

| 编号 | 工作项 | 状态 |
| --- | --- | --- |
| L1 | 搭建 ai-license-mgr 前后端工程骨架 | 已完成 |
| L2 | 实现客户管理 | 已完成 |
| L3 | 实现密钥对管理 | 已完成 |
| L4 | 实现 license 策略与签发 | 已完成 |
| L5 | 实现校验与导出 | 已完成 |
| L6 | 实现授权镜像 | 已完成 |
| L7 | 首期联调与验收 | 已完成 |
| L8 | 与 ai-prod 运行态 License 规则收敛 | 已完成 |
| L9 | license_tool 与交付材料收敛 | 已完成 |
| L10 | 私钥管理、轮转与隔离策略增强 | 已完成 |
| L11 | 授权核心金标准测试向量与一致性基线 | 已完成 |
| L12 | 稳定授权失败原因 / 细节字段收敛 | 已完成 |
| L13 | Python / C++ / SDK / license_tool 跨模块回归链路 | 已完成 |
| L14 | 授权平台字段（操作系统/最低系统版本/架构/应用名）设计与签发工具收口 | 已完成 |
| L15 | 平台准入诊断契约与 ai-prod / ai-sdk 同步 | 已完成 |
| L16 | 客户 / 密钥 / 策略 / 签发连续工作台重构 | 已完成 |
| L17 | 高风险操作（轮转/隔离/失效）影响面与确认体验重构 | 已完成 |
| L18 | 校验结果、diagnostics / vectors / tool release 工作台重构 | 已完成 |
| L19 | 授权完成后的构建联动与首页风险概览收口 | 已完成 |
| L20 | 授权核心 / 文件导出 / 工具发布服务拆分 | 已完成 |
| L21 | shared contract validator 与公共底座接入 | 已完成 |

## 3. 进度维护要求

每次开发前后更新状态、风险、阶段小结，并同步对照 `docs/05_评审/代码逻辑自洽整改清单.md` 中 RL-01 ~ RL-04。

## 4. 当前进度更新

### 4.1 已完成

1. 已完成 ai-license-mgr 基础版客户、密钥、授权策略、签发、校验、导出、审计日志与前端管理台。
2. 已完成基础版 Docker、测试与构建校验。

### 4.2 进行中

1. 当前已完成 L16-L19：ai-license-mgr 前端已升级为“首页概览 / 连续签发 / 风险操作 / 校验与工具”四段式授权工作台。
2. 当前已完成 L16：客户、密钥、策略与签发已被收口为连续向导化工作台，减少了跨页跳转与人工记忆成本。
3. 当前已完成 L17：高风险操作区已补齐轮转 / 隔离的影响面统计、状态展示与显式操作入口。
4. 当前已完成 L18：校验结果页已突出稳定 `result / code / stage / details`，并补齐 diagnostics / vectors / tool release 导出动作。
5. 当前已完成 L19：首页已补齐风险概览、最近签发、审计留痕与“推进 ai-builder”下游联动。
6. 当前已完成 L20：已将 customer/key_pair/policy/issue/tool_release 等职责从 `license_service.py` 拆分为独立子服务；`license_service.py` 收敛为薄编排层并保持 API 签名不变。
7. 当前已完成 L21：shared contract validator 已新增 `validate_license_tool_release_bundle()`，并在 `license_tool` source bundle 生成过程中执行校验，确保交付物契约稳定。

### 4.3 未完成

1. 下一阶段将继续扩展 shared contract validator 覆盖范围：纳入更多授权交付契约（如 license payload/diagnostics、导出清单等）。

### 4.4 阶段小结

ai-license-mgr 已完成 L16-L19，当前模块计划已校准到 R16：本轮已完成 L20/L21，围绕“授权核心 / 文件导出 / 工具发布 / 契约校验”形成了更清晰的服务分层，`license_service.py` 收敛为薄编排层；同时 shared contract validator 已新增并落地 `license_tool` bundle 校验入口，确保交付物契约可在运行时被稳定验证。下一阶段将继续扩展 shared validator 覆盖更多授权交付契约，确保跨模块一致性。
