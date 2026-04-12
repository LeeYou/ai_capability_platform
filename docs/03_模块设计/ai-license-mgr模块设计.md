# ai-license-mgr 模块设计

## 1. 模块目标

建设授权管理子系统，提供客户、公私钥、授权策略、授权文件、授权工具与授权审计管理能力，并保证与客户运行底座的 License 校验逻辑一致。

## 2. 模块职责

1. 客户管理
2. 密钥对管理
3. license 策略管理
4. license 文件生成、签名、校验
5. 授权工具管理与交付
6. 对 builder/prod 提供授权查询能力

## 3. 逻辑组件

1. Web 前端：客户台、密钥台、授权台、工具台
2. API 服务：客户、密钥、轮转/隔离、license、审计管理
3. 加密引擎：签名、验签、指纹生成
4. 文件导出器：`license.bin`、`pubkey.pem`、授权说明
5. 工具管理器：`license_tool` 标准 source bundle、版本归档、错误码说明与硬件信息查询说明

## 4. 核心数据

1. `customer`
2. `key_pair`
3. `license_policy`
4. `license_issue_record`
5. `license_tool_release`

## 5. 授权模型

1. 按时间授权
2. 按硬件指纹授权
3. 按能力范围授权
4. 按版本约束授权
5. 按交付形态授权

## 6. 文件要求

1. 内部宿主机目录：`/data/ai_capability_platform/license/`
2. 标准文件：`license.bin`、`pubkey.pem`
3. 交付工具：`license_tool`
4. 支持替换更新与版本归档，并以标准 C++ source bundle 方式交付 `license_tool`

## 7. 接口要求

1. 客户管理接口
2. 密钥管理接口
3. license 生成接口
4. license 查询接口
5. license 校验接口
6. 硬件指纹/授权工具信息接口

## 8. 非功能要求

1. 加密材料严格权限控制，并支持私钥轮转与隔离后的生命周期追踪
2. 所有签发与变更有审计日志
3. 使用 CST 时区管理生效与到期时间
4. 私钥签发侧与客户运行侧逻辑隔离，已支持密钥隔离、轮转迁移与历史链路追溯
5. License 规则必须与 ai-prod 运行时校验策略保持一致，尤其是 `allowed_versions` / `prefix` / `min_version` / `max_version` 等版本约束语义

## 9. 设计决策

1. 使用成熟密码学库实现签名验签。
2. 硬件指纹使用多特征组合哈希。
3. 主服务与 runtime 双层校验 license。
4. 授权管理系统主要服务内部交付流程，不直接部署到客户生产环境。

## 10. 整改设计与跟踪

### 10.1 当前整改重点

1. 已建立签发侧统一金标准测试向量源，覆盖硬件指纹、版本约束与 license 校验场景。
2. 已将授权失败原因、失败细节收敛为稳定字段：`result` / `code` / `stage` / `details`，避免调用方依赖错误文本解析。
3. 已建立 ai-license-mgr 对 ai-prod Python 校验语义的一致性回归基线，并将诊断契约与测试向量纳入 `license_tool` source bundle 发布物。

### 10.2 与其他模块的关键契约

1. 与 ai-prod 保持 canonical JSON、版本约束、硬件指纹、时间窗口和能力范围规则一致。
2. 与 ai-sdk / `license_tool` 保持统一授权诊断字段与统一校验语义。
3. 与 ai-builder 保持授权记录、交付材料、校验工具、导出清单的一致追溯关系。

### 10.3 对应整改编号

1. RL-01
2. RL-02
3. RL-03

### 10.4 平台字段增量设计

1. 授权策略、签发载荷、签发记录与 `license_tool` 统一新增四个字段：`operating_system`、`min_operating_system_version`、`system_architecture`、`application_name`。
2. 字段语义约束如下：
   - `operating_system`：必填，枚举限定为 `windows / linux / android / ios`。
   - `min_operating_system_version`：可选，空值表示不限制；运行态只做“当前系统版本 >= 最低系统版本”判断。
   - `system_architecture`：可选，空值表示不限制；运行态按规范化后的架构别名做等值判断。
   - `application_name`：必填，仅用于签发标识、审计与交付识别，不参与运行时准入拦截。
3. 运行态诊断契约新增稳定结果码：`operating_system_denied`、`operating_system_version_denied`、`system_architecture_denied`，并分别对应 `operating_system`、`operating_system_version`、`system_architecture` 三个稳定 stage。
4. `VALIDATION_VECTORS.json`、`LICENSE_DIAGNOSTICS.json`、README、错误码说明与 `license_tool` source bundle 必须同步携带上述字段和诊断契约，确保 ai-license-mgr / ai-prod / ai-sdk 三侧一致。
5. 本增量按模块跟踪：
    - L14：授权平台字段设计、策略/签发/前端/tool bundle 收口。
    - L15：与 ai-prod / ai-sdk 平台准入诊断契约同步。

## 11. Web 产品化设计补充

### 11.1 页面定位

1. `ai-license-mgr` 不是纯后台配置页，而是商业交付链路中的授权工作台。
2. 页面需要让交付工程师在一个连续流程中完成“客户 → 密钥 → 策略 → 签发 → 校验 → 导出 / 发布”。
3. 授权页面必须兼顾专业严肃性与可审计性，高风险操作需强提示。

### 11.2 页面结构

1. 概览页：客户数、有效密钥、待签发、即将过期、最近审计风险。
2. 客户台：客户列表、详情、关联 license、关联交付记录。
3. 密钥台：
   - 密钥对列表
   - 状态、用途、轮转记录、隔离记录
   - 风险提示与审计摘要
4. 策略与签发工作台：
   - 左侧策略列表
   - 中间策略编辑 / 签发表单
   - 右侧平台字段、版本约束、能力范围说明
5. 校验与工具页：
   - license 校验结果
   - diagnostics / vectors / tool release 导出
   - 与 ai-prod / ai-sdk 契约一致性说明

### 11.3 关键交互要求

1. 签发流程采用分步向导：选择客户 → 选择密钥 → 配置策略 → 预览载荷 → 签发与导出。
2. 轮转、隔离、失效等高风险动作必须展示影响范围（策略、签发记录、交付对象）。
3. 校验结果页需突出稳定 code / stage / details，不允许只显示原始文本。
4. 授权完成后需要给出“去构建交付包”的明确跳转入口。
