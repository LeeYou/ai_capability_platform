# ai-license-mgr frontend

ai-license-mgr 前端管理台骨架，基于 React + TypeScript + Vite 初始化，用于承载客户台、密钥台与授权台。

## 当前页面内容

1. 公司信息与版本信息展示
2. 客户、密钥对、授权策略、签发记录、审计日志列表展示
3. 授权能力说明与后续建设方向提示

## 本地运行

```bash
cd /home/runner/work/ai_capability_platform/ai_capability_platform/apps/ai-license-mgr/frontend
npm install
npm run dev -- --host 0.0.0.0 --port 26012
```

## 构建校验

```bash
cd /home/runner/work/ai_capability_platform/ai_capability_platform/apps/ai-license-mgr/frontend
npm run build
npm run lint
```

默认使用同源 `/api/v1/*` 接口，也可通过 `VITE_API_BASE_URL` 指定后端地址。
