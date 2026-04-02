# ai-prod frontend

ai-prod 前端管理台与内置测试页，基于 React + TypeScript + Vite 初始化，用于承载能力列表、license 状态、runtime revision 与在线推理验证。

## 当前页面内容

1. 公司信息与版本信息展示
2. 能力列表、license 状态、revision 与操作记录查询
3. reload / rollback 管理操作入口
4. 内置在线推理测试页面

## 本地运行

```bash
cd /home/runner/work/ai_capability_platform/ai_capability_platform/apps/ai-prod/frontend
npm install
npm run dev -- --host 0.0.0.0 --port 26014
```

## 构建校验

```bash
cd /home/runner/work/ai_capability_platform/ai_capability_platform/apps/ai-prod/frontend
npm run build
npm run lint
```

默认使用同源 `/api/v1/*` 接口，也可通过 `VITE_API_BASE_URL` 指定后端地址。
