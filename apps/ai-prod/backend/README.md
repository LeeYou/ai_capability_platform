# ai-prod backend

ai-prod 后端首期工程，提供统一生产 REST 服务、宿主机资源扫描、license 双层校验、运行时实例池、reload/rollback 与内置测试页接口。

## 当前能力

1. 健康检查、能力列表、license 状态接口
2. 宿主机挂载优先、镜像基线回退的资源扫描与能力装载
3. 标准 license 文件验签、时间窗口/能力范围/版本约束/硬件指纹校验
4. runtime revision、实例池、GPU 优先/CPU 自动回退
5. 统一推理接口、内置测试页所需数据接口
6. reload/rollback、结构化日志与审计日志

## 本地运行

```bash
cd /home/runner/work/ai_capability_platform/ai_capability_platform/apps/ai-prod/backend
python -m uvicorn app.main:app --host 0.0.0.0 --port 26004
```

默认宿主机根目录为 `/data/ai_capability_platform`，可通过 `AI_CAP_HOST_ROOT` 覆盖。

SQLite 数据库默认位于 `${AI_CAP_HOST_ROOT}/data/ai_prod.db`。

## 校验命令

```bash
cd /home/runner/work/ai_capability_platform/ai_capability_platform/apps/ai-prod/backend
PYTHONPATH=. python -m unittest discover -s tests -v
```
