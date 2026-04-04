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
