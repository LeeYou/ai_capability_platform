# 单机交付 SDK 开发计划

## 1. 模块目标

持续完善 Linux SO、JNI SO、Windows DLL、头文件、模型包、授权工具、文档与示例工程的统一交付能力，并纳入标准 `delivery_package/`。

## 2. 工作分解

| 编号 | 工作项 | 状态 |
| --- | --- | --- |
| S1 | 固化 SDK ABI 与头文件 | 已完成 |
| S2 | 生成 Linux 交付包 | 已完成 |
| S3 | 生成 Windows 交付包 | 已完成 |
| S4 | 生成 JNI 交付包 | 已完成 |
| S5 | 编写接入文档与验收说明 | 已完成 |
| S6 | 首期联调与验收 | 已完成 |
| S7 | 收敛 Linux/JNI/Windows SDK 标准目录 | 已完成 |
| S8 | 收敛 `license_tool`、示例工程与错误码文档 | 已完成 |
| S9 | 纳入统一 `delivery_package/` 与验收体系 | 已完成 |
| S10 | 与 ai-prod runtime / license / 诊断语义收敛 | 未开始 |
| S11 | 与 ai-builder / ai-prod 真实交付链产物一致性收敛 | 未开始 |
| S12 | SDK 装载校验、示例工程与验收回归增强 | 未开始 |

## 3. 进度维护要求

每次开发前后更新状态、风险、阶段小结，并同步对照 `docs/05_评审/代码逻辑自洽整改清单.md` 中 RS-01 ~ RS-02。

## 4. 当前进度更新

### 4.1 已完成

1. 已完成 SDK 基础版工程骨架、共享 ABI 头文件、Linux/Windows/JNI 包生成、模型包/license/头文件/动态库复制、文档与示例工程生成。
2. 已完成基础版 Docker、测试与构建校验。

### 4.2 进行中

1. 当前阶段已完成单机交付 SDK 标准化交付目录、工具、文档与验收一致性收口。
2. 当前已完成与 ai-builder `delivery_package/` 的目录命名与验收物料对齐：SDK 包已按 `sdk_*` 标准目录输出，并附带 `tools/license_tool`、验收清单、部署说明与快速校验脚本。
3. 当前已继续补齐 package 级 `version_manifest.json`、`delivery_summary.json`、`delivery_summary.md`，进一步对齐 ai-builder 摘要 schema 与交付复审入口。
4. 当前已完成 package 级 `acceptance_checklist.json`、`version_manifest.json`、`delivery_summary.json` 与 shared schema 对齐，checksum 字段命名已与 ai-builder 收敛。
5. 当前已完成本轮整改设计基线刷新：已补齐整改设计章节，并新增 S10-S12 作为下一轮模块整改工作项。

### 4.3 未完成

1. S10：与 ai-prod runtime / license / 诊断语义收敛。
2. S11：与 ai-builder / ai-prod 真实交付链产物一致性收敛。
3. S12：SDK 装载校验、示例工程与验收回归增强。

### 4.4 阶段小结

单机交付 SDK 上一轮已完成 S7-S9，具备标准目录、文档、工具、示例与验收摘要能力；但结合本轮逻辑自洽审查，仍需继续完成与 ai-prod 的 runtime / license / 诊断语义收敛、与 ai-builder / ai-prod 真实交付链产物一致性收敛，以及 SDK 装载校验和示例回归增强。因此本模块计划已进入新一轮整改阶段，新增 S10-S12 作为后续逐项实施与跟踪基线。
