# 09 — 授权与 License 设计

## 9.1 设计目标

1. **离线授权** — 不依赖网络，适用于内网/隔离环境
2. **机器绑定** — 防止 License 文件被复制到其他机器
3. **试用期控制** — 支持限时试用（3 个月、6 个月等）
4. **能力级授权** — 精确控制客户可使用的 AI 能力范围
5. **双层校验** — HTTP 层 + Runtime/插件层双重校验
6. **防篡改** — RSA 数字签名保护，无法伪造或修改
7. **多交付形态兼容** — Docker 平台版、Linux SO、JNI、Windows DLL 均可复用统一授权模型
8. **签发系统内外隔离** — 授权签发能力仅限内部专用服务使用，绝不暴露给客户环境

## 9.2 授权体系架构

```
┌────────────────────────────────────────────────────┐
│                   授权管理体系                       │
│                                                    │
│  ┌──────────────┐    ┌───────────────────────────┐ │
│  │ 授权签发工具  │    │ 客户现场                   │ │
│  │ (内部使用)   │    │                           │ │
│  │              │    │  ┌──────────┐             │ │
│  │ 1.采集指纹   │◄───│  │指纹采集   │             │ │
│  │ 2.生成License│    │  │工具       │             │ │
│  │ 3.RSA签名   │────►│  └──────────┘             │ │
│  │              │    │        ▼                   │ │
│  │  私钥(内部)  │    │  ┌──────────┐             │ │
│  └──────────────┘    │  │license.dat│             │ │
│                      │  └─────┬────┘             │ │
│                      │        ▼                   │ │
│                      │  ┌──────────────────────┐ │ │
│                      │  │  License 验证模块     │ │ │
│                      │  │  (容器内, 公钥验签)   │ │ │
│                      │  │                      │ │ │
│                      │  │  ┌────────────────┐  │ │ │
│                      │  │  │ HTTP 层校验     │  │ │ │
│                      │  │  │ (能力级别检查)   │  │ │ │
│                      │  │  └────────────────┘  │ │ │
│                      │  │          +           │ │ │
│                      │  │  ┌────────────────┐  │ │ │
│                      │  │  │ Runtime 层校验  │  │ │ │
│                      │  │  │ (轻量级检查)    │  │ │ │
│                      │  │  └────────────────┘  │ │ │
│                      │  └──────────────────────┘ │ │
│                      └───────────────────────────┘ │
└────────────────────────────────────────────────────┘
```

## 9.3 License 文件格式

License 文件采用 **JSON + RSA 签名** 格式：

```
┌─────────────────────────┐
│  license.dat 文件结构    │
│                         │
│  [JSON payload]         │  ← Base64 编码的 JSON 授权信息
│  ---SIGNATURE---        │  ← 分隔符
│  [RSA Signature]        │  ← Base64 编码的 RSA-SHA256 签名
└─────────────────────────┘
```

### License JSON Payload

```json
{
    "license_id": "LIC-20260301-001",
    "version": "1.0",
    
    "customer": {
        "id": "CUST-001",
        "name": "某某科技有限公司",
        "contact": "张三"
    },
    
    "license_type": "trial",
    
    "time": {
        "issued_at": "2026-03-01T00:00:00Z",
        "effective_from": "2026-03-01T00:00:00Z",
        "expires_at": "2026-09-01T00:00:00Z",
        "grace_period_hours": 24
    },
    
    "machine": {
        "fingerprint": "sha256:a1b2c3d4e5f6...",
        "bind_components": ["cpu_id", "mac_address", "disk_serial", "board_serial"],
        "allow_vm": false
    },
    
    "capabilities": {
        "allowed": [
            "face_detect",
            "face_recognize",
            "liveness_silent",
            "liveness_action",
            "idcard_detect",
            "doc_classify",
            "general_ocr"
        ],
        "denied": []
    },
    
    "limits": {
        "max_qps": 100,
        "max_daily_calls": -1,
        "max_concurrent": 20
    },
    
    "constraints": {
        "min_platform_version": "1.0.0",
        "max_platform_version": "1.99.99"
    },
    
    "features": {
        "allow_reload": true,
        "allow_admin_api": true,
        "allow_test_page": true
    }
}
```

