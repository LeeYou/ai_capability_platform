# 平台版验收清单

本文档用于当前 AI Platform 仓库版本的 MVP 平台版验收。

## 1. 验收目标

本次验收重点验证以下能力：

- 服务可启动
- 配置链路可生效
- License 校验可生效
- 样板能力可推理
- 管理接口可访问
- reload / rollback 可执行
- 最小回归脚本可完成

## 2. 验收前检查

### 2.1 文件准备

确认以下内容已就绪：

- 平台服务二进制
- 插件二进制
- 模型目录
- 每个能力模型目录均包含 `manifest.yaml`
- 每个能力模型目录均包含 `checksum.sha256`
- 每个能力模型目录均包含 `manifest.yaml` 中声明的模型文件
- `config/platform.yaml`
- `config/plugins_registry.txt`
- License 文件
- `scripts/api_smoke_test.ps1`

### 2.2 配置准备

确认以下配置项符合现场环境：

- `server.host`
- `server.port`
- `server.admin_token`
- `server.request_timeout_ms`
- `server.max_body_size_mb`
- `server.max_video_size_mb`
- `server.license_auto_reload_interval_seconds`

如需覆盖默认值，确认环境变量已设置正确。

## 3. 验收执行项

### 3.1 服务启动

- [ ] 服务进程可正常启动
- [ ] 启动后未立即退出
- [ ] 日志目录可写
- [ ] 审计日志可生成

### 3.2 健康与状态接口

- [ ] `GET /api/v1/health` 返回成功
- [ ] `GET /api/v1/capabilities` 返回成功
- [ ] `GET /api/v1/runtime/status` 返回成功
- [ ] `GET /api/v1/runtime/diagnostics` 返回成功
- [ ] `GET /api/v1/metrics/runtime` 返回成功
- [ ] `GET /api/v1/license/status` 返回成功

### 3.3 推理接口

- [ ] `POST /api/v1/infer/face_detect` 成功返回
- [ ] `POST /api/v1/infer/liveness_action` 视频输入成功返回
- [ ] `POST /api/v1/infer/liveness_action` 多帧输入成功返回
- [ ] 非法 JSON 请求被拒绝
- [ ] 非法 media / image 输入被拒绝

### 3.4 License 校验

- [ ] License 有效时推理成功
- [ ] License 无效时推理被拒绝
- [ ] 未授权 capability 被拒绝
- [ ] License reload 后状态可更新

### 3.5 管理接口

- [ ] 管理接口缺失 `X-Admin-Token` 被拒绝
- [ ] 错误 `X-Admin-Token` 被拒绝
- [ ] 正确 `X-Admin-Token` 可执行 reload
- [ ] `POST /api/v1/runtime/reload-all` 可执行
- [ ] `POST /api/v1/runtime/reload/{capability_id}` 可执行
- [ ] `POST /api/v1/runtime/rollback-all` 可执行
- [ ] `POST /api/v1/runtime/rollback/{capability_id}` 可执行

### 3.6 回归脚本

- [ ] `scripts/api_smoke_test.ps1` 默认模式通过
- [ ] 自定义 `BaseUrl` 模式通过
- [ ] 自定义 `AdminToken` 模式通过
- [ ] `license_invalid` 模式通过
- [ ] `scripts/run_delivery_acceptance.ps1 -PrepareDeliveryRoot -CleanDeliveryRoot -CaptureDiagnostics` 通过
- [ ] `scripts/run_delivery_acceptance_matrix.ps1` 通过
- [ ] 默认 `normal` / `normal_repeat_3` matrix 场景已覆盖最小模型包校验
- [ ] 设置 `AI_PLATFORM_RUN_DELIVERY_CTEST=1` 后，`ctest -C Release -L delivery_acceptance --output-on-failure` 通过

### 3.7 样板能力模板

- [ ] `face_detect`、`liveness_action`、`idcard_detect`、`doc_classify` 与 `seal_detect` 的平台版样板产物已整理齐全
- [ ] 五个样板能力的模型目录均满足最小模型包规范
- [ ] `test_face_detect_sdk` 可通过
- [ ] `test_liveness_action_sdk` 可通过
- [ ] `test_idcard_detect_sdk` 可通过
- [ ] `test_doc_classify_sdk` 可通过
- [ ] `test_seal_detect_sdk` 可通过
- [ ] `test_face_detect_dll` 可通过
- [ ] `test_liveness_action_dll` 可通过
- [ ] `test_idcard_detect_dll` 可通过
- [ ] `test_doc_classify_dll` 可通过
- [ ] `test_seal_detect_dll` 可通过
- [ ] JNI 环境满足时，`FaceDetectJniDemo` 可验证 capability id 与最小推理
- [ ] JNI 环境满足时，`LivenessActionJniDemo` 可验证 capability id 与最小推理
- [ ] JNI 环境满足时，`IdCardDetectJniDemo` 可验证 capability id 与最小推理
- [ ] JNI 环境满足时，`DocClassifyJniDemo` 可验证 capability id 与最小推理
- [ ] JNI 环境满足时，`SealDetectJniDemo` 可验证 capability id 与最小推理

## 4. 建议验收证据

建议保存以下证据：

- 服务启动日志
- `health` 接口返回截图或输出
- `capabilities`、`license/status`、`runtime/status`、`runtime/diagnostics` 输出
- `face_detect` / `liveness_action` / `idcard_detect` / `doc_classify` / `seal_detect` 返回结果
- reload / rollback 返回结果
- smoke test 执行结果
- `logs/acceptance/<timestamp>/acceptance_summary.json`
- 失败场景下的 `logs/acceptance/<scenario>_<timestamp>/acceptance_failure_summary.json`
- `logs/acceptance_matrix/<timestamp>/matrix_summary.json`
- SDK / DLL 样板测试结果
- JNI 样板验证结果（如环境具备）

## 5. 当前版本已知边界

本清单对应的是当前仓库 MVP 版本，因此验收范围默认限定为：

- 以平台主链路为主
- 以 `face_detect`、`liveness_action`、`idcard_detect`、`doc_classify`、`seal_detect` 五个样板能力为主
- 不将“17 个真实能力全部完成”作为本轮验收前提
- 不将前端测试页、内部签发服务、多平台构建产物作为本轮强制验收项

## 6. 通过标准

满足以下条件时，可视为本轮 MVP 平台版验收通过：

- 所有核心接口可访问
- 样板能力推理成功
- License 控制有效
- 管理接口保护有效
- smoke test 可重复执行通过
- 样板能力模板测试可重复通过
- 交付文档与目录模板齐备
