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

> 以下所有命令均在**仓库根目录**（即 `ai_capability_platform/` 所在目录）下执行。

```bash
bash scripts/docker/init_host_root.sh
```

如需自定义宿主机目录，可提前设置：

```bash
export AI_CAP_HOST_ROOT=/data/ai_capability_platform
```

## 3. 启动方式

```bash
docker compose up --build
```

如构建阶段下载 Python 依赖较慢，可在启动前覆盖 pip 构建参数：

```bash
export PIP_DEFAULT_TIMEOUT=300
export PIP_RETRIES=10
# 如需使用内网/就近镜像，可额外设置
# export PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple
# 如需经代理访问外网资源（例如 PyPI / GitHub）
# export HTTP_PROXY=http://127.0.0.1:7890
# export HTTPS_PROXY=http://127.0.0.1:7890
# export NO_PROXY=127.0.0.1,localhost
docker compose up --build
```

说明：

1. 各后端镜像已优先缓存系统依赖和固定 Python 依赖，源码改动不会触发整层重装
2. `ai-test` 中体积较大的 `onnxruntime` 已单独分层，便于重复构建复用缓存
3. 若显式设置了 `PIP_INDEX_URL`、`HTTP_PROXY`、`HTTPS_PROXY`、`NO_PROXY`，compose 构建阶段会自动传递给各镜像

## 4. 健康检查

```bash
bash scripts/docker/health_check.sh
```

## 5. 端口规划

1. ai-train：26000（Web 标注 / 训练 / 模型管理页面）
2. ai-test：26001（Web 测试 / 报告 / 生产镜像验收页面）
3. ai-license-mgr：26002（Web 授权页面）
4. ai-builder：26003（Web 构建页面）
5. ai-prod：26004（C++ HTTP 对外主入口）
6. ai-sdk：26005

Web 页面入口速查：

1. `http://127.0.0.1:26000/`：标注、训练、模型管理
2. `http://127.0.0.1:26001/`：测试、报告、生产镜像验收
3. `http://127.0.0.1:26002/`：授权、license 签发 / 校验
4. `http://127.0.0.1:26003/`：推理库构建、delivery_package 下载

## 6. 联调说明

1. ai-test 通过 `AI_TRAIN_API_BASE_URL` 指向 ai-train
2. ai-builder 通过 `AI_TRAIN_API_BASE_URL`、`AI_LICENSE_MGR_API_BASE_URL` 访问上游服务
3. ai-prod 与 ai-sdk 直接消费宿主机 `models/`、`libs/`、`license/` 等目录
4. ai-prod 容器内已切换为双进程：C++ HTTP 对外监听 `26004`，Python backend 仅在容器内监听 `26014`
5. 当前根目录 `docker-compose.yml` 仍主要用于六模块联调；如需执行 ai-prod 面向客户交付的独立验收与压测，请额外参考 `docs/07_部署运维/ai-prod运行规范.md`
