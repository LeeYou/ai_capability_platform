# ai-test 开发计划

## 1. 模块目标

持续完善内部研发验收与交付验收能力，补齐生产镜像验收、C++ HTTP 主服务回归测试与更专业的测试报告能力。

## 2. 工作分解

| 编号 | 工作项 | 状态 |
| --- | --- | --- |
| TT1 | 搭建 ai-test 前后端工程骨架 | 已完成 |
| TT2 | 对接 ai-train 模型查询接口 | 已完成 |
| TT3 | 实现单接口测试流程 | 已完成 |
| TT4 | 实现批量测试流程 | 已完成 |
| TT5 | 实现 GPU/CPU 自动切换推理测试 | 已完成 |
| TT6 | 实现测试报告生成与导出 | 已完成 |
| TT7 | 实现测试镜像 | 已完成 |
| TT8 | 首期联调与验收 | 已完成 |
| TT9 | 生产镜像验收任务与回归脚本体系 | 已完成 |
| TT10 | 面向 C++ HTTP 主服务的性能/稳定性验收 | 已完成 |
| TT11 | 研发验收与交付验收双视角报告模板 | 已完成 |
| TT12 | 测试样本与训练标注 schema 映射收敛 | 已完成 |
| TT13 | 模型 / 插件 / license / revision 统一验收证据链 | 已完成 |
| TT14 | 新增能力模板化回归与交付验收用例 | 已完成 |

## 3. 进度维护要求

每次开发前后更新状态、风险、阶段小结，并同步对照 `docs/05_评审/代码逻辑自洽整改清单.md` 中 RTS-01 ~ RTS-03。

## 4. 当前进度更新

### 4.1 已完成

1. 已完成 ai-test 基础版工程骨架、模型目录同步、单测/批测、GPU/CPU 回退与测试报告导出能力。
2. 已完成基础前端管理台与 CUDA 11.8 测试镜像落地。
3. 已完成基础测试回归与 Docker 构建校验。

### 4.2 进行中

无。TT1–TT14 全部完成，ai-test 模块 R12 整改已收口。

### 4.3 未完成

无。

### 4.4 阶段小结

本轮（R12）已完成 TT12-TT14：TT12 引入 TASK_TYPE_OUTPUT_SCHEMAS 和任务类型感知仿真推理，_simulate_case_execution() 根据 task_type 生成 classification/detection/ocr/structured_extraction 对应格式输出，并新增 _validate_expected_output() 校验期望输出与训练标注 schema 兼容性；TT13 在 create_test_task() 中加载模型 manifest，构建 evidence_chain（source_train_task_id/manifest_checksum/artifact_path），写入 TestTaskModel.evidence_json 并在报告 summary 中暴露；TT14 新增 get_capability_test_template() 和 create_template_regression_task()，支持新能力快速建立标准化回归基线。新增 8 个测试用例，全部 17 个测试通过，RTS-01/02/03 整改收口。
