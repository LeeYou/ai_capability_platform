# CI 执行规范

本文档用于约定当前 AI Platform 仓库在构建机、受限机器与交付前验证场景下的标准执行方式。

## 1. 目标

当前规范重点解决以下问题：

- 默认应跑哪些测试
- 哪些测试需要显式启用
- 哪些测试适合构建机
- 哪些测试适合现场机或交付前验证机
- 失败后应优先查看哪些证据

## 2. 当前测试入口分层

### 2.1 默认 CTest 测试集

默认 `ctest -C Release --output-on-failure` 会覆盖：

- `tests/` 下的基础单元测试
- Linux SO SDK 样板测试
- Windows DLL 样板测试

该层测试特点：

- 不依赖手工启动 HTTP 服务
- 不要求显式开启交付验收环境变量
- 适合作为构建机默认回归入口

### 2.2 可选交付验收 CTest 测试集

当前仓库额外注册了两个可选测试：

- `test_delivery_acceptance`
- `test_delivery_acceptance_matrix`

对应标签：

- `delivery_acceptance`
- `optional`
- `matrix`

默认情况下，这两个测试会以 `skip` 方式跳过。

启用方式：

```powershell
$env:AI_PLATFORM_RUN_DELIVERY_CTEST='1'
ctest -C Release -L delivery_acceptance --output-on-failure
```

该层测试特点：

- 会触发交付目录准备、冷启动 smoke、诊断抓取或矩阵回归
- 更适合作为交付前验证、夜间回归或专用验证机构建步骤
- 不建议在所有受限机器上默认开启

### 2.3 脚本化交付验收入口

当前脚本入口包括：

- `scripts/run_delivery_acceptance.ps1`
- `scripts/run_delivery_acceptance_matrix.ps1`

适用场景：

- 本地交付前检查
- 现场验证
- 不依赖 CTest 的人工或半自动执行

## 3. 推荐执行矩阵

### 3.1 构建机默认流程

建议执行：

```powershell
cmake -S . -B build -DBUILD_TESTS=ON
cmake --build build --config Release
ctest -C Release --output-on-failure
```

适用范围：

- 日常提交验证
- 合并前基础回归
- 构建产物健康检查

### 3.2 构建机扩展流程

如构建机允许执行交付验收脚本，可增加：

```powershell
$env:AI_PLATFORM_RUN_DELIVERY_CTEST='1'
ctest -C Release -L delivery_acceptance --output-on-failure
```

适用范围：

- 夜间回归
- 交付前集成回归
- 版本候选构建验证

### 3.3 交付前验证机流程

建议直接执行：

```powershell
powershell -ExecutionPolicy Bypass -File scripts/run_delivery_acceptance.ps1 -PrepareDeliveryRoot -CleanDeliveryRoot -CaptureDiagnostics
```

如需批量场景回归，可执行：

```powershell
powershell -ExecutionPolicy Bypass -File scripts/run_delivery_acceptance_matrix.ps1
```

适用范围：

- 交付前最终验证
- 包结构核对
- 诊断证据留档

### 3.4 现场机或受限机器流程

建议优先执行：

- `scripts/validate_plugins_registry.ps1`
- `scripts/run_delivery_acceptance.ps1`

如机器策略限制服务拉起或脚本执行，应至少完成：

- 交付目录完整性检查
- registry 校验
- 配置文件与 license 文件就位检查
- 证据目录路径规划

## 4. 环境变量约定

### 4.1 CTest 交付验收开关

- `AI_PLATFORM_RUN_DELIVERY_CTEST=1`
  - 启用 `test_delivery_acceptance` 与 `test_delivery_acceptance_matrix`

### 4.2 平台运行态覆盖

常用环境变量包括：

- `AI_PLATFORM_CONFIG_PATH`
- `AI_PLATFORM_LICENSE_PATH`
- `AI_PLATFORM_PLUGINS_REGISTRY_PATH`
- `AI_PLATFORM_SERVER_HOST`
- `AI_PLATFORM_SERVER_PORT`
- `AI_PLATFORM_ADMIN_TOKEN`
- `AI_PLATFORM_RUNTIME_AUDIT_LOG_PATH`
- `AI_PLATFORM_LICENSE_AUDIT_LOG_PATH`

这些变量主要由：

- 手工运行服务
- `run_delivery_acceptance.ps1`
- `run_delivery_acceptance_matrix.ps1`

在执行期间注入或覆盖。

## 5. 失败后优先查看的证据

### 5.1 单场景验收失败

优先查看：

- `acceptance_failure_summary.json`
- `runtime_audit.log`
- `audit.log`
- `health.json`
- `runtime_diagnostics.json`

其中 `acceptance_failure_summary.json` 当前会输出：

- `step`
- `failure_category`
- `message`
- `suggestion`
- `evidence_root`

### 5.2 矩阵回归失败

优先查看：

- `matrix_summary.json`
- 对应场景目录下的 `acceptance_failure_summary.json`

矩阵汇总当前会提供：

- `failure_category`
- `failure_step`
- `failure_suggestion`
- `failure_summary_path`

## 6. 当前推荐原则

- 默认 CI 先保证基础 `ctest` 稳定通过
- 交付验收类测试通过环境变量显式启用
- 不把受策略影响的服务拉起测试强塞进所有机器的默认流程
- 交付前验证应优先保留 JSON 证据与失败摘要
- 现场机应优先选择最小扰动、可留痕的验收入口

## 7. 建议后续演进

后续如需要进一步规范 CI，可继续补齐：

- 分层 Pipeline 定义（build / unit / delivery_acceptance / matrix）
- 构建机与交付验证机的职责分离
- 统一产物归档目录规范
- 针对失败分类的自动告警或报告模板
