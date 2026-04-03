# ai-prod 运行规范

## 1. 目标

固化 ai-prod 面向客户交付前的最小运行、验收与压测基线，确保当前 **C++ HTTP 主入口 + Python backend 外壳** 的过渡方案在交付、联调与现场部署时具备一致的执行标准。

## 2. 当前交付形态

1. 对外生产入口：`apps/ai-prod/cpp/build/ai_prod_cpp_proxy`
2. 内部测试验收外壳：`apps/ai-prod/backend`
3. 端口约定：
   - C++ HTTP 对外主入口：`26004`
   - Python backend 内部壳层：`26014`
4. `/internal/*` 仅保留给 Python 测试验收外壳，客户交付链路只校验 `/api/v1/*`

## 3. 部署前准备

1. 初始化宿主机目录

```bash
cd /home/runner/work/ai_capability_platform/ai_capability_platform
bash scripts/docker/init_host_root.sh
```

2. 准备标准运行配置模板

```bash
cd /home/runner/work/ai_capability_platform/ai_capability_platform
cp apps/ai-prod/config/prod_defaults.env /tmp/ai-prod-prod.env
```

3. 确认以下目录已有可交付内容：
   - `${AI_CAP_HOST_ROOT}/models`
   - `${AI_CAP_HOST_ROOT}/libs`
   - `${AI_CAP_HOST_ROOT}/license`
   - `${AI_CAP_HOST_ROOT}/configs`

## 4. 启动方式

### 4.1 启动 Python backend 外壳

```bash
cd /home/runner/work/ai_capability_platform/ai_capability_platform/apps/ai-prod/backend
PYTHONPATH=. python3 -m uvicorn app.main:app --host 127.0.0.1 --port 26014
```

### 4.2 启动 C++ HTTP 主入口

```bash
cd /home/runner/work/ai_capability_platform/ai_capability_platform/apps/ai-prod/cpp
cmake -S . -B build
cmake --build build --parallel
AI_PROD_PY_BACKEND_HOST=127.0.0.1 AI_PROD_PY_BACKEND_PORT=26014 AI_PROD_CPP_BIND_PORT=26004 ./build/ai_prod_cpp_proxy
```

### 4.3 生产镜像默认启动方式

`apps/ai-prod/Dockerfile` 当前已切换为双进程入口：镜像启动后先在容器内拉起 Python backend（`127.0.0.1:26014`），待健康后再启动 C++ HTTP 主服务（`0.0.0.0:26004`）。

## 5. 交付验收基线

### 5.1 必过检查项

1. `/api/v1/health` 返回 `status=ok`
2. `/api/v1/capabilities` 可返回当前能力列表
3. `/api/v1/license/status` 可返回标准 license 状态
4. `/api/v1/admin/catalog` 可返回 catalog / pool 诊断信息
5. `/api/v1/admin/revisions` 对外返回 `404`，确保内部接口未重新暴露
6. 如存在已装载能力，至少完成一次 `/api/v1/infer/{capability}` 成功调用

### 5.2 验收命令

```bash
cd /home/runner/work/ai_capability_platform/ai_capability_platform
python3 apps/ai-prod/scripts/acceptance_check.py --base-url http://127.0.0.1:26004
```

如需在验收阶段同时检查 `license-reload`：

```bash
cd /home/runner/work/ai_capability_platform/ai_capability_platform
python3 apps/ai-prod/scripts/acceptance_check.py \
  --base-url http://127.0.0.1:26004 \
  --run-admin-checks
```

## 6. 基础压测基线

当前仓库先固化“轻量并发 smoke”基线，用于交付前快速确认站点在并发请求下没有明显异常。

### 6.1 健康接口并发 smoke

```bash
cd /home/runner/work/ai_capability_platform/ai_capability_platform
python3 apps/ai-prod/scripts/pressure_smoke.py \
  --base-url http://127.0.0.1:26004 \
  --path /api/v1/health \
  --requests 32 \
  --concurrency 8 \
  --max-p95-ms 5000
```

### 6.2 推理接口并发 smoke（需已装载能力）

```bash
cd /home/runner/work/ai_capability_platform/ai_capability_platform
python3 apps/ai-prod/scripts/pressure_smoke.py \
  --base-url http://127.0.0.1:26004 \
  --path /api/v1/infer/<capability_name> \
  --method POST \
  --body-json '{"input_type":"json","payload":"{\"image\":\"demo\"}","prefer_device":"auto","options":{}}' \
  --requests 16 \
  --concurrency 4 \
  --max-p95-ms 10000
```

## 7. 推荐运行阈值

1. 健康/能力/license/catalog 查询：单次请求建议在 `1000ms` 内返回
2. 基础并发 smoke：成功率应为 `100%`
3. 推理并发 smoke：现场可按模型能力、硬件与 pool 配置单独放宽，但必须记录本次交付的 `p95/p99`
4. reload / rollback 前应确认当前无长时间卡住的 infer 请求
5. 如使用容器部署，对外交付面只允许暴露 `26004`，`26014` 必须保持容器内可达

## 8. 日志与排障关注点

1. Python runtime 日志：`${AI_CAP_HOST_ROOT}/logs/ai_prod_runtime.log`
2. Python 审计日志：`${AI_CAP_HOST_ROOT}/logs/ai_prod_audit.log`
3. runtime snapshot：`${AI_CAP_HOST_ROOT}/data/ai_prod_runtime_snapshot.json`
4. 如验收失败，优先检查：
   - license 是否完整
   - model / libs 目录结构是否满足 manifest 约束
   - C++ `26004` 与 Python `26014` 端口、宿主机根目录、snapshot 路径是否一致

## 9. 与 Makefile 的对应入口

```bash
cd /home/runner/work/ai_capability_platform/ai_capability_platform
make ai-prod-acceptance
make ai-prod-pressure-smoke
```