### License 类型

| 类型 | 标识 | 说明 |
|------|------|------|
| **试用** | `trial` | 限时试用，一般 1-6 个月 |
| **商业** | `commercial` | 正式授权，可长期或按年续费 |
| **开发** | `development` | 开发测试用，功能完整但有水印 |
| **永久** | `perpetual` | 永久授权 (到期时间设为远未来) |

## 9.4 机器指纹方案

### 9.4.1 指纹组成

不依赖单一硬件 ID，组合多个硬件特征：

```cpp
struct MachineInfo {
    std::string cpu_id;           // /proc/cpuinfo 中的 model name + processor count
    std::string mac_address;      // 第一个物理网卡 MAC 地址
    std::string disk_serial;      // 系统盘序列号
    std::string board_serial;     // 主板序列号 (dmidecode)
    std::string hostname;         // 主机名 (可选, 权重低)
};
```

### 9.4.2 指纹计算算法

```
fingerprint = SHA256(
    sort([
        "cpu:" + cpu_id,
        "mac:" + mac_address,
        "disk:" + disk_serial,
        "board:" + board_serial
    ]).join("|")
)

输出格式: "sha256:a1b2c3d4e5f6..."
```

### 9.4.3 容错策略

考虑到硬件更换场景，采用**加权匹配**而非严格匹配：

| 组件 | 权重 | 说明 |
|------|------|------|
| CPU ID | 30 | 更换概率低 |
| MAC 地址 | 25 | 网卡可能更换 |
| 磁盘序列号 | 25 | 磁盘可能更换 |
| 主板序列号 | 20 | 更换概率最低 |

```
匹配规则:
- 总权重 100
- 匹配得分 >= 70 → 通过
- 匹配得分 50-69 → 警告 (允许运行，记录审计日志)
- 匹配得分 < 50 → 拒绝

这样允许客户更换单个硬件而不立即失效。
```

### 9.4.4 Docker 环境特殊处理

在 Docker 容器内采集宿主机指纹的方法：

```bash
# 方案 1: 通过 privileged 模式或设备映射
docker run --privileged ...

# 方案 2 (推荐): 宿主机预先生成指纹文件
# 宿主机运行指纹采集工具:
./fingerprint_tool generate -o /opt/ai_platform/license/machine_fingerprint.txt

# 容器内读取:
/opt/ai_platform/license/machine_fingerprint.txt

# 方案 3: 映射宿主机关键信息
docker run \
  -v /proc/cpuinfo:/host/cpuinfo:ro \
  -v /sys/class/dmi/id:/host/dmi:ro \
  -v /sys/class/net:/host/net:ro \
  ...
```

**推荐方案 2**：宿主机部署时运行指纹采集工具，生成指纹文件，映射进容器。

## 9.5 指纹采集工具

```bash
# fingerprint_tool — 机器指纹采集与管理工具

# 生成机器指纹
fingerprint_tool generate [-o output_file]

# 显示机器信息 (明文)
fingerprint_tool show

# 验证 License 文件 (离线)
fingerprint_tool verify -l license.dat [-f fingerprint_file]

# 输出示例:
# === Machine Information ===
# CPU:   Intel(R) Xeon(R) Gold 6248R @ 3.00GHz (48 cores)
# MAC:   00:1A:2B:3C:4D:5E
# Disk:  S3HCNX0M800001
# Board: /C621A/LEET/M.2
# === Fingerprint ===
# sha256:a1b2c3d4e5f6789012345678901234567890abcdef
```

