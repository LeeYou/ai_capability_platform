# 单机交付 SDK 模块设计

## 1. 模块目标

建设面向第三方系统集成的单机交付方案，提供 Linux SO、JNI SO、Windows DLL、头文件、模型包、授权文件、授权工具和接入文档，保证与生产运行底座共享同一套 Runtime/ABI 规范。

## 2. 模块职责

1. 标准 C/C++ 调用接口
2. 多平台库文件组织
3. 线程安全并发推理支持
4. JNI 封装支持
5. Windows DLL 集成支持
6. 交付文档、示例工程与授权工具说明输出

## 3. 交付内容

1. `lib/` 或 `dll/`
2. `include/` 头文件
3. `models/` 模型包
4. `licenses/` 授权文件
5. JNI 库与 Java 接口说明
6. `tools/license_tool`
7. `docs/` 接入说明、错误码说明、验收说明

## 4. 接口原则

1. 生命周期统一
2. 错误码统一
3. 内存所有权清晰
4. 线程安全约束明确
5. 与生产 Runtime/插件 ABI 严格兼容

## 5. 平台支持

1. Linux x86_64
2. Linux arm64
3. Windows x86
4. Windows x86_64
5. JNI 封装

## 6. 非功能要求

1. GPU 优先，CPU 回退
2. 并发调用安全
3. 与生产 runtime 协议兼容
4. 交付内容可直接纳入统一 `delivery_package/`

## 7. 设计决策

1. 与 ai-builder 产物共享 ABI 标准。
2. JNI 为可选层，不侵入核心推理库。
3. Windows DLL 与 Linux SO 共享相同插件/Runtime 设计原则。
4. SDK 文档、工具、示例必须作为正式交付物一并输出。
