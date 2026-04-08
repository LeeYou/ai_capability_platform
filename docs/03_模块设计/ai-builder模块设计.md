# ai-builder 模块设计

## 1. 模块目标

建设交付构建子系统，面向内部交付流程生成真实工业运行底座所需的多平台推理库、生产镜像、标准交付包与验收材料。

## 2. 模块职责

1. 从 ai-train 获取能力与模型信息
2. 从 ai-license-mgr 获取授权信息
3. 编译能力插件 SO/DLL/JNI 产物
4. 组装生产镜像、SDK、工具与文档
5. 生成标准 `delivery_package/` 目录
6. 输出构建清单、checksum、manifest 与验收物料

## 3. 逻辑组件

1. Web 前端：构建台、交付包管理台、产物台
2. API 服务：构建任务、平台矩阵、交付包查询
3. 构建执行器：CMake 编译、多平台参数封装
4. 打包器：docker/sdk/licenses/mount_template/docs/tools 归档
5. 清单生成器：manifest/checksum/版本说明/验收清单

## 4. 核心数据

1. `build_task`
2. `build_target`
3. `build_artifact`
4. `build_manifest`
5. `delivery_package`

## 5. 产物目录要求

最终输出必须满足：

```text
delivery_package/
├── docker/
├── sdk_linux_x86_64/
├── sdk_linux_aarch64/
├── sdk_windows_x86_64/
├── sdk_windows_x86/
├── licenses/
├── mount_template/
├── docs/
└── tools/
```

## 6. 平台支持

1. Linux x86_64
2. Linux arm64
3. Windows x86
4. Windows x86_64
5. JNI 交付支持
6. Docker 镜像归档支持

## 7. 接口要求

1. 能力列表接口
2. 授权列表接口
3. 构建任务创建/查询接口
4. 交付包查询/下载接口
5. 产物下载接口

## 8. 非功能要求

1. 构建可复现
2. 构建日志持久化
3. 产物包含版本、校验、依赖说明与验收材料
4. 构建参数受控，避免任意命令执行风险
5. 交付目录结构必须统一、稳定、可验收

## 9. 设计决策

1. 推理库采用 C++ + CMake。
2. 运行底座采用 C++ HTTP + C++ Runtime + 插件模式，具备 License 双层校验能力。
3. 一能力一插件，公共 runtime 作为共享层。
4. 统一标准 C ABI 与头文件模板。
5. ai-builder 既负责构建插件，也负责输出客户最终可交付包。

## 10. 整改设计与跟踪

### 10.1 当前整改重点

1. 将构建主链路从模板化 / 占位产物切换为真实插件源码、真实模型包、真实授权记录驱动。
2. 建立模型包、插件、授权、delivery_package 之间的来源追溯关系与校验链路。
3. 在交付前增加可装载性校验，确保输出产物可被 ai-prod 真正装载执行。

### 10.2 与其他模块的关键契约

1. 从 ai-train 获取真实模型包、manifest、labels、preprocess、validation 产物。
2. 从 ai-license-mgr 获取真实授权记录、稳定校验工具与诊断语义。
3. 输出给 ai-prod / ai-sdk 的动态库、manifest、license、docs 必须来自同一真实交付链。

### 10.3 对应整改编号

1. RB-01
2. RB-02
3. RB-03
