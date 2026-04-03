# ai-prod 模块设计

## 1. 模块目标

建设面向客户交付的真实工业运行底座，采用 **C++ HTTP 服务 + C++ Runtime + Capability 插件模式** 提供高并发 REST 推理服务、License 校验、热更新与回滚能力；同时提供面向内部测试和验收的 Web/UI 交互外壳。

## 2. 模块职责

1. 对外提供高并发 REST API 服务
2. 动态加载能力插件与模型包
3. 执行启动时与推理时双层 license 校验
4. 提供健康检查、能力查询、reload/rollback 管理
5. 提供面向内部测试和验收的 Web/UI 测试外壳

## 3. 逻辑组件

1. C++ HTTP 服务层
2. C++ Runtime 层
3. Capability 插件层
4. 模型包管理层
5. License 校验层
6. 更新与回滚控制器
7. Python/React 测试与验收外壳（内部可选）

## 4. 核心流程

1. 启动时扫描宿主机挂载目录与镜像内置目录
2. 按“挂载优先、镜像回退”策略装载资源
3. 校验 license、plugins registry 与模型 manifest
4. 创建能力实例池并注册能力路由
5. 对外提供高并发推理服务
6. 管理端触发 reload 或 rollback
7. 内部测试页面通过外壳调用生产主服务完成人工验收

## 5. API 设计

1. `/api/v1/health`
2. `/api/v1/capabilities`
3. `/api/v1/license/status`
4. `/api/v1/infer/{capability_name}`
5. `/api/v1/admin/reload`
6. `/api/v1/admin/rollback`
7. `/api/v1/admin/catalog`
8. `/api/v1/admin/metrics`

## 6. 资源管理

1. 模型版本化目录
2. 插件版本化目录
3. 活动版本原子切换
4. 实例池化管理 GPU/CPU 资源
5. 日志与审计目录管理

## 7. 非功能要求

1. 并发安全
2. GPU 优先、CPU 自动回退
3. 输入格式统一抽象，支持图片、视频、PDF 等
4. 提供结构化日志和审计日志
5. 提供统一运行时指标观测与交付验收基线输出
6. 支持 x86 与 arm
7. Python 测试外壳不能成为客户生产调用主链路

## 8. 设计决策

1. 生产主服务采用 C++ HTTP 服务。
2. Runtime 采用 C++ 插件化内核，并参考 `ai_platform` 的 Runtime 实现路线。
3. 推理核心保持插件化与标准 C ABI。
4. 生产镜像内置基线资源，同时支持宿主机热更新。
5. Python FastAPI + React 只作为内部测试与验收外壳。
