# ai-prod backend

ai-prod 后端首期工程，提供统一生产 REST 服务、宿主机资源扫描、license 双层校验、运行时实例池、reload/rollback 与内部测试验收外壳所需接口。

当前仓库已开始引入 `apps/ai-prod/cpp/` 下的 C++ HTTP 服务迭代实现，用于逐步把生产主链路从 Python 基础版收敛到 C++ HTTP + C++ Runtime。

## 当前能力

1. 健康检查、能力列表、license 状态接口
2. 宿主机挂载优先、镜像基线回退的资源扫描与能力装载
3. 标准 license 文件验签、时间窗口/能力范围/版本约束/硬件指纹校验
4. runtime revision、实例池、GPU 优先/CPU 自动回退
5. 统一推理接口与启动时/推理时双层 license 校验
6. reload/rollback、结构化日志与审计日志
7. 面向内部测试验收外壳的 `/internal/*` 查询接口

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

## C++ HTTP 迭代实现

```bash
cd /home/runner/work/ai_capability_platform/ai_capability_platform/apps/ai-prod/cpp
cmake -S . -B build
cmake --build build --parallel
ctest --test-dir build --output-on-failure
```

默认行为：

1. C++ 服务在独立运行时默认监听 `0.0.0.0:26005`；生产镜像/compose 默认改为对外 `26004`
2. `/api/v1/health`、`/api/v1/capabilities` 优先读取 runtime snapshot 直接响应；当 snapshot 缺失或不可用时，C++ 启动阶段会先尝试完成自举装载
3. `/api/v1/license/status` 由 C++ 直接读取标准 license 文件返回当前状态
4. 已补齐 `/api/v1/admin/rollback` 到 Python `/api/v1/admin/reload` 的兼容适配
5. 已新增 `/api/v1/admin/catalog` 用于输出 C++ 侧能力目录与轻量实例池诊断信息
6. snapshot 可用时，`/api/v1/infer/{capability_name}` 已由 C++ 直接完成请求解析、license quick check、设备选择、实例池借还、真实插件动态加载执行、结果生成与基础日志审计；snapshot 不可用时自动回退 Python backend
7. `reload/rollback` 已由 C++ 直接完成资源扫描、revision/operation SQLite 持久化、runtime snapshot 重写，以及实例池 drain 编排与切换后 catalog/pool 刷新
8. `license/status` 已改为由 C++ 直接读取标准 license 文件，`infer` 与 `reload/rollback` 已接入 license quick check
9. 已新增 `/api/v1/admin/license-reload`，支持 C++ 侧 license 手动重载与自动监测刷新
10. Python runtime 的 bootstrap / reload / rollback 也已补齐按能力范围与版本约束的二次 license 校验，并记录拒绝审计日志
11. `/internal/*` 查询接口仅保留在 Python 测试验收外壳侧，不再通过 C++ 生产主链路暴露
12. runtime snapshot / capability catalog 已补齐 `model_root`、`binary_path` 元数据，供 C++ infer 侧直接装载并调用插件
13. 启动阶段已支持在 runtime snapshot 缺失时由 C++ 直接完成资源扫描、license 校验、bootstrap revision 持久化与 snapshot 初始写入
14. 当前已新增 runtime 显式状态机，`/api/v1/admin/catalog` 可输出 `bootstrapping / ready / draining / transitioning / error` 状态与错误信息
15. `reload/rollback` 已增加切换互斥保护，并发管理操作会直接拒绝，避免运行时状态竞争
16. 当前已新增请求级 in-flight 跟踪与 RAII 请求租约，`/api/v1/admin/catalog` 可输出 active request 明细，drain 阶段会等待活动请求清空后再执行切换
17. 当前已补齐能力级 `execution_metrics` 与 `plugin_info` 观测字段，`/api/v1/admin/catalog` 可输出请求量、成功/失败次数、推理耗时及当前插件元数据
18. 作为后续继续替换完整插件生命周期的过渡实现
19. 当前生产镜像/compose 已切换为“C++ HTTP 对外 26004 + Python backend 仅容器内 26014”的双进程主链路

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
- `AI_PROD_CPP_SNAPSHOT_MAX_AGE_SECONDS`
- `AI_PROD_CPP_LICENSE_ROOT`
- `AI_PROD_CPP_LICENSE_AUTO_RELOAD_INTERVAL_SECONDS`
