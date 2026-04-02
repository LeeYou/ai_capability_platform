# ai-builder 模块设计

## 1. 模块目标

建设推理库构建子系统，面向多平台生成交付级推理库产物。

## 2. 模块职责

1. 从 ai-train 获取能力与模型信息
2. 从 ai-license-mgr 获取授权信息
3. 编译能力插件 SO/DLL
4. 生成头文件、JNI 可选封装与构建清单
5. 组织多平台交付目录

## 3. 逻辑组件

1. Web 前端：构建台、产物台
2. API 服务：构建任务、平台矩阵、产物查询
3. 构建执行器：CMake 编译、多平台参数封装
4. 打包器：lib/include/license/manifest 产物归档

## 4. 核心数据

1. build_task
2. build_target
3. build_artifact
4. build_manifest

## 5. 产物目录要求

示例：

- `/data/ai_capability_platform/libs/linux_x86_64/face_detect/lib/libface_detect.so`
- `/data/ai_capability_platform/libs/linux_x86_64/face_detect/include/`

## 6. 平台支持

1. Linux x86_64
2. Linux arm64
3. Windows x86
4. Windows x86_64
5. JNI 可选支持

## 7. 接口要求

1. 能力列表接口
2. 授权列表接口
3. 构建任务创建/查询接口
4. 产物下载接口

## 8. 非功能要求

1. 构建可复现
2. 构建日志持久化
3. 产物包含版本、校验与依赖说明
4. 构建参数受控，避免任意命令执行风险

## 9. 设计决策

1. 推理库采用 C++ + CMake。
2. 运行后端优先 ONNX Runtime。
3. 一能力一插件，公共 runtime 作为共享层。
4. 统一标准 C ABI 与头文件模板。
