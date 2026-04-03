# ai-prod backend

ai-prod 后端首期工程，提供统一生产 REST 服务、宿主机资源扫描、license 双层校验、运行时实例池、reload/rollback 与内置测试页接口。

当前仓库已开始引入 `apps/ai-prod/cpp/` 下的 C++ HTTP 服务迭代实现，用于逐步把生产主链路从 Python 基础版收敛到 C++ HTTP + C++ Runtime。

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

## C++ HTTP 迭代实现

```bash
cd /home/runner/work/ai_capability_platform/ai_capability_platform/apps/ai-prod/cpp
cmake -S . -B build
cmake --build build --parallel
ctest --test-dir build --output-on-failure
```

默认行为：

1. C++ 服务监听 `0.0.0.0:26005`
2. `/api/v1/health`、`/api/v1/capabilities`、`/api/v1/license/status` 优先读取 runtime snapshot 直接响应
3. snapshot 不可用或过期时，自动降级转发到 Python 后端 `127.0.0.1:26004`
4. 已补齐 `/api/v1/admin/rollback` 到 Python `/api/v1/admin/reload` 的兼容适配
5. 已新增 `/api/v1/admin/catalog` 用于输出 C++ 侧能力目录与轻量实例池诊断信息
6. snapshot 可用时，`/api/v1/infer/{capability_name}` 已接入 C++ 侧能力存在性校验、实例池借还与繁忙保护
7. `reload/rollback` 已在 C++ 侧接入实例池 drain 编排，切换期间阻断新的 infer 请求并在成功后刷新 catalog/pool
8. `license/status` 已改为由 C++ 直接读取标准 license 文件，`infer` 与 `reload/rollback` 已接入 license quick check
9. 已新增 `/api/v1/admin/license-reload`，支持 C++ 侧 license 手动重载与自动监测刷新
10. 作为后续替换为真实 C++ Runtime 主链路的过渡实现

可选环境变量：

- `AI_PROD_CPP_BIND_HOST`
- `AI_PROD_CPP_BIND_PORT`
- `AI_PROD_PY_BACKEND_HOST`
- `AI_PROD_PY_BACKEND_PORT`
- `AI_PROD_CPP_CONNECT_TIMEOUT_MS`
- `AI_PROD_CPP_READ_TIMEOUT_MS`
- `AI_PROD_CPP_WRITE_TIMEOUT_MS`
- `AI_PROD_CPP_RUNTIME_SNAPSHOT_PATH`
- `AI_PROD_CPP_POOL_SIZE`
- `AI_PROD_CPP_SNAPSHOT_MAX_AGE_SECONDS`
- `AI_PROD_CPP_LICENSE_ROOT`
- `AI_PROD_CPP_LICENSE_AUTO_RELOAD_INTERVAL_SECONDS`
