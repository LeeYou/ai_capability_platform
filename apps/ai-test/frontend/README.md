# ai-test frontend

ai-test 前端管理台骨架，基于 React + TypeScript + Vite 初始化，用于承载单测页面、批测页面与报告中心。

## 当前页面内容

1. 公司信息与版本信息展示
2. ai-train 远端模型目录实时查询
3. 测试任务与测试报告列表展示
4. 后续建设方向提示

## 本地运行

```bash
cd /home/runner/work/ai_capability_platform/ai_capability_platform/apps/ai-test/frontend
npm install
npm run dev -- --host 0.0.0.0 --port 26011
```

## 构建校验

```bash
cd /home/runner/work/ai_capability_platform/ai_capability_platform/apps/ai-test/frontend
npm run build
npm run lint
```

默认使用同源 `/api/v1/*` 接口，也可通过 `VITE_API_BASE_URL` 指定后端地址。
