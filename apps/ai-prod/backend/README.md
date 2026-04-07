# ai-prod backend

ai-prod backend 当前定位为**内部测试验收外壳与诊断查询服务**，不再承担客户生产运行主链路。生产侧公共 REST API 已完全收敛到 `apps/ai-prod/cpp/` 下的 C++ HTTP + C++ Runtime。

## 当前能力

1. 提供面向内部测试验收外壳的 `/internal/*` 诊断查询接口
2. 共享 SQLite revision / operation / audit 日志等验收查询能力
3. 保留 Python runtime service 逻辑用于内部单元测试与行为对照，不再通过公开 API 承担生产职责
4. Python runtime license/status 诊断已输出稳定字段：`result / code / stage / details / diagnostics_version`

## 本地运行

```bash
cd /home/runner/work/ai_capability_platform/ai_capability_platform/apps/ai-prod/backend
python -m uvicorn app.main:app --host 0.0.0.0 --port 26014
```

默认宿主机根目录为 `/data/ai_capability_platform`，可通过 `AI_CAP_HOST_ROOT` 覆盖。

SQLite 数据库默认位于 `${AI_CAP_HOST_ROOT}/data/ai_prod.db`。

## 校验命令

```bash
cd /home/runner/work/ai_capability_platform/ai_capability_platform/apps/ai-prod/backend
PYTHONPATH=. python -m unittest discover -s tests -v
```

## 授权诊断字段

`validate_license_bundle`、runtime snapshot 与 runtime revision detail 中的 `license_status` 现已统一输出：

- `result`
- `code`
- `stage`
- `details`
- `diagnostics_version`

## C++ HTTP 迭代实现

```bash
cd /home/runner/work/ai_capability_platform/ai_capability_platform/apps/ai-prod/cpp
cmake -S . -B build
cmake --build build --parallel
ctest --test-dir build --output-on-failure
```

默认行为：

1. C++ 服务在独立运行时默认监听 `0.0.0.0:26005`；生产镜像/compose 默认改为对外 `26004`
2. `/api/v1/health`、`/api/v1/capabilities` 由 C++ 直接读取 runtime snapshot 响应；当 snapshot 缺失或不可用时会返回运行时错误，不再回退 Python backend
3. `/api/v1/license/status` 由 C++ 直接读取标准 license 文件返回当前状态
4. `/api/v1/admin/reload` 与 `/api/v1/admin/rollback` 已由 C++ 直接执行，不再依赖 Python 公开接口
5. 已新增 `/api/v1/admin/catalog` 用于输出 C++ 侧能力目录与轻量实例池诊断信息
6. 已新增 `/api/v1/admin/metrics` 用于输出 C++ 侧统一运行时指标、endpoint 延迟分位与实例池利用率
7. runtime snapshot / revision 明细 / capability catalog 已补齐 capability 级 `max_batch_size`，实例池繁忙拒绝次数也会在 catalog / metrics 中暴露
8. 当前实例池已支持基础请求排队等待、排队上限与等待超时，且 capability snapshot / catalog 已补齐 `queue_wait_timeout_ms`、`max_pending_request_count` 调度配置透传；`/api/v1/admin/catalog`、`/api/v1/admin/metrics` 会同步输出 `pending_request_count`、`queued_request_count`、`queue_timeout_count`、`avg_queue_wait_ms`
9. `/api/v1/infer/{capability_name}` 已由 C++ 直接完成请求解析、license quick check、设备选择、实例池借还、真实插件动态加载执行、结果生成与基础日志审计；runtime snapshot 不可用时直接返回运行时错误
10. `reload/rollback` 已由 C++ 直接完成资源扫描、revision/operation SQLite 持久化、runtime snapshot 重写，以及实例池 drain 编排与切换后 catalog/pool 刷新
11. `license/status` 已改为由 C++ 直接读取标准 license 文件，`infer` 与 `reload/rollback` 已接入 license quick check
12. 已新增 `/api/v1/admin/license-reload`，支持 C++ 侧 license 手动重载与自动监测刷新
13. Python runtime 的 bootstrap / reload / rollback 逻辑仅保留用于内部单元测试与验收行为对照，不再通过公开 `/api/v1/*` 暴露
14. `/internal/*` 查询接口仅保留在 Python 测试验收外壳侧，不再通过 C++ 生产主链路暴露
15. runtime snapshot / capability catalog 已补齐 `model_root`、`binary_path` 元数据，供 C++ infer 侧直接装载并调用插件
16. 启动阶段已支持在 runtime snapshot 缺失时由 C++ 直接完成资源扫描、license 校验、bootstrap revision 持久化与 snapshot 初始写入
17. 当前已新增 runtime 显式状态机，`/api/v1/admin/catalog` 可输出 `bootstrapping / ready / draining / transitioning / error` 状态与错误信息
18. `reload/rollback` 已增加切换互斥保护，并发管理操作会直接拒绝，避免运行时状态竞争
19. 当前已新增请求级 in-flight 跟踪与 RAII 请求租约，`/api/v1/admin/catalog` 可输出 active request 明细，drain 阶段会等待活动请求清空后再执行切换
20. 当前已补齐能力级 `execution_metrics` 与 `plugin_info` 观测字段，`/api/v1/admin/catalog` 可输出请求量、成功/失败次数、推理耗时及当前插件元数据
21. 当前已补齐可选 `warmup` / `health_check` 生命周期钩子，相关状态、时间戳与失败信息会并入 capability 级 `execution_metrics`
22. 当前已新增统一输入 `payload codec`，`image / video / pdf` 请求会在 C++ 侧完成 base64 解码、格式校验，并将 `input_metadata` 回填到推理结果与审计日志
23. 当前已补齐基于 revision 的能力资源快照持久化；rollback 会优先恢复目标 revision 的具体模型目录、插件目录、插件文件与 manifest 元数据，而不是仅按能力名重扫当前目录
24. 当前生产镜像/compose 已切换为“C++ HTTP 对外 26004 + Python backend 仅容器内 26014”的双进程主链路

