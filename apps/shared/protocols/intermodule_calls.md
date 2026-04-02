# 跨模块调用协议

## 1. 标准链路

1. `ai-train` 生成模型包与 `manifest.json`
2. `ai-test` 拉取 `ai-train` 模型目录快照并产出测试报告
3. `ai-license-mgr` 生成 `license.bin` 与 `pubkey.pem`
4. `ai-builder` 读取模型与 license，输出 `libs/<target>/<capability>/`
5. `ai-prod` 装载 `models/`、`libs/`、`license/` 并执行统一推理 API
6. `ai-sdk` 基于 `ai-builder` 输出整理单机交付目录与 SDK 资料

## 2. 共享宿主机目录

根目录固定为 `/data/ai_capability_platform/`：

1. `data/`
2. `datasets/`
3. `models/`
4. `license/`
5. `libs/`
6. `configs/`
7. `logs/`
8. `exports/`

## 3. 联调验收重点

1. manifest / checksum / license 三者兼容
2. GPU 优先、CPU 自动回退
3. 审计日志与导出产物可追溯
