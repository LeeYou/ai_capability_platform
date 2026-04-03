# AI Platform 宿主机目录模板

本目录用于提供平台版 Docker / 本地运行时所依赖的宿主机目录约定，便于交付、部署、验收时快速准备现场环境。

## 推荐目录结构

```text
/opt/ai_platform/
├── plugins/
├── models/
├── license/
├── config/
└── logs/
```

在 Windows 本地验证场景下，可使用如下等价目录：

```text
<workspace>/deploy/host_template/
├── plugins/
├── models/
├── license/
├── config/
└── logs/
```

## 各目录用途

- `plugins/`
  - 放置能力插件动态库覆盖件。
  - 当前仓库默认能力样板为 `face_detect` 与 `liveness_action`。

- `models/`
  - 放置能力模型目录。
  - 推荐以 `capability_id` 为一级目录，例如 `models/face_detect/`。
  - 当前每个能力目录至少应包含 `manifest.yaml`、`checksum.sha256` 与 `manifest.yaml` 中声明的模型文件。

- `license/`
  - 放置 `license.dat` 或现场授权文件。
  - 建议同时放置机器指纹采集结果，便于续期和问题排查。

- `config/`
  - 放置平台配置覆盖文件。
  - 当前代码最主要的配置入口是 `config/platform.yaml`。

- `logs/`
  - 放置平台运行日志。
  - 当前至少包括：
    - `audit.log`
    - `runtime_audit.log`

## 交付建议

- 对客户现场交付时，应至少提供：
  - 目录模板
  - 默认 `platform.yaml`
  - 默认 `plugins_registry.txt`
  - License 放置说明
  - 回归脚本执行说明

当前仓库同时维护两类 `plugins_registry.txt`：

- `config/plugins_registry.txt`
  - 面向仓库内开发与本地构建验证
  - 默认引用 `build/bin/Release/` 下的插件产物
- `deploy/host_template/config/plugins_registry.txt`
  - 面向交付包解压后的运行目录
  - 默认引用 `plugins/` 与 `models/` 相对路径

建议在整理交付包后，先执行以下命令校验 registry 基线：

```powershell
powershell -ExecutionPolicy Bypass -File scripts/validate_plugins_registry.ps1 -RegistryPath deploy/host_template/config/plugins_registry.txt -DeliveryRoot deploy/host_template
```

如果交付目录中的插件与模型都已准备完成，可增加 `-RequireFilesExist` 做现场完整性校验：

```powershell
powershell -ExecutionPolicy Bypass -File scripts/validate_plugins_registry.ps1 -RegistryPath deploy/host_template/config/plugins_registry.txt -DeliveryRoot deploy/host_template -RequireFilesExist
```

启用 `-RequireFilesExist` 后，当前脚本除检查插件与模型目录存在外，还会校验每个能力模型目录满足最小模型包规范：

- `manifest.yaml` 存在
- `checksum.sha256` 存在
- `manifest.yaml` 中 `capability_id` 与 registry 中 capability 一致
- `manifest.yaml` 中 `model_file` 指向的模型文件存在

如需将当前仓库中的服务、插件、配置、脚本整理到 `deploy/host_template/`，可执行：

```powershell
powershell -ExecutionPolicy Bypass -File scripts/prepare_delivery_host_template.ps1
```

当前整理脚本会优先复制 `deploy/host_template/models/` 下已有模型；如对应样板模型目录不存在，则自动回退复制仓库根目录 `models/` 下的最小模型包。

如需先清理旧内容后重新整理，可增加 `-CleanTarget`：

```powershell
powershell -ExecutionPolicy Bypass -File scripts/prepare_delivery_host_template.ps1 -CleanTarget
```

如需一键执行“交付目录整理 + registry 校验 + 冷启动 smoke + 诊断抓取 + 验收结果落盘”，可执行：

```powershell
powershell -ExecutionPolicy Bypass -File scripts/run_delivery_acceptance.ps1 -PrepareDeliveryRoot -CleanDeliveryRoot -CaptureDiagnostics
```

执行后会在 `deploy/host_template/logs/acceptance/<timestamp>/` 下生成：

- `health.json`
- `license_status.json`
- `runtime_status.json`
- `runtime_diagnostics.json`
- `acceptance_summary.json`

如需将多个交付场景按配置批量回归，可执行：

```powershell
powershell -ExecutionPolicy Bypass -File scripts/run_delivery_acceptance_matrix.ps1
```

默认矩阵配置文件为：

- `config/delivery_acceptance_matrix.json`

矩阵执行后会在 `logs/acceptance_matrix/<timestamp>/matrix_summary.json` 输出总结果，并在每个场景目录下保存对应证据。

