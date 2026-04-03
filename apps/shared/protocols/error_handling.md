# 错误处理协议

## 1. 统一要求

1. 平台内错误码按模块分段管理
2. 错误消息统一中文表达
3. 共享错误码目录以 `apps/shared/schemas/error_codes.json` 为准

## 2. 分层要求

1. 参数校验错误优先在 API 层拦截
2. 目录、文件、schema 不兼容错误优先在服务层校验
3. 构建、打包、验签、装载失败必须落审计日志

## 3. P8 联调要求

1. ai-train 输出的模型 manifest 必须可被 ai-test、ai-builder、ai-prod、ai-sdk 消费
2. ai-license-mgr 签发的 license 必须可被 ai-builder、ai-prod、ai-sdk 复用
3. ai-builder 输出的构建 manifest 必须可被 ai-sdk 与 ai-prod 追溯