## 9.6 授权签发工具 (内部使用)

 授权签发能力分为两种内部形态：

 1. **命令行工具**：适合自动化批量签发。
 2. **内部 Web 服务**：适合交付、商务、运维人员通过页面生成授权文件。

```bash
# license_issuer — 授权签发工具 (仅内部使用，不交付给客户)

# 生成 RSA 密钥对 (首次)
license_issuer keygen -o keys/

# 签发 License
license_issuer issue \
  --customer "某某公司" \
  --customer-id "CUST-001" \
  --type trial \
  --fingerprint "sha256:a1b2c3d4..." \
  --capabilities "face_detect,face_recognize,liveness_silent" \
  --duration 6m \                    # 6个月
  --max-qps 100 \
  --private-key keys/private.pem \
  --output license.dat

# 续期
license_issuer renew \
  --license license.dat \
  --duration 12m \
  --private-key keys/private.pem \
  --output license_renewed.dat

# 查看 License 信息
license_issuer inspect -l license.dat --public-key keys/public.pem
```

## 9.6.1 内部授权签发 Web 服务

该服务单独部署到专用 Docker 中，仅用于内部操作，绝不出现在客户交付包中。

### 服务定位

| 项 | 说明 |
|----|------|
| **服务名称** | License Issuer Web |
| **部署方式** | 独立 Docker 容器 |
| **访问范围** | 仅公司内网/VPN |
| **宿主机端口** | `26010` |
| **安全要求** | 登录鉴权 + 操作审计 + 私钥只读挂载 |

### 功能清单

- **录入客户信息**：客户名称、客户编号、联系人
- **上传/粘贴机器指纹**：支持从 `machine_fingerprint.txt` 导入
- **选择授权能力**：勾选能力列表
- **选择授权类型**：试用、商业、开发、永久
- **设置授权时长**：如 3 个月、6 个月、12 个月
- **生成并下载 `license.dat`**
- **查看历史签发记录**
- **续期/补签**

### 安全约束

1. **私钥只在内部签发环境存在**。
2. **私钥通过只读挂载注入，不入镜像**。
3. **服务需登录鉴权，支持角色权限控制**。
4. **所有签发操作写审计日志**。
5. **该服务不对外网开放，不交付客户**。

## 9.7 运行时校验机制

### 9.7.1 双层校验架构

```
┌─────────────────────────────────────────┐
│  Layer 1: HTTP 服务层校验 (完整校验)     │
│                                         │
│  ✓ 签名验证                              │
│  ✓ 机器指纹匹配                          │
│  ✓ 有效期检查                            │
│  ✓ 能力范围检查 (请求的能力是否已授权)     │
│  ✓ QPS/并发限制检查                       │
│  ✓ 平台版本约束检查                       │
│                                         │
│  检查时机: 每个推理请求前                  │
│  缓存策略: 缓存校验结果，定期刷新          │
└─────────────────┬───────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────┐
│  Layer 2: Runtime 层校验 (轻量校验)      │
│                                         │
│  ✓ License 状态标记检查 (内存中的布尔值)  │
│  ✓ 能力是否在授权范围                     │
│                                         │
│  检查时机: 分配实例前                     │
│  目的: 防止绕过 HTTP 层直接调用 Runtime   │
└─────────────────────────────────────────┘
```

### 9.7.2 校验流程

```
启动时:
├── 读取 License 文件
├── RSA 公钥验签
├── 解析 JSON payload
├── 读取机器指纹文件
├── 匹配机器指纹 (加权匹配)
├── 检查有效期
├── 检查平台版本约束
├── 缓存: 授权状态 + 授权能力列表 + 到期时间
└── 记录审计日志

推理请求时 (HTTP 层):
├── 读取缓存的授权状态
│   ├── 无效 → 返回 403 + 原因
│   └── 有效 → 继续
├── 检查请求能力是否在授权范围
│   ├── 未授权 → 返回 403
│   └── 已授权 → 继续
├── 检查是否到期 (内存中的到期时间)
│   ├── 已到期 → 返回 403
│   ├── 宽限期内 → 返回 200 + Warning 头
│   └── 未到期 → 继续
└── 放行请求

定期检查 (后台线程, 默认每小时):
├── 重新读取 License 文件 (支持热更新 License)
├── 重新完整校验
├── 更新内存缓存
└── 记录审计日志
```