## 交付验收与运行规范

1. 默认环境模板：`/home/runner/work/ai_capability_platform/ai_capability_platform/apps/ai-prod/config/prod_defaults.env`
2. 交付验收脚本：`/home/runner/work/ai_capability_platform/ai_capability_platform/apps/ai-prod/scripts/acceptance_check.py`
3. 基础压测脚本：`/home/runner/work/ai_capability_platform/ai_capability_platform/apps/ai-prod/scripts/pressure_smoke.py`
4. 运行规范文档：`/home/runner/work/ai_capability_platform/ai_capability_platform/docs/07_部署运维/ai-prod运行规范.md`

可选环境变量：

- `AI_PROD_CPP_BIND_HOST`
- `AI_PROD_CPP_BIND_PORT`
- `AI_PROD_PY_BACKEND_HOST`
- `AI_PROD_PY_BACKEND_PORT`
- `AI_CAP_DATABASE_PATH`
- `AI_CAP_GPU_AVAILABLE`
- `AI_PROD_CPP_CONNECT_TIMEOUT_MS`
- `AI_PROD_CPP_READ_TIMEOUT_MS`
- `AI_PROD_CPP_WRITE_TIMEOUT_MS`
- `AI_PROD_CPP_RUNTIME_SNAPSHOT_PATH`
- `AI_PROD_CPP_RUNTIME_LOG_PATH`
- `AI_PROD_CPP_AUDIT_LOG_PATH`
- `AI_PROD_CPP_IMAGE_RESOURCE_ROOT`
- `AI_PROD_CPP_POOL_SIZE`
- `AI_PROD_CPP_INFER_QUEUE_WAIT_TIMEOUT_MS`
- `AI_PROD_CPP_INFER_QUEUE_MAX_PENDING_REQUESTS`
- `AI_PROD_CPP_SNAPSHOT_MAX_AGE_SECONDS`
- `AI_PROD_CPP_LICENSE_ROOT`
- `AI_PROD_CPP_LICENSE_AUTO_RELOAD_INTERVAL_SECONDS`
