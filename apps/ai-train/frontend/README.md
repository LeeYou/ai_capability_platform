# ai-train frontend

ai-train 前端管理台骨架，基于 React + TypeScript + Vite 初始化，用于承载标注台、训练台和模型管理台。

## 当前页面内容

1. 公司信息与版本信息展示
2. ai-train 当前后端能力概览
3. 实时查询能力、标注任务、训练任务、模型产物列表
4. 标注台、训练台、模型台后续建设提示

## 本地运行

```bash
cd /home/runner/work/ai_capability_platform/ai_capability_platform/apps/ai-train/frontend
npm install
npm run dev -- --host 0.0.0.0 --port 26010
```

## 构建校验

```bash
cd /home/runner/work/ai_capability_platform/ai_capability_platform/apps/ai-train/frontend
npm run build
```

后续将继续接入 ai-train 后端接口，逐步建设标注台、训练台与模型管理台的真实交互页面。

默认使用同源 `/api/v1/*` 接口，也可通过 `VITE_API_BASE_URL` 指定后端地址。
