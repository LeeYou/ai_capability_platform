# AI 能力平台 (AI Capability Platform)

面向交付的 AI 能力运行平台 MVP，以统一 Runtime、HTTP 服务、授权与热更新机制承载多种 AI 能力插件。

## 概述

本平台不是简单的模型服务，而是一套完整的**可交付 AI 运行平台**，包含：

- **主 HTTP/REST 服务** — 统一能力路由、参数校验、授权检查
- **通用推理 Runtime** — 插件动态加载、实例池管理、并发调度
- **C++ 推理插件动态库** — 每个 AI 能力独立一个插件，标准 C ABI
- **离线授权系统** — 机器绑定、试用期控制、双层校验
- **热更新机制** — SO/模型/License 可热更新和回滚，无需重启

当前仓库重点是平台主链路闭环、配置驱动与后续扩展基线，而不是一次性堆满全部业务能力。

## 当前样板能力基线 (5 项)

| 分组 | 能力 |
|------|------|
| **人脸** | `face_detect`、`liveness_action` |
| **证件** | `idcard_detect` |
| **文档** | `doc_classify` |
| **印章** | `seal_detect` |

## 技术栈

- **语言**: C++17 (服务端/插件)
- **推理**: 插件内最小推理样板 / 可扩展到 ONNX Runtime 等后端
- **HTTP**: cpp-httplib
- **构建**: CMake 3.20+

## 项目文档

详细设计方案见 [`docs/design/`](docs/design/00_目录.md)，包含 15 篇设计文档覆盖架构、接口、部署、授权等所有方面。

当前仓库新增了面向 MVP 交付的配套资料：
- [`docs/deploy/platform_delivery_mvp.md`](docs/deploy/platform_delivery_mvp.md) — 平台版最小交付说明
- [`docs/acceptance/platform_acceptance_checklist.md`](docs/acceptance/platform_acceptance_checklist.md) — 平台版验收清单
- [`deploy/host_template/`](deploy/host_template/README.md) — 宿主机目录模板

## 快速开始

```powershell
cmake -S . -B build -DBUILD_TESTS=ON
cmake --build build --config Release

./build/bin/Release/ai_platform_server.exe

curl http://127.0.0.1:26000/api/v1/health
```

## Docker 运行

当前仓库已提供一套面向交付目录约定的 Docker 运行模板：

- `docker/Dockerfile`
- `docker/docker-compose.yml`
- `docker/docker-compose.cpu.yml`
- `docker/entrypoint.sh`

容器内默认同时保留两套目录：

- `/app/`
  - 镜像内置的服务、插件、模型与默认配置
- `/opt/ai_platform/`
  - 面向现场挂载与覆盖的宿主机目录

默认 compose 会挂载以下宿主机目录：

- `/opt/ai_platform/plugins`
- `/opt/ai_platform/models`
- `/opt/ai_platform/license`
- `/opt/ai_platform/config`
- `/opt/ai_platform/logs`

如需以 CPU 模式启动，可执行：

```powershell
docker compose -f docker/docker-compose.cpu.yml up --build
```

如需使用默认 compose，可执行：

```powershell
docker compose -f docker/docker-compose.yml up --build
```

容器启动时会自动：

- 初始化 `/opt/ai_platform/` 目录结构
- 若宿主机缺少 `platform.yaml` 或 `plugins_registry.txt`，则从镜像内默认配置复制
- 导出 `AI_PLATFORM_CONFIG_PATH` 与 `AI_PLATFORM_PLUGINS_REGISTRY_PATH`
- 将审计日志默认写入 `/opt/ai_platform/logs/`

当前 Docker 镜像内置的默认 registry 使用 Linux 插件命名：

- `plugins/libcap_face_detect.so`
- `plugins/libcap_liveness_action.so`
- `plugins/libcap_idcard_detect.so`
- `plugins/libcap_doc_classify.so`
- `plugins/libcap_seal_detect.so`

建议在首次启动前先准备：

