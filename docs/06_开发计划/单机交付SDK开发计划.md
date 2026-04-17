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
| S10 | 与 ai-prod runtime / license / 诊断语义收敛 | 已完成 |
| S11 | 与 ai-builder / ai-prod 真实交付链产物一致性收敛 | 已完成 |
| S12 | SDK 装载校验、示例工程与验收回归增强 | 已完成 |

## 3. 进度维护要求

每次开发前后更新状态、风险、阶段小结，并同步对照 `docs/05_评审/代码逻辑自洽整改清单.md` 中 RS-01 ~ RS-03。

## 4. 当前进度更新

### 4.1 已完成

1. 已完成 SDK 基础版工程骨架、共享 ABI 头文件、Linux/Windows/JNI 包生成、模型包/license/头文件/动态库复制、文档与示例工程生成。
2. 已完成基础版 Docker、测试与构建校验。
3. 已完成单机交付 SDK 标准化交付目录、工具、文档与验收一致性收口。
4. 已完成与 ai-builder `delivery_package/` 的目录命名与验收物料对齐：SDK 包已按 `sdk_*` 标准目录输出，并附带 `tools/license_tool`、验收清单、部署说明与快速校验脚本。
5. 已补齐 package 级 `version_manifest.json`、`delivery_summary.json`、`delivery_summary.md`，进一步对齐 ai-builder 摘要 schema 与交付复审入口。
6. 已完成 package 级 `acceptance_checklist.json`、`version_manifest.json`、`delivery_summary.json` 与 shared schema 对齐，checksum 字段命名已与 ai-builder 收敛。
7. 已完成 S10：SDK 内 `tools/license_tool` 已附带 `LICENSE_DIAGNOSTICS.json`、`VALIDATION_VECTORS.json`，manifest/README/验收清单/校验脚本已同步对齐 ai-prod / ai-license-mgr 的稳定授权诊断语义。
8. 已完成 S11：SDK 包生成已强依赖 ai-builder 交付目录（`lib/include/license` 必须存在），SDK manifest 中附带 `source_builder_manifest`，实现了与 ai-builder 真实交付链产物的一致性收敛。
9. 已完成 S12：SDK 包内已内置 `validation/verify_sdk_package.py` 校验脚本，可验证标准目录结构、manifest、checksums、LICENSE_DIAGNOSTICS.json 与 VALIDATION_VECTORS.json 齐全；已生成 `sample_c_api.c`、`CMakeLists.txt`（Linux/Windows/JNI）和 `NativeBridge.java` 示例工程；后端单元测试已覆盖校验脚本执行通过的端到端回归。
10. 已完成基线验证：ai-sdk 后端单元测试（全部 5 个测试用例）均已通过，stage_status 已同步更新为 S7–S12 全部 completed。

### 4.2 进行中

1. 暂无。

### 4.3 未完成

1. 暂无；ai-sdk 模块当前轮 S11-S12 已全部完成，后续如继续推进将转入新的 SDK 增量计划。

### 4.4 阶段小结

单机交付 SDK 本轮已完成 S11-S12：SDK 包生成已强依赖 ai-builder 真实交付目录（缺少 lib/include/license 则构建报错），manifest 中附带 `source_builder_manifest` 实现产物溯源；同时在每个目标包内生成 `validation/verify_sdk_package.py` 校验脚本（检查必要文件存在性）、标准示例工程（C/C++/Java），并通过后端单元测试对校验脚本执行做端到端回归。`stage_status` 已同步更新为 S7–S12 全部 completed。当前 ai-sdk 模块本轮所有整改项均已完成。
