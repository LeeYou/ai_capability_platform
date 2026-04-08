# ai-builder 开发计划

## 1. 模块目标

持续完善多平台推理库构建、打包与交付能力，统一输出标准 `delivery_package/`、镜像归档、SDK 目录、文档材料、挂载模板与工具链。

## 2. 工作分解

| 编号 | 工作项 | 状态 |
| --- | --- | --- |
| B1 | 搭建 ai-builder 前后端工程骨架 | 已完成 |
| B2 | 对接能力与授权查询接口 | 已完成 |
| B3 | 固化标准 C ABI 与 CMake 模板 | 已完成 |
| B4 | 实现 Linux 构建链路 | 已完成 |
| B5 | 实现 Windows 构建链路 | 已完成 |
| B6 | 实现 JNI 可选构建链路 | 已完成 |
| B7 | 实现产物打包与目录组织 | 已完成 |
| B8 | 首期联调与验收 | 已完成 |
| B9 | 输出标准 `delivery_package/` 目录 | 已完成 |
| B10 | 输出生产镜像 tarball、mount_template、tools、docs | 已完成 |
| B11 | 输出验收清单、版本清单与交付摘要 | 已完成 |
| B12 | 真实插件源码 / 真实构建输入主链路切换 | 已完成 |
| B13 | 模型包 / 插件 / license / delivery_package 追溯链路收敛 | 已完成 |
| B14 | 交付前运行时可装载性与一致性校验 | 已完成 |

## 3. 进度维护要求

每次开发前后更新状态、风险、阶段小结，并同步对照 `docs/05_评审/代码逻辑自洽整改清单.md` 中 RB-01 ~ RB-03。

## 4. 当前进度更新

### 4.1 已完成

1. 已完成 ai-builder 基础版目录同步、平台矩阵、标准 C ABI、Linux 原生构建、Windows/JNI 模板交付、产物打包归档与前端管理台。
2. 已完成基础版 Docker、测试与构建校验。
3. 已完成 B9-B11：delivery_package 完整物料（docker/sdk/licenses/mount_template/tools/docs/验收清单/版本清单/交付摘要）。
4. 已完成 B12（R11）：ONNX Runtime 任务类型感知插件源码模板与模型包文件复制到 SDK models 目录。
5. 已完成 B13（R11）：delivery_package 追溯链路（provenance: source_train_task_id、manifest checksum、builder_task_id）。
6. 已完成 B14（R11）：交付前运行时可装载性与一致性校验，pre_delivery_validation.json 写入 delivery_package。

### 4.2 进行中

无。B1–B14 全部完成，ai-builder 模块 R11 整改已收口。

### 4.3 未完成

无。

### 4.4 阶段小结

本轮（R11）已完成 B12-B14：

1. **B12**：`_render_source()` 从 echo 占位桩切换为 ONNX Runtime 任务类型感知 C++ 模板，支持 `ONNXRUNTIME_ENABLED` 编译宏控制真实推理路径，仿真模式下保持 ABI 合规回退；`CMakeLists.txt` 补齐 ONNX Runtime 可选链接选项；模型包文件（manifest.json、labels.json、preprocess.json、权重文件）从 ai-train `artifact_path` 复制到每个 SDK 的 `models/<capability>/<version>/` 目录。
2. **B13**：在每个目标 manifest 和任务级 build_manifest 中记录 `provenance`，包含 `source_train_task_id`、`source_manifest_path`、`source_manifest_checksum`、`model_artifact_path`、`builder_task_id`、`issue_record_id`；`package_manifest.json` 中同步写入 `provenance` 字段，B13 追溯链路全链路闭环。
3. **B14**：新增 `_validate_model_package()`、`_validate_plugin_loadability()`、`_run_pre_delivery_checks()` 函数，在每个目标构建完成后执行：模型包完整性校验、license 文件存在性、插件 ctypes 动态装载与 ABI 符号校验；校验结果写入 `delivery_package/pre_delivery_validation.json`，`package_manifest.json` 中同步更新 `pre_delivery_validation_status`；B9-B14 全部写入 `stage_status`。

所有新增逻辑均有测试覆盖（新增 11 个测试用例，原有 4 个测试继续通过），共 15 个测试全部通过。ai-builder 模块 B1-B14 全量完成，RB-01/RB-02/RB-03 整改收口。
