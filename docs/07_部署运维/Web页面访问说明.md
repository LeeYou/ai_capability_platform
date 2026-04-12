# Web 页面访问说明

## 1. 目标

明确联调环境下各个业务流程应该打开哪个 Web 页面，避免出现“服务起来了但不知道去哪一个页面操作”的问题。

## 2. 启动方式

```bash
cd /home/runner/work/ai_capability_platform/ai_capability_platform
bash scripts/docker/init_host_root.sh
docker compose up --build
```

## 3. 页面访问总览

| 流程阶段 | 页面入口 | 模块 | 页面职责 |
| --- | --- | --- | --- |
| 标注 | `http://127.0.0.1:26000/` | ai-train | 标注任务列表、样本级编辑、保存、提交 |
| 训练 | `http://127.0.0.1:26000/` | ai-train | 训练任务 prepare / execute、日志与结果摘要查看 |
| 模型管理 | `http://127.0.0.1:26000/` | ai-train | 模型产物列表、manifest / runtime contract 查看 |
| 测试 | `http://127.0.0.1:26001/` | ai-test | 测试任务、测试报告、性能基线、验收任务查看 |
| 生产镜像测试 | `http://127.0.0.1:26001/` | ai-test | 面向 ai-prod 的验收任务与报告查看 |
| 授权 | `http://127.0.0.1:26002/` | ai-license-mgr | 客户、密钥、策略、签发、校验、tool release |
| 推理库构建 | `http://127.0.0.1:26003/` | ai-builder | 构建任务创建、交付目标、产物下载 |
| 生产镜像构建上下文 | `http://127.0.0.1:26003/` | ai-builder | delivery_package、docs、tools、镜像上下文归档 |

## 4. 推荐操作顺序

1. 先在 `ai-train` 页面完成标注与训练，确认模型产物已生成。
2. 再在 `ai-test` 页面查看模型目录、执行测试与验收任务。
3. 在 `ai-license-mgr` 页面创建客户、密钥、授权策略并签发 license。
4. 在 `ai-builder` 页面选择模型与授权记录，发起推理库构建与交付打包。
5. 构建完成后，回到 `ai-test` 页面执行生产镜像验收与报告查看。

## 5. ai-prod 说明

1. `ai-prod` 的公开运行入口仍是 `http://127.0.0.1:26004/api/v1/*`。
2. 当前联调阶段面向“生产测试”的主 Web 页面在 `ai-test`，不是 `ai-prod`。
3. `ai-prod` 前端控制台仍用于内部研发 / QA 调试，如需单独打开，请运行：

```bash
cd /home/runner/work/ai_capability_platform/ai_capability_platform/apps/ai-prod/frontend
npm install
npm run dev -- --host 0.0.0.0 --port 26014
```

## 6. 常见判断方式

1. 如果你要做“标注、训练、模型查看”，打开 `26000`。
2. 如果你要做“测试、报告、生产镜像验收”，打开 `26001`。
3. 如果你要做“客户、密钥、授权策略、license 签发”，打开 `26002`。
4. 如果你要做“推理库构建、交付物下载、镜像构建上下文打包”，打开 `26003`。
