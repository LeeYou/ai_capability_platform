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
| B15 | 构建向导、平台选择与交付预览工作台重构 | 已完成 |
| B16 | 实时日志、阶段状态与失败重试工作台重构 | 已完成 |
| B17 | delivery_package / 产物目录树 / 校验结果视图重构 | 已完成 |
| B18 | 构建完成后的生产验收联动与首页队列概览收口 | 已完成 |

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

1. 当前已完成 B15-B18：ai-builder 前端已升级为“首页概览 / 构建向导 / 任务工作台 / 交付包视图”四段式交付工作台。
2. 当前已完成 B15：构建向导已收口模型、授权、平台与 JNI 选项输入，并在右侧提供交付预览。
3. 当前已完成 B16：任务工作台已补齐构建队列、阶段状态、目标输出与归档下载入口。
4. 当前已完成 B17：交付包视图已补齐 artifact 列表、manifest / provenance JSON 与 delivery_package 下载入口。
5. 当前已完成 B18：首页已重构为优先构建模型、失败任务回看与去 ai-prod 验收的连续动作入口。

### 4.3 未完成

1. 暂无；B15-B18 已全部完成，后续如继续推进将进入下一轮交付体验优化。

### 4.4 阶段小结

ai-builder 已完成 B15-B18：现已把真实构建链路重构为构建向导、任务工作台与交付包视图，交付工程师可以在同一工作台中完成模型 / license 选择、平台目标配置、构建状态查看、产物下载、manifest / provenance 校验以及去 ai-prod 的下一步验收联动。经前端 `npm run build && npm run lint` 验证，当前 ai-builder Web 工作台重构已完成。
