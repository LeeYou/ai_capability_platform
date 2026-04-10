# ai-builder frontend

ai-builder 前端管理台，基于 React + TypeScript + Vite，用于承载构建台、平台矩阵与产物台。

## 当前页面内容

1. 公司信息与版本信息展示
2. 平台矩阵、能力目录、授权记录、构建任务、构建目标与产物列表展示
3. 构建任务创建入口
4. delivery_package、构建目标与交付产物下载入口
5. 作为“推理库 / 生产镜像构建”页面入口使用

## Web 访问入口

1. docker compose 联调入口：`http://127.0.0.1:26003/`
2. 页面职责：推理库构建、交付包下载、生产镜像构建上下文查看
3. 同源接口：`/api/v1/*`

## 本地运行（前端开发模式）

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
