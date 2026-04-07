# ai-train backend

ai-train 后端首期工程骨架，提供训练子系统的基础 API、配置管理与数据集扫描能力。

## 当前能力

1. 健康检查接口
2. AI 能力注册与列表接口
3. 数据集绑定与列表接口
4. 标注任务创建、查询与结果提交接口
5. 训练任务创建、查询、状态流转与日志接口
6. 模型产物登记、列表与详情接口
7. 按任务类型分层的标注 schema（classification / detection / OCR / structured_extraction）
8. 标注结果到 `training_input.json` 的统一适配链路
9. 训练工作区准备、模板脚手架生成与训练执行导出
10. SQLite 元数据持久化

## 训练工作区

训练任务可通过 `POST /api/v1/training-tasks/{task_id}/prepare` 生成工作区，默认落盘到 `${AI_CAP_HOST_ROOT}/data/training_jobs/<task_id>/`，包含：

1. `train_config.json`
2. `run_training.sh`
3. `training_input.json`
4. `template_bundle.json`
5. `model_export_spec.json`
6. `train_runner.py`

训练任务也可通过 `POST /api/v1/training-tasks/{task_id}/execute` 直接完成一次受控的训练执行与导出模拟，生成 `exported_model/`、结果摘要与日志。

## 本地运行

```bash
cd /home/runner/work/ai_capability_platform/ai_capability_platform/apps/ai-train/backend
python -m uvicorn app.main:app --host 0.0.0.0 --port 26000
```

默认宿主机根目录为 `/data/ai_capability_platform`，可通过环境变量 `AI_CAP_HOST_ROOT` 覆盖。

SQLite 数据库默认位于 `${AI_CAP_HOST_ROOT}/data/ai_train.db`，也可通过 `AI_CAP_DATABASE_PATH` 覆盖。