- `/opt/ai_platform/license/license.dat`
- `/opt/ai_platform/config/plugins_registry.txt`
- `/opt/ai_platform/models/<capability_id>/` 最小模型包目录

其中模型目录当前需满足最小模型包规范，详见下文“最小模型包规范”。

## 最小 API 回归

当前仓库提供 Windows PowerShell 版最小回归脚本：

```powershell
powershell -ExecutionPolicy Bypass -File scripts/api_smoke_test.ps1
```

脚本支持通过参数覆盖目标地址与 Admin Token：

```powershell
powershell -ExecutionPolicy Bypass -File scripts/api_smoke_test.ps1 -BaseUrl http://127.0.0.1:26001 -AdminToken custom-admin-token
```

如需对同一目标实例重复执行 smoke，可使用：

```powershell
powershell -ExecutionPolicy Bypass -File scripts/api_smoke_test.ps1 -RepeatCount 3
```

如需使用一键回归脚本统一处理“服务可达性检查 / 可选启动服务 / 等待健康检查 / 重复执行 smoke”，可使用：

```powershell
powershell -ExecutionPolicy Bypass -File scripts/run_platform_smoke.ps1 -RepeatCount 3
```

如需由脚本尝试自行拉起服务，可增加：

```powershell
powershell -ExecutionPolicy Bypass -File scripts/run_platform_smoke.ps1 -StartServer -RepeatCount 3
```

当前服务启动还支持以下环境变量覆盖：

- `AI_PLATFORM_CONFIG_PATH`
- `AI_PLATFORM_SERVER_HOST`
- `AI_PLATFORM_SERVER_PORT`
- `AI_PLATFORM_SERVER_WORKERS`
- `AI_PLATFORM_SERVER_REQUEST_TIMEOUT_MS`
- `AI_PLATFORM_SERVER_MAX_BODY_SIZE_MB`
- `AI_PLATFORM_SERVER_MAX_VIDEO_SIZE_MB`
- `AI_PLATFORM_ADMIN_TOKEN`
- `AI_PLATFORM_LICENSE_PATH`
- `AI_PLATFORM_LICENSE_AUTO_RELOAD_INTERVAL_SECONDS`
- `AI_PLATFORM_PLUGINS_REGISTRY_PATH`
- `AI_PLATFORM_LICENSE_AUDIT_LOG_PATH`
- `AI_PLATFORM_RUNTIME_AUDIT_LOG_PATH`

当前配置生效顺序为：

- 启动时先读取 `AI_PLATFORM_CONFIG_PATH` 指定的 `platform.yaml`
- 然后解析 `server.*` 与 `paths.*`
- 再根据 `paths.*` 推导实际生效的 `plugins_registry`、`license`、`audit log` 路径
- 最后由环境变量再次覆盖对应字段

当前默认路径策略为：

- `license_path` 默认优先取 `paths.host_license_dir/license.dat`
- 如宿主机目录不可用，则回退到仓库内 `build/tmp/demo_license.dat`
- `plugins_registry` 默认优先取 `paths.host_config_dir/plugins_registry.txt`
- 如宿主机目录不可用，则回退到 `paths.builtin_config_dir/plugins_registry.txt` 或仓库默认 `config/plugins_registry.txt`
- 审计日志默认优先写入 `paths.host_log_dir`

当前建议明确区分两类 registry：

- `config/plugins_registry.txt`
  - 面向仓库内开发与本地构建验证
  - 默认使用 `build/bin/Release/` 下的插件路径
- `deploy/host_template/config/plugins_registry.txt`
  - 面向交付包解压后的标准运行目录
  - 默认使用 `plugins/` 与 `models/` 相对路径

如需在交付整理前先校验 registry 格式与字段，可执行：

```powershell
powershell -ExecutionPolicy Bypass -File scripts/validate_plugins_registry.ps1
```

如需校验交付态 registry，可执行：

```powershell
powershell -ExecutionPolicy Bypass -File scripts/validate_plugins_registry.ps1 -RegistryPath deploy/host_template/config/plugins_registry.txt -DeliveryRoot deploy/host_template
```

