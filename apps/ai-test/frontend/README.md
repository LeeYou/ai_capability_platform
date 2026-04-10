# ai-test frontend

ai-test 前端管理台，基于 React + TypeScript + Vite，用于承载测试工作台、镜像验收页面与报告中心。

## 当前页面内容

1. 公司信息与版本信息展示
2. ai-train 远端模型目录实时查询
3. 测试任务、验收任务、性能基线与测试报告列表展示
4. 生产镜像验收任务结果查看
5. 作为“生产测试 / 验收”页面入口使用

## Web 访问入口

1. docker compose 联调入口：`http://127.0.0.1:26001/`
2. 页面职责：测试、报告、生产镜像验收
3. 同源接口：`/api/v1/*`

## 本地运行（前端开发模式）

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
