# ai_capability_platform

ai 通用能力平台，面向工业级 AI 模块全生命周期管理与交付。

## 文档导航

- [文档总览](docs/README.md)
- [产品设计文档](docs/01_产品设计/产品设计文档.md)
- [总体架构设计文档](docs/02_总体架构/总体架构设计文档.md)
- [模块设计文档目录](docs/03_模块设计)
- [规范与技术选型](docs/04_规范与选型/技术选型与工程规范.md)
- [设计审查报告](docs/05_评审/设计审查报告.md)
- [ai_platform 对比评估报告](docs/05_评审/ai_platform对比评估报告.md)
- [开发计划目录](docs/06_开发计划)
- [开发计划审查报告](docs/05_评审/开发计划审查报告.md)
- [部署运维与联调文档](docs/07_部署运维)

## 平台级联调入口

```bash
cd /home/runner/work/ai_capability_platform/ai_capability_platform
bash scripts/docker/init_host_root.sh
docker compose up --build
```

如网络较慢，可先调大 pip 构建超时，必要时切换镜像源：

```bash
export PIP_DEFAULT_TIMEOUT=300
export PIP_RETRIES=10
# 可按需切换为企业内网或就近镜像
# export PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple
docker compose up --build
```

共享 schema 位于 `apps/shared/`，平台级校验命令如下：

```bash
cd /home/runner/work/ai_capability_platform/ai_capability_platform
python -m unittest discover -s apps/shared/tests -v
docker compose config
```

## 公司信息

- 公司名称：北京爱知之星科技股份有限公司（Agile Star）
- 域名：agilestar.cn