如需进一步校验插件与模型目录已经实际存在，可增加：

```powershell
powershell -ExecutionPolicy Bypass -File scripts/validate_plugins_registry.ps1 -RegistryPath deploy/host_template/config/plugins_registry.txt -DeliveryRoot deploy/host_template -RequireFilesExist
```

在当前版本中，`-RequireFilesExist` 除检查插件库与模型目录存在外，还会同时校验最小模型包结构。

如需将当前构建产物整理到 `deploy/host_template/`，可执行：

```powershell
powershell -ExecutionPolicy Bypass -File scripts/prepare_delivery_host_template.ps1
```

当前整理脚本会同时准备样板模型目录：

- 优先复制 `deploy/host_template/models/` 下的交付态模型
- 如缺失，则回退复制仓库根目录 `models/` 下的最小模型包

如需先清理旧的整理结果再重新生成，可增加：

```powershell
powershell -ExecutionPolicy Bypass -File scripts/prepare_delivery_host_template.ps1 -CleanTarget
```

当前 `server` 相关配置的生效范围：

- `request_timeout_ms`：影响 HTTP 读写超时
- `max_body_size_mb`：影响 HTTP payload 上限与 infer 请求体大小校验
- `max_video_size_mb`：当前影响 JSON 内联 `media.data` 的最小大小限制

当前仓库还提供了一个视频类请求的最小样板能力：`liveness_action`。该能力目前用于验证以下两类输入能够从 HTTP 层进入 Runtime，并传递到插件层完成最小闭环：

- `media.type=video` + `params.action`
- 多张 `images` 作为 `frame_sequence` + `params.action`

当前约定 `images[].data` 与 `media.data` 使用 **base64 文本载荷**；如提供 `data` 字段，HTTP 层会进行最小 base64 合法性校验。

当前约定 `images[].uri` 与 `media.uri` 仅接受**离线可访问的本地路径**形式：

- 普通本地路径
- `file://` URI

当前会拒绝 `http://`、`https://` 等远程 URL。

例如，可用如下方式验证自定义端口和自定义 Admin Token 生效：

```powershell
$env:AI_PLATFORM_SERVER_PORT='26001'
$env:AI_PLATFORM_ADMIN_TOKEN='custom-admin-token'
./build/bin/Release/ai_platform_server.exe

powershell -ExecutionPolicy Bypass -File scripts/api_smoke_test.ps1 -BaseUrl http://127.0.0.1:26001 -AdminToken custom-admin-token
```

如需验证 License 无效场景，可先用不存在的授权文件路径启动服务，再执行：

```powershell
$env:AI_PLATFORM_LICENSE_PATH='config/missing_license.dat'
powershell -ExecutionPolicy Bypass -File scripts/api_smoke_test.ps1 -Mode license_invalid
```

当前脚本覆盖：

- 健康检查
- infer 成功路径
- infer 失败路径（含 `license invalid`、`capability not licensed`）
- 非法 JSON / 错误 Content-Type / 缺少媒体输入 / 非法结构 / 非法格式 / 超长 request_id
- capabilities / runtime status / runtime metrics
- reload-all / 单能力 reload
- 管理写接口 Admin Token 缺失 / 错误 / 正确 token
- 自定义 `BaseUrl` 端口与 `/health` 返回端口一致性
- 自定义 `AdminToken` 生效且默认 token 失效
- `request_timeout_ms` / `max_body_size_mb` / `max_video_size_mb` 已接入当前 HTTP 层配置链路
- `liveness_action` 的 `media.type=video` 成功路径
- `liveness_action` 的多帧 `frame_sequence` 成功路径与非法 `action` 失败路径
- `images.data` / `media.data` 的非法 base64 失败路径
- `images.uri` / `media.uri` 的远程 URL 失败路径
- `license_invalid` 模式下的 infer / reload-all / 单能力 reload 拒绝路径
- 管理接口 `405 Method Not Allowed`

当前脚本已经按平台真实语义处理 `rollback-all`：

