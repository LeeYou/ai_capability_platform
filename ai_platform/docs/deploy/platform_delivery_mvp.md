# 平台版 MVP 交付说明

本文档用于指导当前仓库版本的最小平台版交付、部署与验证。

## 1. 适用范围

当前仓库适合用于以下目标：

- 平台主链路演示
- 本地或测试环境最小部署
- 授权、推理、管理接口、reload/rollback 的最小闭环验证
- 五个样板能力的交付验证：`face_detect`、`liveness_action`、`idcard_detect`、`doc_classify`、`seal_detect`

当前版本暂不等同于完整客户正式交付版，尤其是以下内容仍需后续补齐：

- 17 个真实能力插件
- 完整前端测试页面
- 完整 Docker 生产交付链路
- 内部 License 签发 Web 服务
- 大规模多交付形态打包流程

## 2. 当前可交付内容

建议将以下内容整理为一版 MVP 交付包：

- 服务端二进制
- 五个样板插件二进制
- `config/platform.yaml`
- `config/plugins_registry.txt`
- `scripts/api_smoke_test.ps1`
- `deploy/host_template/`
- `docs/acceptance/platform_acceptance_checklist.md`
- License 放置说明

## 3. 运行前准备

### 3.1 必备文件

至少准备：

- 平台主程序
- `face_detect` 插件
- `liveness_action` 插件
- `idcard_detect` 插件
- `doc_classify` 插件
- `seal_detect` 插件
- 对应模型目录
- 可用 License 文件
- `platform.yaml`
- `plugins_registry.txt`

### 3.2 关键配置

当前服务主要从以下位置读取配置：

- `config/platform.yaml`
- `platform.yaml` 中的 `server.*` 与 `paths.*`
- 环境变量覆盖：
  - `AI_PLATFORM_CONFIG_PATH`
  - `AI_PLATFORM_LICENSE_PATH`
  - `AI_PLATFORM_SERVER_HOST`
  - `AI_PLATFORM_SERVER_PORT`
  - `AI_PLATFORM_SERVER_WORKERS`
  - `AI_PLATFORM_SERVER_REQUEST_TIMEOUT_MS`
  - `AI_PLATFORM_SERVER_MAX_BODY_SIZE_MB`
  - `AI_PLATFORM_SERVER_MAX_VIDEO_SIZE_MB`
  - `AI_PLATFORM_LICENSE_AUTO_RELOAD_INTERVAL_SECONDS`
  - `AI_PLATFORM_ADMIN_TOKEN`
  - `AI_PLATFORM_PLUGINS_REGISTRY_PATH`
  - `AI_PLATFORM_LICENSE_AUDIT_LOG_PATH`
  - `AI_PLATFORM_RUNTIME_AUDIT_LOG_PATH`

当前推荐按以下顺序理解配置生效链路：

1. 通过 `AI_PLATFORM_CONFIG_PATH` 或默认值定位 `platform.yaml`
2. 读取 `server.*` 与 `paths.*`
3. 依据 `paths.*` 推导 registry、license、审计日志默认路径
4. 最后由环境变量覆盖对应字段

## 4. 推荐目录组织

### 4.1 仓库内验证目录

```text
ai_platform/
├── build/
├── config/
├── deploy/host_template/
├── docs/
├── scripts/
└── src/
```

### 4.2 现场交付目录

```text
/opt/ai_platform/
├── plugins/
├── models/
├── license/
├── config/
└── logs/
```

## 5. 最小部署步骤

### 5.1 本地运行

1. 确认构建产物存在。
2. 确认 `platform.yaml` 中 `paths.*` 与现场目录约定一致。
3. 确认 `plugins_registry.txt` 已指向正确插件与模型目录。
4. 准备有效 License 文件。
5. 设置环境变量（如需覆盖默认值）。
6. 启动服务进程。
7. 运行 smoke test。

建议优先使用冷启动实例执行 smoke test，避免复用已被 reload/rollback 修改过状态的旧进程。

### 5.2 建议的最小检查项

启动后应优先检查：

- `GET /api/v1/health`
- `GET /api/v1/capabilities`
- `GET /api/v1/license/status`
- `GET /api/v1/runtime/status`
- `GET /api/v1/runtime/diagnostics`
- `POST /api/v1/infer/face_detect`
- `POST /api/v1/infer/liveness_action`
- `POST /api/v1/infer/idcard_detect`
- `POST /api/v1/infer/doc_classify`
- `POST /api/v1/infer/seal_detect`
- `POST /api/v1/runtime/reload-all`
- `POST /api/v1/runtime/rollback-all`

如需将交付准备与验收执行固化成一条标准链路，当前建议直接执行：

```powershell
powershell -ExecutionPolicy Bypass -File scripts/run_delivery_acceptance.ps1 -PrepareDeliveryRoot -CleanDeliveryRoot -CaptureDiagnostics
```

该脚本会依次完成：

1. 整理 `deploy/host_template/` 目录。
2. 校验交付态 `plugins_registry.txt`。
3. 使用交付态 `platform.yaml`、`plugins_registry.txt` 与 `license/license.dat` 启动冷实例。
4. 执行 smoke test。
5. 抓取 `health`、`license/status`、`runtime/status` 与 `runtime/diagnostics`。
6. 输出验收摘要与 JSON 证据到 `deploy/host_template/logs/acceptance/<timestamp>/`。

如需进一步将多个场景固化为配置驱动回归矩阵，可执行：

```powershell
powershell -ExecutionPolicy Bypass -File scripts/run_delivery_acceptance_matrix.ps1
```

默认矩阵配置位于 `config/delivery_acceptance_matrix.json`，当前至少覆盖：

- 正常单次验收
- 正常模式重复执行
- 缺失授权文件下的 `license_invalid` 场景

矩阵总结果会输出到 `deploy/host_template/logs/acceptance_matrix/<timestamp>/matrix_summary.json`。

如需将这些入口纳入构建机、交付验证机与可选 CTest 流程，请同时参考：

- `docs/deploy/ci_execution_guide.md`

## 6. 交付限制说明

当前版本的重点是“平台最小闭环可演示、可验证”，因此交付时应明确以下边界：

- 当前插件数量仍以样板能力为主
- 当前五个能力主要用于验证平台骨架、配置链路与多交付模板
- Docker 文件和生产部署链路需要继续按目标平台加固
- SDK / JNI / Windows DLL 仍属于样板化阶段

## 7. 建议的对外交付话术

建议对内外统一描述为：

- 当前版本是“平台版 MVP / 预交付版本”
- 已可验证平台骨架、授权机制、推理链路和管理接口
- 后续版本将逐步补齐真实能力、前端测试页、多交付形态和完整运维资产

## 8. 下一阶段落地建议

基于当前版本，建议优先推进：

1. 将五个样板能力逐步替换为真实业务能力。
2. 固化平台版部署包结构。
3. 增加配置驱动与冷启动重复执行的端到端回归。
4. 以五个样板能力为模板推进 Linux SO / JNI / Windows DLL 单能力交付。