## 当前样板能力交付模板

当前仓库建议先将以下五个样板能力作为“模板能力”固化交付：

- `face_detect`
- `liveness_action`
- `idcard_detect`
- `doc_classify`
- `seal_detect`

推荐至少准备以下产物：

- 平台主服务二进制
- `libcap_face_detect.dll`
- `libcap_liveness_action.dll`
- `libcap_idcard_detect.dll`
- `libcap_doc_classify.dll`
- `libcap_seal_detect.dll`
- `models/face_detect/`
- `models/liveness_action/`
- `models/idcard_detect/`
- `models/doc_classify/`
- `models/seal_detect/`
- `config/platform.yaml`
- `config/plugins_registry.txt`
- `license/license.dat`
- `scripts/api_smoke_test.ps1`
- `scripts/validate_plugins_registry.ps1`

如果需要同步验证多交付形态，建议同时整理以下样板产物：

- Linux SO SDK 样板
  - `ai_sdk_face_detect_sample`
  - `ai_sdk_liveness_action_sample`
  - `ai_sdk_idcard_detect_sample`
  - `ai_sdk_doc_classify_sample`
  - `ai_sdk_seal_detect_sample`
  - `test_face_detect_sdk`
  - `test_liveness_action_sdk`
  - `test_idcard_detect_sdk`
  - `test_doc_classify_sdk`
  - `test_seal_detect_sdk`
- Windows DLL 样板
  - `ai_face_detect_sdk.dll`
  - `ai_liveness_action_sdk.dll`
  - `ai_idcard_detect_sdk.dll`
  - `ai_doc_classify_sdk.dll`
  - `ai_seal_detect_sdk.dll`
  - `face_detect_dll_sample`
  - `liveness_action_dll_sample`
  - `idcard_detect_dll_sample`
  - `doc_classify_dll_sample`
  - `seal_detect_dll_sample`
  - `test_face_detect_dll`
  - `test_liveness_action_dll`
  - `test_idcard_detect_dll`
  - `test_doc_classify_dll`
  - `test_seal_detect_dll`
- JNI 样板
  - `FaceDetectJniBridge.java`
  - `LivenessActionJniBridge.java`
  - `IdCardDetectJniBridge.java`
  - `DocClassifyJniBridge.java`
  - `SealDetectJniBridge.java`
  - `FaceDetectJniDemo.java`
  - `LivenessActionJniDemo.java`
  - `IdCardDetectJniDemo.java`
  - `DocClassifyJniDemo.java`
  - `SealDetectJniDemo.java`

其中 JNI 当前仍采用条件构建方式：环境满足时参与构建，不满足时允许跳过，但桥接模板已可作为后续新增能力的参考实现。

## 推荐的样板能力验证顺序

- 第一步：平台版主链路验证
  - 启动服务
  - 执行 `GET /api/v1/health`
  - 执行 `GET /api/v1/capabilities`
  - 执行 `POST /api/v1/infer/face_detect`
  - 执行 `POST /api/v1/infer/liveness_action`
  - 执行 `POST /api/v1/infer/idcard_detect`
  - 执行 `POST /api/v1/infer/doc_classify`
  - 执行 `POST /api/v1/infer/seal_detect`
  - 执行 `POST /api/v1/runtime/reload-all`
  - 执行 `POST /api/v1/runtime/rollback-all`

- 第二步：Linux SO SDK 模板验证
  - 执行 `test_face_detect_sdk`
  - 执行 `test_liveness_action_sdk`
  - 执行 `test_idcard_detect_sdk`
  - 执行 `test_doc_classify_sdk`
  - 执行 `test_seal_detect_sdk`
  - 确认 capability id、推理结果、授权失败诊断字段符合预期

- 第三步：Windows DLL 模板验证
  - 执行 `test_face_detect_dll`
  - 执行 `test_liveness_action_dll`
  - 执行 `test_idcard_detect_dll`
  - 执行 `test_doc_classify_dll`
  - 执行 `test_seal_detect_dll`
  - 确认导出接口、推理结果、授权失败诊断字段符合预期

- 第四步：JNI 模板验证
  - 在具备 JDK/JNI 环境时构建 JNI bridge
  - 通过 Java Demo 验证 capability id 与最小推理返回

- 对当前仓库版本，建议优先将本模板作为“交付包解压后的宿主机目录骨架”。

## 当前版本说明

当前仓库已形成平台主链路的 MVP 闭环，但 Docker 交付链路与插件产物路径仍需要按目标平台进一步固化。因此本模板的主要目标是先统一目录规范，降低后续交付整理成本。
