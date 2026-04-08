# ai_platform 对比评估报告

> **历史评估说明**：本报告撰写于平台早期融合阶段（R1 之前），描述的是当时 ai-prod 以 Python 实现为主的状态。**当前平台已全面完成 C++ HTTP + C++ Runtime 生产主链路落地（R2–R14），ai-prod 已具备完整的插件装载、license 双层校验、热更新/回滚、manifest 强契约校验与 capability 接入门禁能力。** 本报告保留作为架构演进决策的历史依据，如需了解最新实现状态请参见总体开发计划与各模块开发计划。

## 1. 评估范围与依据

本报告对比当前仓库的 `ai_capability_platform` 与子目录 `ai_platform`，重点覆盖总体架构、技术选型、部署交付、共享基础能力，以及训练、测试、授权、构建、生产运行、Web/UI、样本标注等模块设计与实现现状。

评估依据分为两类：

1. **设计文档依据**
   - `docs/01_产品设计/产品设计文档.md`
   - `docs/02_总体架构/总体架构设计文档.md`
   - `docs/03_模块设计/*.md`
   - `docs/04_规范与选型/技术选型与工程规范.md`
   - `ai_platform/docs/design/00_目录.md`
   - `ai_platform/docs/design/03_系统架构设计.md`
   - `ai_platform/docs/design/05_CPP推理插件SO设计.md`
   - `ai_platform/docs/design/06_Runtime运行时设计.md`
   - `ai_platform/docs/design/07_HTTP服务层设计.md`
   - `ai_platform/docs/design/09_授权与License设计.md`
   - `ai_platform/docs/design/10_更新与回滚机制.md`

2. **实现代码依据**
   - `apps/ai-train/backend/README.md`
   - `apps/ai-test/backend/README.md`
   - `apps/ai-license-mgr/backend/README.md`
   - `apps/ai-builder/backend/README.md`
   - `apps/ai-prod/backend/README.md`
   - `apps/ai-prod/backend/app/services/runtime_service.py`
   - `apps/ai-prod/backend/app/db/models.py`
   - `apps/shared/README.md`
   - `ai_platform/README.md`
   - `ai_platform/src/runtime/`
   - `ai_platform/src/server/`
   - `ai_platform/src/license/`
   - `docker-compose.yml`

## 2. 总体结论

### 2.1 结论摘要

`ai_capability_platform` 的优势在于**生命周期覆盖更完整、管理面更完整、跨模块元数据体系更完整**；`ai_platform` 的优势在于**交付运行面更聚焦、更成熟、更接近工业级运行内核**。

换句话说：

1. **如果目标是建设“研发到交付”的平台体系**，当前 `ai_capability_platform` 的方向更完整。
2. **如果目标是建设“现场可交付、可热更新、可多形态输出”的运行底座**，`ai_platform` 的设计更成熟。
3. 最优路线不是二选一，而是：**保留当前平台的训练/测试/授权/构建管理体系，吸收 `ai_platform` 在 Runtime、HTTP 服务、交付形态、更新回滚、License 落地细节方面的设计。**

### 2.2 一句话评价

| 维度 | 结论 |
|---|---|
| 生命周期完整性 | `ai_capability_platform` 更强 |
| 运行时成熟度 | `ai_platform` 更强 |
| 管理后台与业务闭环 | `ai_capability_platform` 更强 |
| 交付形态与现场部署设计 | `ai_platform` 更强 |
| 元数据与跨系统协作 | `ai_capability_platform` 更强 |
| 热更新、回滚、插件运行细节 | `ai_platform` 更强 |

## 3. 总体架构对比

### 3.1 平台定位

| 项 | ai_capability_platform | ai_platform |
|---|---|---|
| 定位 | 工业级 AI 通用能力全生命周期平台 | 面向交付的 AI 能力运行平台 MVP |
| 目标 | 覆盖标注、训练、测试、授权、构建、交付、生产运行 | 聚焦 Runtime、HTTP 服务、插件、License、热更新 |
| 适用阶段 | 内部研发生产线 + 对外交付 | 对外交付运行底座 |

**评估：**

