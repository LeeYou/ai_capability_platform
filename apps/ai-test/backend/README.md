# ai-test backend

ai-test 后端首期工程，提供模型查询代理、单接口测试、批量测试、测试报告生成与导出能力。

## 当前能力

1. 健康检查接口
2. ai-train 模型与能力信息同步/查询接口
3. 单接口测试与批量测试接口
4. GPU 优先、CPU 回退的基础执行策略
5. 测试结果持久化与 HTML/JSON/PDF 报告生成
6. 测试报告导出接口

## 本地运行

```bash
cd /home/runner/work/ai_capability_platform/ai_capability_platform/apps/ai-test/backend
python -m uvicorn app.main:app --host 0.0.0.0 --port 26001
```

默认宿主机根目录为 `/data/ai_capability_platform`，可通过环境变量 `AI_CAP_HOST_ROOT` 覆盖。

SQLite 数据库默认位于 `${AI_CAP_HOST_ROOT}/data/ai_test.db`。

## 校验命令

```bash
cd /home/runner/work/ai_capability_platform/ai_capability_platform/apps/ai-test/backend
PYTHONPATH=. python -m unittest discover -s tests -v
```
