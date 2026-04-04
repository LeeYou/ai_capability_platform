# ai-license-mgr backend

ai-license-mgr 后端首期工程，提供客户、密钥对、授权策略、license 签发、校验、导出与审计日志能力，并与 ai-prod 运行态保持一致的版本约束判定语义。

## 当前能力

1. 健康检查接口
2. 客户管理、密钥对管理、授权策略管理接口
3. 硬件指纹生成接口
4. license 签发、查询、校验接口
5. `license.bin` / `pubkey.pem` 导出接口
6. 审计日志查询接口
7. 与 ai-prod 对齐的 `allowed_versions` / `prefix` / `min_version` / `max_version` 版本约束语义

## 本地运行

```bash
cd /home/runner/work/ai_capability_platform/ai_capability_platform/apps/ai-license-mgr/backend
python -m uvicorn app.main:app --host 0.0.0.0 --port 26002
```

默认宿主机根目录为 `/data/ai_capability_platform`，可通过环境变量 `AI_CAP_HOST_ROOT` 覆盖。

SQLite 数据库默认位于 `${AI_CAP_HOST_ROOT}/data/ai_license_mgr.db`。

## 校验命令

```bash
cd /home/runner/work/ai_capability_platform/ai_capability_platform/apps/ai-license-mgr/backend
PYTHONPATH=. python -m unittest discover -s tests -v
```