### 9.7.3 到期行为

| 阶段 | 行为 |
|------|------|
| **正常运行** | 全功能可用 |
| **到期前 7 天** | 正常运行 + 日志警告 + API 响应中附带 Warning 头 |
| **到期后宽限期** (默认 24h) | 正常运行 + 强警告 + 审计日志 |
| **宽限期后** | **禁止推理**，仅保留以下接口可用：`/api/v1/health`、`/api/v1/license/status`、`/api/v1/capabilities`(标记为 expired) |

### 9.7.4 当前已落地的 HTTP 层授权控制

当前实现已经在 HTTP 层落地如下最小授权控制：

- `POST /api/v1/infer/{capability_id}`：先校验 License 总状态，再校验 capability 是否授权
- `POST /api/v1/runtime/reload-all`：先校验 `X-Admin-Token`，再校验 License 总状态
- `POST /api/v1/runtime/reload/{capability_id}`：先校验 `X-Admin-Token`，再校验 License 总状态

当前最小错误语义：

| 接口范围 | 场景 | HTTP Status | code | message |
|----------|------|-------------|------|---------|
| infer | License 无效 | `403` | `-402` | `license invalid` |
| infer | capability 未授权 | `403` | `-401` | `capability not licensed` |
| reload 管理接口 | Admin Token 缺失或错误 | `401` | `-303` | `admin token invalid` |
| reload 管理接口 | License 无效 | `403` | `-302` | `license invalid` |

这与设计中的 `allow_admin_api`、`allow_reload` 能力开关保持方向一致。当前实现尚未把 License `features` 字段逐项解析为运行时策略，而是先通过 Admin Token + License 总状态完成管理写接口的最小保护闭环。

## 9.8 License 管理器实现

```cpp
class LicenseManager {
public:
    // 初始化（加载并校验 license.dat）
 + 公钥 + 机器指纹
    bool initialize(const std::string& license_path,
                    const std::string& public_key_path,
                    const std::string& fingerprint_path);
    
    // ---- 校验接口 ----
    
    // 完整校验 (启动时 + 定期刷新)
    LicenseStatus full_validate();
    
    // 快速校验 (每次请求)
    bool quick_check(const std::string& capability_id) const;
    
    // ---- 状态查询 ----
    
    // 获取授权状态
    LicenseInfo get_status() const;
    
    // 检查特定能力是否授权
    bool is_capability_licensed(const std::string& capability_id) const;
    
    // 获取剩余天数
    int days_remaining() const;
    
    // 是否在宽限期
    bool in_grace_period() const;
    
    // ---- 管理 ----
    
    // 重新加载 License (热更新)
    bool reload_license(const std::string& new_license_path = "");
    
    // 启动后台监控线程
    void start_monitor(int check_interval_seconds = 3600);
    void stop_monitor();

private:
    // RSA 验签
    bool verify_signature(const std::string& payload, const std::string& signature);
    
    // 解析 License
    bool parse_license(const std::string& license_content);
    
    // 机器指纹匹配
    FingerprintMatchResult match_fingerprint();
    
    struct CachedStatus {
        bool valid = false;
        std::string reason;
        std::set<std::string> licensed_capabilities;
        int64_t expires_at = 0;
        int64_t grace_until = 0;
        int max_qps = 0;
        int max_concurrent = 0;
    };
    
    std::atomic<CachedStatus*> cached_status_{nullptr};  // 原子指针，无锁读
    mutable std::shared_mutex status_mutex_;
    
    std::string public_key_;
    std::string machine_fingerprint_;
    nlohmann::json license_payload_;
    
    std::thread monitor_thread_;
    std::atomic<bool> monitor_running_{false};
};

struct LicenseInfo {
    bool valid;
    std::string license_id;
    std::string license_type;
    std::string customer_name;
    std::string issued_at;
    std::string expires_at;
    int days_remaining;
    bool in_grace_period;
    bool machine_bound;
    std::vector<std::string> licensed_capabilities;
    int max_qps;
    std::string rejection_reason;  // 无效时的原因
};
```

