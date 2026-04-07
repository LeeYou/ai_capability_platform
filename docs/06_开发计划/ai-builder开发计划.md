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
| B12 | 真实插件源码 / 真实构建输入主链路切换 | 未开始 |
| B13 | 模型包 / 插件 / license / delivery_package 追溯链路收敛 | 未开始 |
| B14 | 交付前运行时可装载性与一致性校验 | 未开始 |

## 3. 进度维护要求

每次开发前后更新状态、风险、阶段小结，并同步对照 `docs/05_评审/代码逻辑自洽整改清单.md` 中 RB-01 ~ RB-03。

## 4. 当前进度更新

### 4.1 已完成

1. 已完成 ai-builder 基础版目录同步、平台矩阵、标准 C ABI、Linux 原生构建、Windows/JNI 模板交付、产物打包归档与前端管理台。
2. 已完成基础版 Docker、测试与构建校验。

### 4.2 进行中

1. 当前阶段已明确 ai-builder 后续重点是成为真正的最终交付包生成中心。
2. 当前已完成 B9：构建任务结束后会自动输出标准 `delivery_package/` 目录骨架，并提供归档下载入口。
3. 当前已完成 B10：delivery_package 已补齐 ai-prod 生产镜像构建上下文 tarball、mount_template、tools 与 docs 交付物料。
4. 当前已完成 B11：delivery_package 已补齐验收清单、版本清单与交付摘要，交付包元信息已具备最终收口能力。
5. 对照总体计划核对后，R3“标准交付包与验收体系融合实现”在 ai-builder 侧已完成，后续残留工作主要转向跨模块 schema 与交付材料继续细化。
6. 当前已结合总体计划 R7，对前端构建台补齐在线创建构建任务、任务详情查看、构建目标下载与 `delivery_package` 交付摘要预览，进一步提升内部交付工作台的专业化程度。
7. 当前已结合总体计划 R7 第二轮，继续补齐跨模块联调导航入口、当前模块标识与联调复审清单展示，提升与 ai-license-mgr / ai-prod / ai-test / ai-train 的统一联调效率。
8. 当前已完成 R7 最终收口：前端已切换为共享 R7 workspace 配置与公共样式，并统一展示总体联调复审结论。
9. 当前已完成与 shared schema 的最终对齐：`acceptance_checklist.json`、`version_manifest.json`、`delivery_summary.json`、`mount_template`、`tools_bundle`、`docs_bundle` 均已有统一 schema 与 example，可支撑现场交付复审复用。
10. 当前已完成本轮整改设计基线刷新：已补齐整改设计章节，并新增 B12-B14 作为下一轮模块整改工作项。

### 4.3 未完成

1. B12：真实插件源码 / 真实构建输入主链路切换。
2. B13：模型包 / 插件 / license / delivery_package 追溯链路收敛。
3. B14：交付前运行时可装载性与一致性校验。

### 4.4 阶段小结

ai-builder 上一轮已完成 B9-B11，具备标准 `delivery_package/`、交付摘要与 shared schema 收敛能力；但结合本轮逻辑自洽审查，仍需继续完成真实插件构建链切换、模型包 / 插件 / license / delivery_package 的可追溯性，以及交付前运行时可装载性校验。因此本模块计划已进入新一轮整改阶段，新增 B12-B14 作为后续逐项实施与跟踪基线。