1. 当前平台在产品边界上更大，适合作为“平台主工程”。
2. `ai_platform` 边界更清晰，几乎只围绕交付运行展开，因此在运行面设计上更深入。

### 3.2 架构分层

`ai_capability_platform` 在 `docs/02_总体架构/总体架构设计文档.md` 中定义了“门户与管理层 / 业务服务层 / 共享基础层 / 交付运行层 / 基础设施层”的五层体系；`ai_platform` 在 `ai_platform/docs/design/03_系统架构设计.md` 中定义了“HTTP 服务层 / Runtime 层 / 插件层 / 模型包层”的四层体系。

| 对比项 | ai_capability_platform | ai_platform | 评估 |
|---|---|---|---|
| 顶层管理层 | 有 | 无 | 当前平台更强 |
| 业务服务分层 | 明确拆成 train/test/license/builder/prod | 无独立业务服务拆分 | 当前平台更强 |
| 运行时内核分层 | 有概念设计 | 有非常具体的分层与数据流 | `ai_platform` 更强 |
| 插件与模型边界 | 已定义 | 已细化到接口、数据流、装载流程 | `ai_platform` 更强 |

### 3.3 技术选型

| 项 | ai_capability_platform | ai_platform | 评估 |
|---|---|---|---|
| 管理后端 | Python 3.11 + FastAPI | 无 | 当前平台更强 |
| 管理前端 | React + TypeScript + Vite | 无 | 当前平台更强 |
| 训练/测试 | Python + PyTorch/ONNX Runtime | 无 | 当前平台更强 |
| 生产 HTTP | FastAPI | cpp-httplib | `ai_platform` 更偏高性能运行面 |
| Runtime | 设计上为 C++ 动态库 | 实现上为 C++ Runtime | `ai_platform` 更成熟 |
| 构建体系 | CMake + Python 编排 | CMake 为主 | 各有侧重 |

**关键判断：**

当前平台的技术选型更适合快速建设管理系统；`ai_platform` 的技术选型更适合把运行面做成“可交付底座”。两者并不冲突，但当前平台在 `ai-prod` 上的运行面深度明显弱于 `ai_platform`。

### 3.4 部署与交付

| 项 | ai_capability_platform | ai_platform |
|---|---|---|
| 部署方式 | 多服务 Docker Compose | 单运行平台镜像 + 宿主机覆盖目录 |
| 交付形态 | Docker + SDK/JNI 设计 | Docker + Linux SO + JNI + Windows DLL 明确设计 |
| 宿主机目录 | `/data/ai_capability_platform/` 全链路目录 | `/opt/ai_platform/` 运行交付目录 |
| 资源加载策略 | 镜像内置基线 + 宿主机挂载优先 | 同策略，但交付细节更完整 |

**评估：**

1. 当前平台的部署体系更适合内部研发协同。
2. `ai_platform` 的交付体系更适合客户现场落地。
3. 当前平台缺少一套像 `ai_platform/docs/deploy/`、`ai_platform/docs/acceptance/` 那样细颗粒度的运行交付说明与验收体系。

## 4. 模块逐项对比评估

### 4.1 样本标注与数据管理

| 项 | ai_capability_platform | ai_platform | 评估结论 |
|---|---|---|---|
| 模块归属 | `ai-train` | 无 | 当前平台明显领先 |
| 设计深度 | 有数据集绑定、标注任务、结果提交 | 未覆盖 | 当前平台是补足全生命周期的关键模块 |
| 实现印证 | `apps/ai-train/backend/README.md` 已有标注 API 与数据集扫描 | 无 | 当前平台优势明确 |

**结论：**

这是当前平台相对 `ai_platform` 最明确的优势之一。`ai_platform` 在这一块基本空白，用户提到其“Web 页面和标记样本页面部分设计不全面”，从仓库内容看这一判断成立。

### 4.2 训练模块

| 项 | ai_capability_platform | ai_platform | 评估结论 |
|---|---|---|---|
| 模块 | `ai-train` | 无 | 当前平台领先 |
| 目标 | 训练任务、模型产物、能力元数据 | 未覆盖 | 当前平台补齐研发链路 |
| 技术栈 | Python + PyTorch | 无 | 当前平台更完整 |

