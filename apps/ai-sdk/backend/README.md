# ai-sdk backend

单机交付 SDK 后端首期工程，提供 SDK 目录扫描、Linux/Windows/JNI 标准目录交付包生成、`license_tool`/验收文档/快速校验脚本输出，以及归档导出能力。

## 当前能力

1. 健康检查与 SDK 目录查询接口
2. 固化 SDK ABI 共享头文件、错误码与线程安全说明
3. 基于 ai-builder 产物生成 Linux / Windows / JNI 单机交付包
4. 自动复制模型包、license、头文件、动态库与可选 JNI 产物
5. 自动生成接入说明、错误码说明、部署说明、验收清单、C/C++ 示例与 Java 示例
6. 自动附带 `tools/license_tool` source bundle、`validation/verify_sdk_package.py` 与 package 级 `acceptance_checklist.json`
7. 记录包任务、目标、产物与审计日志

## 本地运行

```bash
cd /home/runner/work/ai_capability_platform/ai_capability_platform/apps/ai-sdk/backend
python -m uvicorn app.main:app --host 0.0.0.0 --port 26005
```

默认宿主机根目录为 `/data/ai_capability_platform`，可通过环境变量 `AI_CAP_HOST_ROOT` 覆盖。

SQLite 数据库默认位于 `${AI_CAP_HOST_ROOT}/data/ai_sdk.db`。

## 校验命令

```bash
cd /home/runner/work/ai_capability_platform/ai_capability_platform/apps/ai-sdk/backend
PYTHONPATH=. python -m unittest discover -s tests -v
```
