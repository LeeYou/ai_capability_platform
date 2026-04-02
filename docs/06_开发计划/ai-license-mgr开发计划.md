# ai-license-mgr 开发计划

## 1. 模块目标

落地客户、密钥、license 管理与签发能力。

## 2. 工作分解

| 编号 | 工作项 | 状态 |
| --- | --- | --- |
| L1 | 搭建 ai-license-mgr 前后端工程骨架 | 已完成 |
| L2 | 实现客户管理 | 已完成 |
| L3 | 实现密钥对管理 | 已完成 |
| L4 | 实现 license 策略与签发 | 已完成 |
| L5 | 实现校验与导出 | 已完成 |
| L6 | 实现授权镜像 | 已完成 |
| L7 | 联调与验收 | 已完成 |

## 3. 进度维护要求

每次开发前后更新状态、风险、阶段小结。

## 4. 当前进度更新

### 4.1 本轮已完成

1. 已确认 ai-license-mgr 为 ai-test 后的下一个实施模块。
2. 已完成 ai-license-mgr 模块设计、开发计划与工程规范核对。
3. 已建立 ai-license-mgr 后端 FastAPI + SQLite 工程骨架与基础配置。
4. 已建立 ai-license-mgr 前端 React + TypeScript + Vite 工程骨架。
5. 已实现客户管理、密钥对管理与审计日志能力。
6. 已实现硬件指纹生成、license 策略管理、签发、校验与导出能力。
7. 已实现标准文件 `license.bin`、`pubkey.pem` 落盘与替换更新。
8. 已接入 ai-license-mgr 前端真实查询页面，展示客户、密钥、策略、签发记录与审计日志。
9. 已新增 ai-license-mgr CUDA 11.8 Dockerfile 与运行说明。
10. 已完成 ai-train/ai-test/ai-license-mgr 后端测试、三端前端 build/lint 与 ai-license-mgr Docker 构建阶段校验。

### 4.2 本轮进行中

1. ai-license-mgr 模块当前开发计划工作项已完成，后续进入增强迭代阶段。
2. 后续增强方向包括更细粒度的策略编辑、授权轮转与 builder/prod 联调查询能力。

### 4.3 阶段小结

ai-license-mgr 模块已完成本轮计划内的客户、密钥、授权策略、签发、校验、导出、审计日志、前端管理台与 CUDA 11.8 镜像文件落地，形成可运行、可校验、可持续迭代的基础版本闭环。