**优势：**

1. 将训练纳入统一平台，而不是散落在脚本体系中。
2. 模型可追溯到训练任务、数据集与能力元数据。

**不足：**

1. 当前仍偏“训练工程骨架”，距离成熟训练平台还有差距。
2. 与 `ai_platform` 的模型包、交付目录、插件接口之间，还缺少更强的一体化约束文档。

### 4.3 测试模块

| 项 | ai_capability_platform | ai_platform | 评估结论 |
|---|---|---|---|
| 模块 | `ai-test` | 无独立测试平台 | 当前平台领先 |
| 目标 | 单接口测试、批量测试、报告生成 | 仅提供最小 smoke 与测试页 | 当前平台更像正式测试子系统 |
| 实现印证 | `apps/ai-test/backend/README.md`、测试报告输出设计 | `ai_platform` 以回归脚本为主 | 当前平台更完整 |

**结论：**

当前平台的 `ai-test` 是面向内部质量流程的正式模块；`ai_platform` 的测试设计更偏“运行平台自验证”，不构成替代关系。

### 4.4 授权模块

| 项 | ai_capability_platform | ai_platform | 评估结论 |
|---|---|---|---|
| 模块形态 | `ai-license-mgr` 独立子系统 | Runtime 内 License 管理 | 两者应融合 |
| 优势 | 客户、密钥、策略、签发流程管理更强 | 授权校验落地、运行期约束更强 | 当前平台强管理，`ai_platform` 强执行 |
| 实现侧证据 | `apps/ai-license-mgr/backend/README.md` | `ai_platform/src/license/`、`09_授权与License设计.md` | `ai_platform` 细节更成熟 |

**结论：**

1. 当前平台在“授权签发管理”上更强。
2. `ai_platform` 在“授权文件运行期校验、受限模式、自动重载、硬件绑定”等落地机制上更强。
3. 最佳方案应是：**签发侧保留 `ai-license-mgr`，运行侧复用 `ai_platform` 的 License 校验设计。**

### 4.5 构建与交付模块

| 项 | ai_capability_platform | ai_platform | 评估结论 |
|---|---|---|---|
| 模块 | `ai-builder` + `ai-sdk` | 脚本化交付整理 + 交付模板 | 当前平台更平台化，`ai_platform` 更贴近交付细节 |
| 目标 | 构建任务、日志、产物组织、多平台模板 | 交付目录、registry 校验、主机模板、验收 | 两边各有长处 |
| 多平台表达 | 文档和模块职责已覆盖 | 文档非常清晰，运行交付边界更清楚 | `ai_platform` 文档更成熟 |

**结论：**

1. 当前平台更适合做“交付构建中心”。
2. `ai_platform` 更适合提供“标准交付模板、交付目录、验收清单、现场运行约束”。
3. 当前平台短板不在是否有 builder，而在**builder 的交付标准化细节文档不如 `ai_platform` 完整**。

### 4.6 生产运行模块

| 项 | ai_capability_platform | ai_platform | 评估结论 |
|---|---|---|---|
| 模块 | `ai-prod` | `ai_platform_server` + Runtime | `ai_platform` 明显更成熟 |
| 设计目标 | FastAPI + C++ Runtime | C++ HTTP + C++ Runtime + 插件 | `ai_platform` 更统一 |
| 实现现状 | Python 服务已具备 revision、reload、scan、license 检查等逻辑 | C++ runtime/server/license 目录齐备 | `ai_platform` 更接近真实工业运行底座 |

**关键实现发现：**

1. `apps/ai-prod/backend/app/services/runtime_service.py` 已实现资源扫描、实例池、revision、reload/rollback、license 校验、日志与审计。
2. 但当前实现是 **Python 内部模拟运行时**，并未体现出 `dlopen/dlsym` 或 Python 到 C++ Runtime 的实际桥接。
3. `ai_platform/src/runtime/` 已有 `plugin_manager`、`pool_manager`、`reload_controller`、`capability_pool` 等明确运行时组件，成熟度更高。

**结论：**

