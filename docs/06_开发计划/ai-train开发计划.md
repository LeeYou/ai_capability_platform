# ai-train 开发计划

## 1. 模块目标

持续完善内部研发侧的样本标注、训练管理、模型管理与能力查询能力，并提升 UI 体验与模型包标准化程度，为交付链路提供稳定输入。

## 2. 工作分解

| 编号 | 工作项 | 状态 |
| --- | --- | --- |
| T1 | 搭建 ai-train 前后端工程骨架 | 已完成 |
| T2 | 接入 SQLite 与宿主机持久化目录 | 已完成 |
| T3 | 实现能力注册与数据集绑定 | 已完成 |
| T4 | 实现样本标记基础功能 | 已完成 |
| T5 | 实现训练任务管理与日志跟踪 | 已完成 |
| T6 | 实现模型产物管理与查询 API | 已完成 |
| T7 | 实现 CUDA 11.8 训练镜像 | 已完成 |
| T8 | 首期联调与验收 | 已完成 |
| T9 | 标注台与训练台交互增强 | 已完成 |
| T10 | 模型包内容与交付 manifest 进一步标准化 | 已完成 |
| T11 | 与 ai-test / ai-builder 的交付元数据收敛 | 已完成 |
| T12 | 标注 schema 分层与任务类型标准化 | 已完成 |
| T13 | 标注结果到训练输入适配器链路收敛 | 已完成 |
| T14 | 真实训练执行器与模型导出链路收敛 | 已完成 |
| T15 | 模型包 manifest 与 runtime / builder 消费契约收敛 | 已完成 |
| T16 | 新增能力训练模板 / 测试模板 / 推理模板统一脚手架 | 已完成 |

## 3. 进度维护要求

每次开发前后更新状态、风险、阶段小结，并同步对照 `docs/05_评审/代码逻辑自洽整改清单.md` 中 RT-01 ~ RT-05。

## 4. 当前进度更新

### 4.1 已完成

1. 已完成 ai-train 基础版前后端骨架、数据集扫描、能力注册与元数据持久化。
2. 已完成标注任务、训练任务、模型产物、训练工作区准备与基础前端管理台。
3. 已完成基础版 Docker、测试与回归校验。

### 4.2 进行中

1. 当前阶段已明确 ai-train 后续重点转向“更专业的内部标注/训练 UI”和“更严格的交付模型包标准化”。
2. 当前已完成 T9：后端已补齐标注任务样本级详情、批量保存/批量提交接口，前端管理台已升级为更专业的标注台，并支持样本级编辑与批量提交。
3. 当前已完成 T9：训练台已补齐日志轮询、训练执行计划展示与训练结果摘要回显，前端可直接查看训练任务最近日志与执行元数据。
4. 当前已完成 T10：模型产物登记已补齐 `preprocessing`、`thresholds`、`labels`、`validation` 等标准 manifest 字段，并自动生成 `preprocess.json`、`labels.json`、`validation/acceptance_checklist.json` 等模型包内容。
5. 当前已完成 T11：模型 manifest 已补齐面向 ai-test / ai-builder 的 `delivery_metadata`，并同步更新 shared `manifest_model.json` schema，进一步收敛交付元数据接口。
6. 当前已结合总体计划 R7 第二轮，对前端补齐跨模块联调导航入口、当前模块标识与联调复审清单展示，便于训练侧与测试/构建/交付链路统一联调。
7. 当前已完成 R7 最终收口：前端已切换为共享 R7 workspace 配置与公共样式，并统一展示总体联调复审结论。
8. 当前已完成本轮整改设计基线刷新：已补齐整改设计章节，并新增 T12-T16 作为下一轮模块整改工作项。
9. 当前已正式完成 ai-train 模块整改实施：已完成模块设计文档、模块开发计划、工程规范与现状代码的回对，并完成 T12-T16 全量代码收敛。
10. 当前已完成按任务类型分层的标注 schema、样本级校验与前端分层编辑能力，统一支持 classification、detection、OCR、structured_extraction 四类任务。
11. 当前已完成标注结果到训练输入适配链路收敛：训练工作区已输出 `training_input.json`、`template_bundle.json`、`model_export_spec.json`、`train_runner.py` 与新的执行计划。
12. 当前已完成训练执行与导出链路收敛：训练任务可通过执行接口产生日志、结果摘要与 `exported_model/` 导出目录。
13. 当前已完成模型 manifest/runtime 契约收敛：模型产物已补齐 `task_type`、`runtime_contract`、模板 bundle 与导出文件信息，并同步更新 shared `manifest_model.json` schema/example。
14. 当前已完成基线验证：ai-train 后端单元测试、前端 build/lint、shared schema 测试均已通过。

### 4.3 未完成

1. 暂无；ai-train 模块当前轮 T12-T16 已全部完成，后续若继续增强，将进入下一轮增量规划。

### 4.4 阶段小结

ai-train 本轮已完成 T12-T16：在上一轮 T9/T10/T11 的基础上，进一步把标注能力按任务类型收敛为 classification、detection、OCR、structured_extraction 四类标准 schema，并同步落到后端校验、标注结果存储与前端分层编辑界面；同时建立了从标注结果到 `training_input.json` 的统一适配器链路，并在训练工作区中补齐 `template_bundle.json`、`model_export_spec.json`、`train_runner.py` 与新的执行计划；训练侧不再仅停留在脚手架提示，而是可通过执行接口产生日志、结果摘要与 `exported_model/` 导出目录；模型产物则进一步补齐 `task_type`、`runtime_contract`、模板 bundle、导出文件信息，并同步更新 shared `manifest_model.json` schema/example。经后端单元测试、前端 build/lint 与 shared schema 测试验证，当前 ai-train 模块整改已完成，本轮模块代码、设计文档与开发计划已对齐。
