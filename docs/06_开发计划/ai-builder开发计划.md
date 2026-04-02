# ai-builder 开发计划

## 1. 模块目标

落地多平台推理库构建、打包与产物管理能力。

## 2. 工作分解

| 编号 | 工作项 | 状态 |
| --- | --- | --- |
| B1 | 搭建 ai-builder 前后端工程骨架 | 已完成 |
| B2 | 对接能力与授权查询接口 | 已完成 |
| B3 | 固化标准 C ABI 与 CMake 模板 | 已完成 |
| B4 | 实现 Linux 构建链路 | 已完成 |
| B5 | 实现 Windows 构建链路 | 已完成 |
| B6 | 实现 JNI 可选构建链路 | 已完成 |
| B7 | 实现产物打包与目录组织 | 已完成 |
| B8 | 联调与验收 | 已完成 |

## 3. 进度维护要求

每次开发前后更新状态、风险、阶段小结。

## 4. 当前进度更新

### 4.1 本轮已完成

1. 已确认 ai-builder 为 ai-license-mgr 后的下一个实施模块。
2. 已完成 ai-builder 模块设计、开发计划与工程规范核对。
3. 已建立 ai-builder 后端 FastAPI + SQLite 工程骨架与基础配置。
4. 已建立 ai-builder 前端 React + TypeScript + Vite 工程骨架。
5. 已实现 ai-train 能力/模型与 ai-license-mgr 授权记录/策略同步及快照回退能力。
6. 已固化标准 C ABI、头文件模板、JNI 模板、CMake 模板与受控构建参数。
7. 已实现平台矩阵、构建任务、构建目标、构建日志、产物记录与审计日志能力。
8. 已实现 Linux x86_64 原生 CMake 构建链路，以及 Linux arm64 / Windows x86 / Windows x86_64 / JNI 模板交付链路。
9. 已实现 libs 标准目录组织、manifest/checksum 生成、归档下载与运行说明。
10. 已完成 ai-train/ai-test/ai-license-mgr/ai-builder 后端测试、四端前端 build/lint 与 ai-builder Docker 构建阶段校验。

### 4.2 本轮进行中

1. ai-builder 模块当前开发计划工作项已完成，后续进入增强迭代阶段。
2. 后续增强方向包括真实 Windows 交叉编译环境、JNI 实际编译链路与 builder/prod/SDK 联调。

### 4.3 阶段小结

ai-builder 模块已完成本轮计划内的目录同步、平台矩阵、标准 C ABI、Linux 原生构建、Windows/JNI 模板交付、产物打包归档、前端管理台与 CUDA 11.8 镜像文件落地，形成可运行、可校验、可持续迭代的基础版本闭环。