生产运行面是当前平台相对 `ai_platform` 的主要短板，尤其体现在：

1. Runtime 还没有真正落到独立 C++ 内核。
2. 并发、实例池、插件生命周期控制仍更多停留在 Python 业务层实现。
3. 对“高并发 + 热更新 + 插件 SO 生命周期”这类工业运行关键场景，`ai_platform` 的设计可信度更高。

### 4.7 Runtime / 插件体系

| 项 | ai_capability_platform | ai_platform | 评估结论 |
|---|---|---|---|
| 标准 C ABI | 设计中明确 | 文档与头文件更完整 | `ai_platform` 更强 |
| 插件生命周期 | 设计有原则 | 文档/源码已细化 | `ai_platform` 更强 |
| 模型装载与实例池 | 当前实现有抽象 | 文档与源码均更成熟 | `ai_platform` 更强 |
| 多外壳适配 | 设计有 SDK/JNI | 明确“统一 Runtime / Plugin Core + 多外壳” | `ai_platform` 更强 |

**结论：**

`ai_platform` 在这一层基本可以视为当前平台的“运行内核参考实现”。当前平台的总体架构方向正确，但底层运行时设计深度还不够。

### 4.8 Web / UI

| 项 | ai_capability_platform | ai_platform | 评估结论 |
|---|---|---|---|
| 管理后台 | 各子系统独立 React 前端 | 无 | 当前平台明显更强 |
| 测试页面 | `ai-test`、`ai-prod` 前端 | 内置轻量测试页 | 当前平台更完整 |
| 用户体验 | 管理流程化 | 仅验证运行主链路 | 当前平台更适合正式平台产品 |

**结论：**

这也是当前平台的明显优势。`ai_platform` 的 Web 部分主要服务于运行验证，而不是服务于平台管理。

### 4.9 共享基础能力

| 项 | ai_capability_platform | ai_platform | 评估结论 |
|---|---|---|---|
| 共享层 | `apps/shared` | 头文件 + registry + config | 当前平台更强 |
| 作用 | 统一 schema、协议、示例、测试 | 面向运行时的接口与配置基线 | 当前平台更适合跨模块协作 |
| 校验机制 | 有共享 schema 测试 | 有 registry 校验脚本 | 各有价值 |

**结论：**

当前平台在“跨系统共享元数据”上明显更先进；`ai_platform` 更偏运行时工程约束。前者适合平台协同，后者适合交付落地。

## 5. 当前 ai_capability_platform 的优势

### 5.1 生命周期闭环更完整

覆盖数据、标注、训练、测试、授权、构建、交付、运行，能够形成一套完整的内部生产线，而不是单一运行容器。

### 5.2 管理面更成熟

各子系统均有明确职责、独立服务和前端入口，更适合团队分工和业务流程固化。

### 5.3 元数据与协议治理更好

`apps/shared` 让平台具备统一 schema、协议、示例、测试基础，这对后续新增 AI 能力、跨模块对接、长期维护非常关键。

### 5.4 平台拆分更利于演进

训练、测试、授权、构建、生产运行分别演进，便于团队按角色协作，也便于后续替换具体实现。

### 5.5 更适合做“上层平台”

如果公司需要一套真正的“AI 能力生产平台”，当前平台架构更符合长期产品化路线。

## 6. 当前 ai_capability_platform 的劣势

### 6.1 运行时内核不够扎实

`ai-prod` 当前已有不少运行管理逻辑，但核心仍主要在 Python 中实现；相比 `ai_platform` 的 C++ Runtime，工业化程度不足。

### 6.2 交付形态落地细节不如 ai_platform

当前平台已经定义 Docker、SDK、JNI、多平台支持，但交付模板、部署模板、验收清单、运行目录约束还不够细。

### 6.3 热更新/回滚机制的运行时可信度偏弱

文档层面已经有设计，Python 层面也有 revision 与 rollback 记录，但和真正 SO 生命周期管理、实例池 drain、原子替换相比还有明显差距。

### 6.4 授权运行态设计不如 ai_platform 细

当前平台更强在签发与管理，`ai_platform` 更强在现场运行约束、受限模式、自动重载、宿主机覆盖路径等落地规则。

