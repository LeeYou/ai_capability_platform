# ai-prod 模块设计

## 1. 模块目标

建设生产交付子系统，以统一 Docker 镜像方式提供工业级 REST 推理服务。

## 2. 模块职责

1. 统一 REST API 服务
2. 动态加载能力插件与模型包
3. 执行 license 校验
4. 提供健康检查、能力查询、reload 管理
5. 提供内置测试页面

## 3. 逻辑组件

1. API 网关层
2. Runtime 层
3. Capability 插件层
4. 模型包管理层
5. 更新与回滚控制器

## 4. 核心流程

1. 启动时扫描宿主机挂载目录
2. 按“挂载优先、镜像回退”策略装载资源
3. 校验 license 与模型 manifest
4. 构建能力实例池
5. 提供推理服务
6. 管理端触发 reload 或回滚

## 5. API 设计

1. `/api/v1/health`
2. `/api/v1/capabilities`
3. `/api/v1/license/status`
4. `/api/v1/infer/{capability_name}`
5. `/api/v1/admin/reload`

## 6. 资源管理

1. 模型版本化目录
2. 插件版本化目录
3. 活动版本原子切换
4. 实例池化管理 GPU/CPU 资源

## 7. 非功能要求

1. 并发安全
2. GPU 优先、CPU 自动回退
3. 输入格式统一抽象，支持图片、视频、PDF 等
4. 提供结构化日志和审计日志
5. 支持 x86 与 arm

## 8. 设计决策

1. 首期主服务采用 Python FastAPI，调用 C++ Runtime。
2. 推理核心保持插件化与标准 C ABI。
3. 生产镜像内置基线资源，同时支持宿主机热更新。
