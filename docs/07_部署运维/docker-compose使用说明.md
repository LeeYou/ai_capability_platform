# docker-compose 使用说明

## 1. 目标

提供联调阶段统一的六模块启动入口，覆盖：

1. ai-train
2. ai-test
3. ai-license-mgr
4. ai-builder
5. ai-prod
6. ai-sdk

## 2. 初始化宿主机目录

```bash
cd /home/runner/work/ai_capability_platform/ai_capability_platform
bash scripts/docker/init_host_root.sh
```

如需自定义宿主机目录，可提前设置：

```bash
export AI_CAP_HOST_ROOT=/data/ai_capability_platform
```

## 3. 启动方式

```bash
cd /home/runner/work/ai_capability_platform/ai_capability_platform
docker compose up --build
```

## 4. 健康检查

```bash
cd /home/runner/work/ai_capability_platform/ai_capability_platform
bash scripts/docker/health_check.sh
```

## 5. 端口规划

1. ai-train：26000
2. ai-test：26001
3. ai-license-mgr：26002
4. ai-builder：26003
5. ai-prod：26004（C++ HTTP 对外主入口）
6. ai-sdk：26005

## 6. 联调说明

1. ai-test 通过 `AI_TRAIN_API_BASE_URL` 指向 ai-train
2. ai-builder 通过 `AI_TRAIN_API_BASE_URL`、`AI_LICENSE_MGR_API_BASE_URL` 访问上游服务
3. ai-prod 与 ai-sdk 直接消费宿主机 `models/`、`libs/`、`license/` 等目录
4. ai-prod 容器内已切换为双进程：C++ HTTP 对外监听 `26004`，Python backend 仅在容器内监听 `26014`
5. 当前根目录 `docker-compose.yml` 仍主要用于六模块联调；如需执行 ai-prod 面向客户交付的独立验收与压测，请额外参考 `docs/07_部署运维/ai-prod运行规范.md`