### 6.5 生产 HTTP 层与 Runtime 层耦合策略还需明确

当前平台设计上是 “FastAPI + C++ Runtime”，但从现有代码看，桥接路径和边界还没有真正固化为工程事实。

## 7. 建议吸收 ai_platform 的重点能力

### 7.1 P0：把 ai_platform 作为运行内核参考

建议重点吸收以下内容：

1. `ai_platform/src/runtime/` 的 Runtime 组件划分。
2. `ai_platform/docs/design/06_Runtime运行时设计.md` 的实例池、调度、reload/rollback 思路。
3. `ai_platform/docs/design/05_CPP推理插件SO设计.md` 的 C ABI 和多交付壳层设计。

### 7.2 P0：重构 ai-prod 的运行边界

建议把 `ai-prod` 明确拆成：

1. Python/FastAPI 管理与 API 适配层；
2. 独立 C++ Runtime 内核；
3. 标准插件加载与模型包装载层。

如果后续压测显示 Python HTTP 层成为瓶颈，再进一步评估是否直接复用 `ai_platform` 的 C++ HTTP 服务。

### 7.3 P1：补齐交付与验收文档

建议参考以下内容完善当前平台文档：

1. `ai_platform/docs/deploy/platform_delivery_mvp.md`
2. `ai_platform/docs/acceptance/platform_acceptance_checklist.md`
3. `ai_platform/deploy/host_template/README.md`

重点补齐：

1. 交付目录模板
2. 现场部署步骤
3. 运行校验脚本
4. 验收证据清单

### 7.4 P1：统一 License 生产侧协议

建议保留 `ai-license-mgr` 负责签发管理，但让运行侧完全对齐 `ai_platform` 的 License 校验模型，避免“签发端一套、运行端一套”。

### 7.5 P1：把多交付形态做成 builder 的标准产物

建议把 `ai_platform` 的“统一 Runtime / 多外壳交付”思想纳入 `ai-builder`，让 `ai-builder` 真正成为：

1. Docker 平台交付产物生成器；
2. Linux SO SDK 产物生成器；
3. JNI 产物生成器；
4. Windows DLL 产物生成器。

## 8. 推荐融合架构

### 8.1 建议分工

| 层 | 推荐归属 |
|---|---|
| 数据、标注、训练、测试、授权管理、构建编排 | 保留在 `ai_capability_platform` |
| 生产 Runtime、插件内核、SO 生命周期、实例池、热更新、回滚 | 参考并吸收 `ai_platform` |
| 共享 schema、manifest、license 协议 | 由当前平台统一治理 |
| Docker/SDK/JNI/DLL 交付模板 | 以 `ai-builder` 为出口，吸收 `ai_platform` 模板 |

### 8.2 推荐判断

**推荐方向：以当前平台为主平台，以 `ai_platform` 为运行内核与交付规范参考实现。**

原因是：

1. 当前平台承担的是更大的产品边界，不能回退成单纯运行平台。
2. `ai_platform` 的真正价值，不在替代 train/test/license/builder，而在补强 prod/runtime/delivery。

## 9. 最终评估结论

### 9.1 当前平台相对 ai_platform 的核心优势

1. 平台边界更完整
2. 研发流程更完整
3. 管理面更完整
4. 元数据治理更完整
5. 更适合长期产品化和团队协作

### 9.2 当前平台相对 ai_platform 的核心短板

1. 运行时内核成熟度不足
2. 生产交付规范细节不足
3. Runtime 与 HTTP 的边界未完全工程化
4. 多交付形态虽已设计，但运行面复用内核还不够清晰

### 9.3 最终建议

短期内不建议推翻当前平台设计；应当在保留当前平台总体结构的前提下，优先吸收 `ai_platform` 在以下三方面的成果：

1. **Runtime 内核设计**
2. **交付目录与验收体系**
3. **生产侧 License / 热更新 / 回滚机制**

这样可以形成“**上层平台完整、下层运行扎实**”的组合架构，既保留当前平台的全生命周期优势，也补齐现场交付与工业运行短板。
