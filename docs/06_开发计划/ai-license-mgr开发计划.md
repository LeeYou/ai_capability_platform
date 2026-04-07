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

## 3. 进度维护要求

每次开发前后更新状态、风险、阶段小结，并同步对照 `docs/05_评审/代码逻辑自洽整改清单.md` 中 RL-01 ~ RL-03。

## 4. 当前进度更新

### 4.1 已完成

1. 已完成 ai-license-mgr 基础版客户、密钥、授权策略、签发、校验、导出、审计日志与前端管理台。
2. 已完成基础版 Docker、测试与构建校验。

### 4.2 进行中

1. 当前已完成 ai-license-mgr 本轮整改实施：建立授权金标准测试向量源，覆盖硬件指纹、版本约束与 license 校验场景。
2. 当前已完成稳定授权诊断字段收敛：校验接口与签发记录已统一输出 `result` / `code` / `stage` / `details` / `diagnostics_version`。
3. 当前已完成 `license_tool` source bundle 发布材料增强：manifest/README/ERROR_CODES 中已补齐稳定诊断 code，并附带 `LICENSE_DIAGNOSTICS.json` 与 `VALIDATION_VECTORS.json`。
4. 当前已完成 ai-license-mgr 对 ai-prod Python 校验语义的一致性回归测试，形成跨模块基线。
5. 当前已完成前端授权工作台增强：已展示稳定校验 code/细节，并补齐 diagnostics / vectors 导出入口。
6. 当前已完成基线验证：ai-license-mgr backend unittest 与 frontend build/lint 均已通过。

### 4.3 未完成

1. 暂无；ai-license-mgr 模块当前轮 L11-L13 已全部完成，后续将转入 ai-prod / ai-sdk 侧的一致性继续收口。

### 4.4 阶段小结

ai-license-mgr 本轮已完成 L11-L13：一方面补齐授权金标准测试向量与统一诊断契约，形成硬件指纹、版本约束与 license 校验的统一基线；另一方面把校验接口与签发记录收敛为 `result` / `code` / `stage` / `details` 稳定字段，并将同一份契约和测试向量纳入 `license_tool` source bundle 发布物；同时新增 ai-license-mgr 对 ai-prod Python 校验语义的一致性回归测试，确保相同真实 license 在签发侧与运行侧得到一致结论。经后端单元测试与前端 build/lint 验证，当前 ai-license-mgr 模块本轮整改已完成。
