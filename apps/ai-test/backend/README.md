# ai-test backend

ai-test 后端当前提供模型查询代理、单接口测试、批量测试、生产镜像验收任务、性能/稳定性验收基线管理，以及研发验收 / 交付验收双视角的测试报告生成与导出能力。

## 当前能力

1. 健康检查接口
2. ai-train 模型与能力信息同步/查询接口
3. 单接口测试与批量测试接口
4. GPU 优先、CPU 回退的基础执行策略
5. 面向 ai-prod 公共入口的 `acceptance_check.py` / `pressure_smoke.py` 验收任务编排
6. 面向 C++ HTTP 主服务的性能/稳定性验收基线模板初始化与查询/写入
7. 研发验收 / 交付验收双视角报告模板切换
8. 测试结果持久化与 HTML/JSON/PDF 报告生成
9. 测试报告导出接口

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

## 关键接口

1. `POST /api/v1/single-tests`
2. `POST /api/v1/batch-tests`
3. `POST /api/v1/acceptance-tasks`
4. `GET /api/v1/acceptance-tasks`
5. `GET /api/v1/acceptance-tasks/{id}`
6. `GET /api/v1/performance-baselines`
7. `POST /api/v1/performance-baselines`
8. `GET /api/v1/test-reports`
9. `GET /api/v1/test-reports/{id}?template_type=research|delivery`
10. `GET /api/v1/test-reports/{id}/export?export_format=json|html|pdf&template_type=research|delivery`