当前运行态可观测性相关接口包括：

- `GET /api/v1/runtime/status`
  - 面向运行摘要，返回能力数量、pool 摘要、runtime metrics 聚合、license 有效性与 capability 状态摘要
- `GET /api/v1/runtime/diagnostics`
  - 面向现场诊断，统一返回：
    - 当前生效的 `server` 配置
    - 当前生效的关键路径（`platform_config`、`plugins_registry`、审计日志路径）
    - runtime 初始化状态与 capability 装载摘要
    - registry 打开结果、已配置/已加载能力数量、已加载 capability 列表
    - 插件装载失败明细（`stage`、`library_path`、`model_dir`、`message`）
    - 当前 license 状态摘要
- `GET /api/v1/license/status`
  - 面向授权状态，返回有效性、失败原因、授权时间窗、权限位与 capability 授权列表

如需将“交付目录准备 + registry 校验 + 冷启动 smoke + 诊断抓取 + 验收结果落盘”串成一条标准验收链，可执行：

```powershell
powershell -ExecutionPolicy Bypass -File scripts/run_delivery_acceptance.ps1 -PrepareDeliveryRoot -CleanDeliveryRoot -CaptureDiagnostics
```

该脚本当前会：

- 调用 `prepare_delivery_host_template.ps1` 整理 `deploy/host_template/`
- 校验 `deploy/host_template/config/plugins_registry.txt`
- 以交付态 `platform.yaml` / `plugins_registry.txt` / `license/license.dat` 启动冷实例并执行 smoke
- 抓取 `health`、`license/status`、`runtime/status`、`runtime/diagnostics`
- 将验收摘要与 JSON 证据落盘到 `deploy/host_template/logs/acceptance/<timestamp>/`

如需将多种交付场景固化成配置驱动的回归矩阵，可执行：

```powershell
powershell -ExecutionPolicy Bypass -File scripts/run_delivery_acceptance_matrix.ps1
```

默认矩阵配置位于：

- `config/delivery_acceptance_matrix.json`

当前默认 `normal` 与 `normal_repeat_3` 场景已启用 `require_models=true`，因此会在基线验收中同时校验样板能力的最小模型包结构。

当前默认覆盖的场景包括：

- `normal`
- `normal_repeat_3`
- `license_invalid_missing_license`

矩阵执行完成后，会在 `deploy/host_template/logs/acceptance_matrix/<timestamp>/matrix_summary.json` 输出总汇总，并在每个场景子目录下保留对应验收证据。

当前失败场景已做统一摘要加固：

- 单场景验收失败时，会输出 `acceptance_failure_summary.json`
- 矩阵执行失败时，会在 `matrix_summary.json` 中汇总每个场景的：
  - `failure_category`
  - `failure_step`
  - `failure_suggestion`
  - `failure_summary_path`

当前内置的失败分类主要包括：

- `delivery_artifact_missing`
- `registry_invalid`
- `platform_config_missing`
- `license_invalid`
- `model_missing`
- `server_startup_failed`
- `smoke_failed`
- `diagnostics_capture_failed`

- 全部能力均具备 `previous_model_dir` 时允许全量成功
- 部分能力不存在可回滚前态时允许返回 `partial rollback failed`
- 因此更适合用于平台基线回归，而不是某两个固定能力的硬编码演示

## 样板能力模板回归

当前仓库已将 `face_detect`、`liveness_action`、`idcard_detect`、`doc_classify` 与 `seal_detect` 固化为首批样板能力模板，并补充了以下回归覆盖：

- `tests/test_plugin_manager.cpp`
  - 校验样板能力注册表加载
  - 校验最小模型包预校验
  - 校验 `instance_count` / `model_dir` 读取
  - 校验单能力模型 reload 的最小行为
- `tests/test_reload_controller.cpp`
  - 校验单能力 reload
  - 校验 rollback
  - 校验 reload 失败明细
  - 校验 reload-all
