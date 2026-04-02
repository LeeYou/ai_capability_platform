# ai-license-mgr 模块设计

## 1. 模块目标

建设授权管理子系统，提供客户、公私钥、授权策略、授权文件管理能力。

## 2. 模块职责

1. 客户管理
2. 密钥对管理
3. license 策略管理
4. license 文件生成、签名、校验
5. 对 builder/prod 提供授权查询能力

## 3. 逻辑组件

1. Web 前端：客户台、密钥台、授权台
2. API 服务：客户、密钥、license、审计管理
3. 加密引擎：签名、验签、指纹生成
4. 文件导出器：license.bin、pubkey.pem

## 4. 核心数据

1. customer
2. key_pair
3. license_policy
4. license_issue_record

## 5. 授权模型

1. 按时间授权
2. 按硬件指纹授权
3. 按能力范围授权
4. 按版本约束授权

## 6. 文件要求

1. 宿主机目录：`/data/ai_capability_platform/license/`
2. 标准文件：`license.bin`、`pubkey.pem`
3. 支持替换更新

## 7. 接口要求

1. 客户管理接口
2. 密钥管理接口
3. license 生成接口
4. license 查询接口
5. license 校验接口

## 8. 非功能要求

1. 加密材料严格权限控制
2. 所有签发与变更有审计日志
3. 使用 CST 时区管理生效与到期时间

## 9. 设计决策

1. 使用成熟密码学库实现签名验签。
2. 硬件指纹使用多特征组合哈希。
3. 主服务与 runtime 双层校验 license。
