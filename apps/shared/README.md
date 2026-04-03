# apps/shared

平台级共享协议、schema、示例与联调校验资产。

## 目录说明

1. `schemas/`：统一错误码、manifest、license、API 响应、能力元数据 schema
2. `protocols/`：跨模块调用、错误处理与 API 响应约定
3. `examples/`：与 schema 对齐的示例文件
4. `tests/`：共享资产解析与示例一致性校验

## 校验命令

```bash
cd /home/runner/work/ai_capability_platform/ai_capability_platform
python -m unittest discover -s apps/shared/tests -v
```
