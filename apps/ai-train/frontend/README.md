# ai-train frontend

ai-train 前端管理台，基于 React + TypeScript + Vite，用于承载标注台、训练台和模型管理台。

## 当前页面内容

1. 公司信息与版本信息展示
2. ai-train 当前后端能力概览
3. 实时查询能力、标注任务、训练任务、模型产物列表
4. 标注样本级保存 / 提交
5. 训练任务 prepare / execute / 结果摘要写回
6. 模型产物详情查看

## Web 访问入口

1. docker compose 联调入口：`http://127.0.0.1:26000/`
2. 页面职责：标注、训练、模型管理
3. 同源接口：`/api/v1/*`

## 本地运行（前端开发模式）

```bash
cd /home/runner/work/ai_capability_platform/ai_capability_platform/apps/ai-train/frontend
npm install
npm run dev -- --host 0.0.0.0 --port 26010
```

## 构建校验

```bash
cd /home/runner/work/ai_capability_platform/ai_capability_platform/apps/ai-train/frontend
npm run build
npm run lint
```

默认使用同源 `/api/v1/*` 接口，也可通过 `VITE_API_BASE_URL` 指定后端地址。
