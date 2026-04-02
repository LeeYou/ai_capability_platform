# ai-builder frontend

ai-builder 前端管理台骨架，基于 React + TypeScript + Vite 初始化，用于承载构建台、平台矩阵与产物台。

## 当前页面内容

1. 公司信息与版本信息展示
2. 平台矩阵、能力目录、授权记录、构建任务、构建目标与产物列表展示
3. 推理库交付说明与后续增强方向提示

## 本地运行

```bash
cd /home/runner/work/ai_capability_platform/ai_capability_platform/apps/ai-builder/frontend
npm install
npm run dev -- --host 0.0.0.0 --port 26013
```

## 构建校验

```bash
cd /home/runner/work/ai_capability_platform/ai_capability_platform/apps/ai-builder/frontend
npm run build
npm run lint
```

默认使用同源 `/api/v1/*` 接口，也可通过 `VITE_API_BASE_URL` 指定后端地址。
