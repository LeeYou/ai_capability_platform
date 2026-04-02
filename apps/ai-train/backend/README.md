# ai-train backend

ai-train 后端首期工程骨架，提供训练子系统的基础 API、配置管理与数据集扫描能力。

## 当前能力

1. 健康检查接口
2. AI 能力列表接口
3. 数据集扫描接口

## 本地运行

```bash
cd /home/runner/work/ai_capability_platform/ai_capability_platform/apps/ai-train/backend
python -m uvicorn app.main:app --host 0.0.0.0 --port 26000
```

默认宿主机根目录为 `/data/ai_capability_platform`，可通过环境变量 `AI_CAP_HOST_ROOT` 覆盖。