- `tests/test_license_manager.cpp`
  - 校验有效授权初始化
  - 校验 denied capability
  - 校验 invalid signature reload 失败
  - 校验 expired license reload 失败
- `src/sdk/linux_so/test_face_detect_sdk.cpp`
- `src/sdk/linux_so/test_liveness_action_sdk.cpp`
- `src/sdk/linux_so/test_idcard_detect_sdk.cpp`
- `src/sdk/linux_so/test_doc_classify_sdk.cpp`
- `src/sdk/linux_so/test_seal_detect_sdk.cpp`
- `src/sdk/windows_dll/test_face_detect_dll.cpp`
- `src/sdk/windows_dll/test_liveness_action_dll.cpp`
- `src/sdk/windows_dll/test_idcard_detect_dll.cpp`
- `src/sdk/windows_dll/test_doc_classify_dll.cpp`
- `src/sdk/windows_dll/test_seal_detect_dll.cpp`

## 最小模型包规范

当前平台已在插件加载与模型 reload 前增加最小模型包预校验。默认要求每个能力模型目录至少包含：

- `manifest.yaml`
- `checksum.sha256`
- `model.onnx`

其中 `manifest.yaml` 当前至少包含以下字段：

```yaml
capability_id: face_detect
version: 1.0.0
model_file: model.onnx
```

当前预校验会检查：

- 模型目录存在且为目录
- `manifest.yaml` 存在
- `checksum.sha256` 存在
- `model_file` 指向的模型文件存在
- `manifest.yaml` 中的 `capability_id` 与当前 capability 一致

当前仓库已为五个样板能力补充最小模型包目录：

- `models/face_detect/`
- `models/liveness_action/`
- `models/idcard_detect/`
- `models/doc_classify/`
- `models/seal_detect/`

如需执行完整测试，建议在开启 `BUILD_TESTS=ON` 后运行：

```powershell
ctest -C Release --output-on-failure
```

当前仓库已额外提供两个 **可选** 的 CTest 入口：

- `test_delivery_acceptance`
- `test_delivery_acceptance_matrix`

默认情况下，这两个测试会以 `skip` 方式跳过，不影响常规单元测试；如需启用，可先设置：

```powershell
$env:AI_PLATFORM_RUN_DELIVERY_CTEST='1'
ctest -C Release -L delivery_acceptance --output-on-failure
```

这样可以把交付验收与矩阵回归纳入标准 `ctest` 调度，同时保持当前受限机器上的默认非破坏性行为。

样板能力交付模板与推荐验证顺序见：

- `deploy/host_template/README.md`
- `docs/acceptance/platform_acceptance_checklist.md`
- `docs/acceptance/design_implementation_gap_assessment.md`
- `docs/deploy/ci_execution_guide.md`
- `docs/design/16_新增能力多交付接入规范.md`

如需继续扩展第四个及后续能力，可先使用最小脚手架生成器创建骨架文件：

```powershell
powershell -ExecutionPolicy Bypass -File scripts/generate_capability_scaffold.ps1 -CapabilityId doc_classify -CapabilityName "文档分类" -MediaMode image
```

该脚本当前会生成基础骨架文件，并半自动追加 `src/plugins/CMakeLists.txt`、`src/sdk/linux_so/CMakeLists.txt`、`src/sdk/windows_dll/CMakeLists.txt`、`src/jni/CMakeLists.txt` 中的新能力目标；但仍不会自动修改 `plugins_registry.txt`、运行时测试入口或文档，生成后仍需按 `docs/design/16_新增能力多交付接入规范.md` 完成剩余接线。

## 宿主机目录

```
/opt/ai_platform/
├── plugins/    # SO 插件 (可更新)
├── models/     # 模型 (可更新)
├── license/    # 授权文件
├── config/     # 配置覆盖
└── logs/       # 日志输出
```

Windows 本地验证可等价映射到：

```text
<workspace>/deploy/host_template/
├── plugins/
├── models/
├── license/
├── config/
└── logs/
```

## 仓库地址

```
https://git.agilestar.cn/ai_cpp/ai_platform.git
```