## 9.8.1 多交付形态授权适配

| 交付形态 | 授权校验位置 | 说明 |
|---------|-------------|------|
| Docker 平台版 | HTTP 层 + Runtime 层 | 双层校验 |
| Linux SO 版 | SDK 入口层 + 插件内部 | 无 HTTP 层 |
| JNI 版 | JNI 桥接层 + 插件内部 | Java 调用前先验授权 |
| Windows DLL 版 | DLL 导出入口 + 插件内部 | 本地离线校验 |

统一要求：

- 授权文件格式尽量保持一致。
- 客户环境不持有私钥。
- 单能力交付版可裁剪掉不必要的平台级字段，但校验模型一致。

## 9.9 密钥管理

| 密钥 | 存储位置 | 用途 |
|------|---------|------|
| **RSA 私钥** | 内部授权签发服务器 (不交付) | 签发 License |
| **RSA 公钥** | 编译进镜像 `/app/config/license_public.pem` | 验证 License 签名 |

**安全措施**：
- 公钥嵌入二进制文件中（编译时 embed），增加提取难度
- 私钥 2048 位 RSA，存储在离线签发环境
- License 文件本身不含任何密钥材料

```cpp
// 公钥嵌入示例 (编译时)
// 通过 CMake 将 public.pem 转为 C 数组
// 或使用 xxd -i public.pem > embedded_key.h

static const unsigned char EMBEDDED_PUBLIC_KEY[] = {
    // ... 编译时嵌入的公钥数据
};
static const size_t EMBEDDED_PUBLIC_KEY_SIZE = sizeof(EMBEDDED_PUBLIC_KEY);
```

## 9.10 审计日志

所有授权相关事件写入独立的审计日志：

```
/opt/ai_platform/logs/audit.log
```

```
[2026-03-26T10:00:00Z] [LICENSE] Platform started. License: LIC-20260301-001, Type: trial, Expires: 2026-09-01
[2026-03-26T10:00:00Z] [LICENSE] Machine fingerprint match: score=95/100 (PASS)
[2026-03-26T10:00:00Z] [LICENSE] Licensed capabilities: face_detect, face_recognize, liveness_silent, ...
[2026-03-26T14:00:00Z] [LICENSE] Periodic check: valid, 159 days remaining
[2026-08-25T10:00:00Z] [LICENSE] WARNING: License expires in 7 days
[2026-09-01T00:00:00Z] [LICENSE] WARNING: License expired, entering grace period (24h)
[2026-09-02T00:00:00Z] [LICENSE] CRITICAL: License expired and grace period ended. Inference disabled.
[2026-09-03T10:00:00Z] [LICENSE] License reloaded: LIC-20260901-002, new expiry: 2027-03-01
```

## 9.11 License 更新流程

```
1. 客户提交机器指纹文件
   └── 通过安全渠道发送 machine_fingerprint.txt

2. 内部签发新 License
   └── license_issuer renew/issue → license.dat

3. 交付新 License 到客户
   └── 通过安全渠道发送 license.dat

4. 客户更新
   └── 将 license.dat 放入 /opt/ai_platform/license/
   └── 方式 A: 等待自动检测 (默认每小时)
   └── 方式 B: 调用 POST /api/v1/admin/reload { "type": "license" }

5. 自动生效
   └── 平台检测到新 License → 验证 → 生效
   └── 无需重启容器
```
