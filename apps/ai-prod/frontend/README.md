# ai-prod frontend

ai-prod 前端为 **内部测试 / 验收外壳**，基于 React + TypeScript + Vite 初始化，用于承载能力列表、license 状态、runtime revision 与在线推理验证；不作为客户生产调用主链路。

## 当前页面内容

1. 公司信息与版本信息展示
2. 能力列表、license 状态、revision 与操作记录查询
3. reload / rollback 管理操作入口
4. 内置在线推理测试页面

## 内外边界

1. 生产主链路由 C++ HTTP 服务承载，对外暴露 `/api/v1/*`
2. 本前端通过 `/internal/*` 查询内部 revision / operation / audit 等验收信息
3. 本前端仅供研发、QA、交付联调阶段使用

## 本地运行

```bash
cd /home/runner/work/ai_capability_platform/ai_capability_platform/apps/ai-prod/frontend
npm install
npm run dev -- --host 0.0.0.0 --port 26014
```

开发模式默认将 `/api/v1/*` 与 `/internal/*` 代理到 `http://127.0.0.1:26004`，可通过 `VITE_DEV_BACKEND_ORIGIN` 覆盖。

## 构建校验

```bash
cd /home/runner/work/ai_capability_platform/ai_capability_platform/apps/ai-prod/frontend
npm run build
npm run lint
```

默认使用同源接口；运行时 API 走 `/api/v1/*`，内部验收查询走 `/internal/*`。如需显式指定后端地址，可通过 `VITE_API_BASE_URL` 覆盖。
