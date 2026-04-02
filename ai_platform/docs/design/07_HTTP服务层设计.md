# 07 — HTTP 服务层设计

## 7.1 职责边界

HTTP 服务层**只负责**：

| 职责 | 说明 |
|------|------|
| 接收 HTTP 请求 | 监听端口（默认 26000），解析 HTTP 方法/路径/头/体 |
| 参数校验 | 校验必填字段、图像/视频格式、大小限制 |
| License 状态检查 | 调用 License 模块检查授权状态和能力范围 |
| 能力路由 | 根据 URL 中的 capability_id 路由到 Runtime |
| 请求转换 | 将 HTTP 请求转为 Runtime 的 InferRequest |
| 响应序列化 | 将 InferResult 转为统一 JSON 响应 |
| 管理接口 | 健康检查、能力列表、授权状态、reload 管理 |
| 静态文件服务 | 提供测试 Web 页面的静态文件 |
| 访问日志 | 记录每个请求的基本信息 |
| CORS 处理 | 支持跨域请求（测试页面需要） |

**不负责**：模型推理、插件管理、实例调度。

## 7.2 API 路由设计

### 7.2.1 路由总表

| 方法 | 路径 | 说明 | 认证 |
|------|------|------|------|
| `POST` | `/api/v1/infer/{capability_id}` | 统一推理接口 | License |
| `GET` | `/api/v1/health` | 健康检查 | 无 |
| `GET` | `/api/v1/capabilities` | 获取能力列表 | 无 |
| `GET` | `/api/v1/runtime/status` | 获取运行时状态与汇总指标 | 无 |
| `GET` | `/api/v1/metrics/runtime` | 获取独立运行时指标 | 无 |
| `GET` | `/api/v1/license/status` | 获取授权状态 | 无 |
| `POST` | `/api/v1/runtime/reload/{capability_id}` | 触发单能力热更新 | 预留 |
| `POST` | `/api/v1/runtime/reload-all` | 触发全量能力热更新 | 预留 |
| `GET` | `/api/v1/version` | 获取平台版本信息 | 无 |
| `GET` | `/` | 测试 Web 页面 (静态文件) | 无 |

当前代码实现以 `/api/v1/runtime/*` 与 `/api/v1/metrics/runtime` 作为管理接口路径，属于现阶段最小可运行实现；后续如引入统一管理鉴权，可再收敛到 `/api/v1/admin/*` 风格。

### 7.2.2 版本策略

- URL 中包含版本号 `/api/v1/...`
- 未来升级不兼容 API 时使用 `/api/v2/...`
- `/api/v1` 在 v2 发布后仍保留一段时间

## 7.3 统一推理接口

### 7.3.1 请求格式

**POST** `/api/v1/infer/{capability_id}`

```
Content-Type: application/json
```

**通用请求体**：

```json
{
    "request_id": "optional-client-request-id",
    "images": [
        {
            "data": "base64编码的图像数据",
            "format": "jpeg"
        }
    ],
    "params": {
        // 能力特定参数，可选
    }
}
```

当前实现同时支持最小文件引用方式：

```json
{
    "request_id": "optional-client-request-id",
    "images": [
        {
            "uri": "demo.jpg",
            "format": "jpeg"
        }
    ],
    "params": {
    }
}
```

 对于视频类能力，扩展请求体如下：

 ```json
 {
     "request_id": "optional-client-request-id",
     "media": {
         "type": "video",
         "data": "base64编码的视频文件数据",
         "format": "mp4"
     },
     "params": {
         "sample_fps": 5,
         "max_frames": 32
     }
 }
 ```

**各能力特定参数示例**：

```json
// face_detect — 人脸检测
{
    "images": [{"data": "base64...", "format": "jpeg"}],
    "params": {
        "min_face_size": 30,
        "confidence_threshold": 0.5,
        "max_faces": 10,
        "return_landmarks": true
    }
}

// face_recognize — 人脸识别 (比对)
{
    "images": [
        {"data": "base64_face_1...", "format": "jpeg"},
        {"data": "base64_face_2...", "format": "jpeg"}
    ],
    "params": {
        "threshold": 0.65
    }
}

// liveness_action — 指令活体
{
    "images": [
        {"data": "base64_frame_1...", "format": "jpeg"},
        {"data": "base64_frame_2...", "format": "jpeg"},
        {"data": "base64_frame_3...", "format": "jpeg"}
    ],
    "params": {
        "actions": ["blink", "open_mouth", "turn_head"],
        "timeout_seconds": 15
    }
}

// doc_classify — 证件类型识别
{
    "images": [{"data": "base64...", "format": "jpeg"}],
    "params": {
        "top_k": 3
    }
}

// general_ocr — 通用 OCR
{
    "images": [{"data": "base64...", "format": "jpeg"}],
    "params": {
        "language": "zh-en",
        "detect_direction": true,
        "return_confidence": true
    }
}

// deepfake_detect — 换脸检测（视频）
{
    "media": {
        "type": "video",
        "data": "base64_video...",
        "format": "mp4"
    }
}
```

### 7.3.2 当前输入校验与限制

当前 HTTP 层已经实现以下最小输入校验：

| 项目 | 当前规则 |
|------|----------|
| Content-Type | `POST /infer/*` 必须为 `application/json`，兼容带 charset 参数 |
| 请求体类型 | 必须是 JSON object |
| 请求体大小 | 最大 `server.max_body_size_mb`，默认 `50 MB` |
| `request_id` | 可选；如存在必须是非空字符串，最大长度 `128` |
| `params` | 可选；如存在必须是 object |
| `images` | 可选；如存在必须是 array |
| 空图片数组 | `images: []` 视为非法输入 |
| 图片数量 | 最多 `8` 张 |
| 图片项 | 必须是 object，且至少包含 `data` 或 `uri` |
| `images[].data` | 如提供，当前要求为 base64 文本 |
| `images[].uri` | 如提供，当前仅接受本地路径或 `file://` |
| 图片格式 | 白名单：`jpeg`、`jpg`、`png`、`bmp` |
| `media` | 可选；如存在必须是 object |
| `media.type` | 当前仅支持 `video` |
| 视频项 | 至少包含 `data` 或 `uri` |
| `media.data` | 如提供，当前要求为 base64 文本 |
| `media.uri` | 如提供，当前仅接受本地路径或 `file://` |
| 视频格式 | 白名单：`mp4`、`avi`、`mov` |
| `media.data` 大小 | 当前最小实现受 `server.max_video_size_mb` 限制，默认 `200 MB` |
| 媒体输入要求 | `images` 与 `media` 至少存在一种 |

当前实现中，`liveness_action` 已作为视频类请求最小样板能力接入，可用于验证以下两类输入从 HTTP 层进入 Runtime，并传递到插件层的最小闭环：

- `media.type=video` + `params.action`
- 多张 `images` 作为 `frame_sequence` + `params.action`

当前最小专属校验规则：

- `params.action` 必填
- 当前允许动作：`blink`、`mouth`、`shake_head`、`nod`
- `liveness_action` 必须提供视频输入，或至少 `2` 张图片作为帧序列输入

当前推理入口还增加了最小授权拦截：

| 项目 | 当前规则 |
|------|----------|
| License 总状态 | `POST /infer/*` 在请求体校验通过后先检查 License 总状态，`valid=false` 时直接拒绝 |
| Capability 授权 | License 有效后再检查 capability 是否在授权列表中 |

当前错误语义采用最小明确错误消息，如：`content-type must be application/json`、`invalid json body`、`request_id too long`、`images array is empty`、`invalid images`、`invalid image data`、`invalid image uri`、`unsupported image format`、`invalid media data`、`invalid media uri`、`unsupported media format`、`missing media input`、`license invalid`、`capability not licensed`。

当前错误码语义：

| 场景 | HTTP Status | code | message |
|------|-------------|------|---------|
| License 无效 | `403` | `-402` | `license invalid` |
| capability 未授权 | `403` | `-401` | `capability not licensed` |

### 7.3.4 管理写接口最小认证与授权

当前实现已对管理写接口增加最小保护，范围包括：

- `POST /api/v1/runtime/reload-all`
- `POST /api/v1/runtime/reload/{capability_id}`

当前认证/授权顺序如下：

1. 先校验请求头 `X-Admin-Token`
2. Token 通过后再校验 License 总状态
3. 两者都通过后才执行 reload

当前返回语义：

| 场景 | HTTP Status | code | message |
|------|-------------|------|---------|
| Admin Token 缺失或错误 | `401` | `-303` | `admin token invalid` |
| License 无效 | `403` | `-302` | `license invalid` |
| reload 执行失败 | `400` | `-301` / `-300` | `reload all failed` / `reload failed` |

### 7.3.5 统一响应格式

**成功响应**：

```json
{
    "code": 0,
    "message": "success",
    "data": {
        // 能力特定的返回数据
    },
    "request_id": "req_20260326_abc123",
    "cost_ms": 42.5,
    "api_version": "v1"
}
```

当前实现的推理响应还会补充：

- `endpoint`
- `timestamp`

**各能力返回 data 示例**：

```json
// face_detect
{
    "face_count": 2,
    "faces": [
        {
            "box": {"x": 100, "y": 50, "width": 120, "height": 140},
            "confidence": 0.98,
            "landmarks": {
                "left_eye": [130, 90],
                "right_eye": [190, 88],
                "nose": [160, 120],
                "left_mouth": [135, 155],
                "right_mouth": [185, 153]
            }
        },
        {
            "box": {"x": 300, "y": 80, "width": 100, "height": 130},
            "confidence": 0.95,
            "landmarks": { ... }
        }
    ]
}

// face_recognize
{
    "similarity": 0.87,
    "is_same_person": true,
    "threshold": 0.65
}

// liveness_silent
{
    "is_live": true,
    "score": 0.92,
    "threshold": 0.5
}

// face_attribute
{
    "glasses": true,
    "hat": false,
    "mask": false,
    "head_pose": {"yaw": 5.2, "pitch": -3.1, "roll": 1.5},
    "age_range": "25-35",
    "gender": "male",
    "gender_confidence": 0.96
}

// doc_classify
{
    "doc_type": "id_card_front",
    "doc_type_id": 1,
    "doc_type_name": "二代身份证人像面",
    "confidence": 0.97,
    "candidates": [
        {"doc_type": "id_card_front", "confidence": 0.97},
        {"doc_type": "temp_id_card", "confidence": 0.02}
    ]
}

// general_ocr
{
    "text_regions": [
        {
            "box": [[10,20], [200,20], [200,50], [10,50]],
            "text": "识别到的文字内容",
            "confidence": 0.95
        }
    ],
    "full_text": "所有识别文字的拼接结果"
}

// seal_detect
{
    "seal_count": 1,
    "seals": [
        {
            "box": {"x": 400, "y": 500, "width": 150, "height": 150},
            "confidence": 0.93,
            "shape": "circle"
        }
    ]
}
```

**错误响应**：

```json
{
    "code": -2,
    "message": "Invalid parameter: image data is empty",
    "data": null,
    "request_id": "req_20260326_abc123",
    "cost_ms": 0.5,
    "api_version": "v1"
}
```

## 7.4 当前管理接口补充说明

### 7.4.1 `/api/v1/capabilities`

当前实现除能力列表外，还返回：

- `summary`
- `summary.status_breakdown`
- `summary.metrics`
- 每个 capability 下钻的最小 `metrics`

其中 `summary.metrics` 与 capability 级 `metrics` 已包含：

- `request_count`
- `success_count`
- `failure_count`
- `busy_reject_count`
- `avg_cost_ms` 或汇总耗时字段
- `last_request_timestamp`
- `last_success_timestamp`
- `last_failure_timestamp`
- `last_error_code`

### 7.4.2 `/api/v1/runtime/status`

当前实现返回：

- 运行状态
- host / port
- capability / pool 汇总信息
- 汇总 `metrics`
- capability 级 metrics 列表

### 7.4.3 `/api/v1/metrics/runtime`

当前实现提供独立的 runtime metrics 视图，用于将运行时指标从 `runtime/status` 中解耦。

### 7.4.4 当前 server 配置来源

当前实现中的 HTTP 服务配置来源如下：

1. `ServerConfig` 结构体默认值
2. `config/platform.yaml` 中的 `server.host`、`server.port`、`server.workers`、`server.request_timeout_ms`、`server.max_body_size_mb`、`server.max_video_size_mb`、`server.admin_token`
3. 环境变量覆盖：`AI_PLATFORM_SERVER_HOST`、`AI_PLATFORM_SERVER_PORT`、`AI_PLATFORM_SERVER_WORKERS`、`AI_PLATFORM_SERVER_REQUEST_TIMEOUT_MS`、`AI_PLATFORM_SERVER_MAX_BODY_SIZE_MB`、`AI_PLATFORM_SERVER_MAX_VIDEO_SIZE_MB`、`AI_PLATFORM_ADMIN_TOKEN`

其中：

- `host` / `port` 直接影响监听地址与端口
- `workers` 影响 `cpp-httplib` 线程池大小
- `request_timeout_ms` 影响 HTTP 读写超时
- `max_body_size_mb` 影响 `cpp-httplib` payload 上限与 infer 请求体大小校验
- `max_video_size_mb` 当前影响 JSON 内联 `media.data` 的最小大小限制
- `admin_token` 影响管理写接口 `X-Admin-Token` 校验

## 7.5 当前最小回归脚本

当前仓库已提供 Windows 可执行的最小回归脚本：

- 路径：`scripts/api_smoke_test.ps1`

当前脚本支持通过参数覆盖：

- `-BaseUrl`
- `-AdminToken`
- `-Mode`

当前覆盖范围包括：

- `GET /api/v1/health`
- `POST /api/v1/infer/{capability_id}` 成功路径
- `POST /api/v1/infer/{capability_id}` 失败路径
- 非法 JSON / 缺少媒体输入 / 非法结构 / 非法格式
- `images.data` / `media.data` 非法 base64 失败路径
- `images.uri` / `media.uri` 远程 URL 失败路径
- `POST /api/v1/infer/liveness_action` 的 `media.type=video` 成功路径
- `POST /api/v1/infer/liveness_action` 的多帧 `frame_sequence` 成功路径
- `POST /api/v1/infer/liveness_action` 的非法 `action` 失败路径
- `GET /api/v1/capabilities`
- `GET /api/v1/runtime/status`
- `GET /api/v1/metrics/runtime`
- 管理写接口 Admin Token 缺失 / 错误 / 正确 token
- `license_invalid` 模式下 infer 与管理写接口拒绝路径
- 自定义 `BaseUrl` 与 `/health.data.port` 一致性验证
- 自定义 `AdminToken` 生效且默认 token 失效的验证
- 管理接口 `405 Method Not Allowed` 基线验证

## 7.6 管理接口详细设计

### 7.6.1 健康检查

**GET** `/api/v1/health`

```json
// 响应
{
    "code": 0,
    "message": "healthy",
    "data": {
        "status": "healthy",           // healthy | degraded | unhealthy
        "uptime_seconds": 86400,
        "device_mode": "cuda",
        "gpu_info": {
            "name": "NVIDIA A10",
            "memory_total_mb": 24576,
            "memory_used_mb": 4096
        },
        "capabilities_total": 10,
        "capabilities_healthy": 10,
        "capabilities_degraded": 0,
        "capabilities_unhealthy": 0
    }
}
```

### 7.6.2 能力列表

**GET** `/api/v1/capabilities`

```json
{
    "code": 0,
    "data": {
        "capabilities": [
            {
                "capability_id": "face_detect",
                "name": "人脸检测",
                "description": "检测图像中的人脸位置",
                "version": "1.0.0",
                "model_version": "v1",
                "status": "ready",
                "device": "cuda",
                "pool_size": 4,
                "pool_available": 3,
                "licensed": true,
                "endpoint": "/api/v1/infer/face_detect"
            },
            // ...
        ],
        "total": 10
    }
}
```

### 7.6.3 授权状态

**GET** `/api/v1/license/status`

```json
{
    "code": 0,
    "data": {
        "valid": true,
        "license_type": "trial",          // trial | commercial
        "customer": "某某公司",
        "issued_at": "2026-03-01T00:00:00Z",
        "expires_at": "2026-09-01T00:00:00Z",
        "days_remaining": 159,
        "machine_bound": true,
        "licensed_capabilities": [
            "face_detect", "face_recognize", "liveness_silent",
            "idcard_detect", "general_ocr"
        ],
        "max_qps": 100
    }
}
```

### 7.4.4 热更新

**POST** `/api/v1/admin/reload`

```json
// 请求
{
    "capability_id": "face_detect",     // 必填
    "type": "model"                     // "model" | "plugin" | "all"
}

// 响应
{
    "code": 0,
    "message": "Reload successful",
    "data": {
        "capability_id": "face_detect",
        "old_version": "v1.0.0",
        "new_version": "v1.1.0",
        "reload_type": "model",
        "cost_ms": 2500
    }
}
```

### 7.4.5 回滚

**POST** `/api/v1/admin/rollback`

```json
// 请求
{
    "capability_id": "face_detect"
}

// 响应
{
    "code": 0,
    "message": "Rollback successful",
    "data": {
        "capability_id": "face_detect",
        "rolled_back_to": "v1.0.0",
        "cost_ms": 1800
    }
}
```

## 7.5 请求处理管线

```cpp
// 伪代码 — HTTP 请求处理管线

void handle_infer(const httplib::Request& req, httplib::Response& res) {
    auto start = now();
    std::string request_id = generate_request_id();
    
    // 1. 提取 capability_id
    std::string capability_id = req.matches[1];  // 从 URL 路径提取
    
    // 2. 解析 JSON
    nlohmann::json body;
    try {
        body = nlohmann::json::parse(req.body);
    } catch (...) {
        return send_error(res, AI_ERROR_INVALID_PARAM, "Invalid JSON body", request_id);
    }
    
    // 3. 参数校验
    if (!body.contains("images") || !body["images"].is_array() || body["images"].empty()) {
        return send_error(res, AI_ERROR_INVALID_PARAM, "Missing or empty 'images' field", request_id);
    }
    
    // 4. License 检查
    auto license_status = license_mgr_->check(capability_id);
    if (!license_status.valid) {
        return send_error(res, AI_ERROR_LICENSE_INVALID, license_status.message, request_id);
    }
    
    // 5. 构建 InferRequest
    InferRequest infer_req;
    infer_req.request_id = request_id;
    infer_req.capability_id = capability_id;
    infer_req.params = body.value("params", nlohmann::json::object());
    
    // 解码图像
    for (auto& img_json : body["images"]) {
        ImageData img;
        img.data = base64_decode(img_json["data"].get<std::string>());
        img.format = img_json.value("format", "jpeg");
        infer_req.images.push_back(std::move(img));
    }
    
    // 6. 调用 Runtime
    InferResult result = runtime_->infer(infer_req);
    
    // 7. 构建响应
    double cost_ms = elapsed_ms(start);
    nlohmann::json response = {
        {"code", result.code},
        {"message", result.message},
        {"data", result.data},
        {"request_id", request_id},
        {"cost_ms", cost_ms},
        {"api_version", "v1"}
    };
    
    // 8. 记录访问日志
    log_access(req, capability_id, result.code, cost_ms);
    
    // 9. 返回
    res.set_content(response.dump(), "application/json");
}
```

## 7.6 中间件设计

```
请求 → [CORS] → [RequestID] → [AccessLog] → [RateLimit] → [LicenseCheck] → Handler → 响应
```

| 中间件 | 职责 |
|--------|------|
| **CORS** | 添加跨域头，处理 OPTIONS 预检请求 |
| **RequestID** | 生成/透传请求 ID |
| **AccessLog** | 记录请求基本信息 (方法、路径、耗时、状态码) |
| **RateLimit** | 可选，限制 QPS (根据 License 配置) |
| **LicenseCheck** | 推理接口前置授权检查 |

## 7.7 静态文件服务

HTTP 服务同时提供测试 Web 页面的静态文件服务：

```cpp
// 挂载静态文件目录
server.set_mount_point("/", "/app/web");

// 首页路由
server.Get("/", [](const auto& req, auto& res) {
    res.set_redirect("/index.html");
});
```

## 7.8 Server 核心类

```cpp
class AiHttpServer {
public:
    bool initialize(const ServerConfig& config, 
                    AiRuntime* runtime,
                    LicenseManager* license_mgr);
    
    // 启动监听 (阻塞)
    void start();
    
    // 停止
    void stop();

private:
    void setup_routes();
    void setup_middlewares();
    
    // ---- 路由处理函数 ----
    void handle_infer(const httplib::Request& req, httplib::Response& res);
    void handle_health(const httplib::Request& req, httplib::Response& res);
    void handle_capabilities(const httplib::Request& req, httplib::Response& res);
    void handle_capability_detail(const httplib::Request& req, httplib::Response& res);
    void handle_license_status(const httplib::Request& req, httplib::Response& res);
    void handle_admin_reload(const httplib::Request& req, httplib::Response& res);
    void handle_admin_rollback(const httplib::Request& req, httplib::Response& res);
    void handle_admin_metrics(const httplib::Request& req, httplib::Response& res);
    void handle_version(const httplib::Request& req, httplib::Response& res);
    
    // ---- 辅助 ----
    void send_json(httplib::Response& res, const nlohmann::json& json, int http_status = 200);
    void send_error(httplib::Response& res, int code, const std::string& message,
                    const std::string& request_id, int http_status = 400);
    std::string generate_request_id();
    bool verify_admin_token(const httplib::Request& req);
    
    httplib::Server server_;
    AiRuntime* runtime_ = nullptr;
    LicenseManager* license_mgr_ = nullptr;
    ServerConfig config_;
};

struct ServerConfig {
    std::string host = "0.0.0.0";
    int port = 26000;
    int workers = 8;
    int request_timeout_ms = 30000;
    size_t max_body_size_mb = 50;
    size_t max_video_size_mb = 200;
    std::string admin_token;           // 管理接口令牌
    std::string static_dir = "/app/web";
    bool enable_cors = true;
};
```

## 7.9 端口约定

- AI 平台主服务默认监听容器内端口 `26000`
- 宿主机映射默认使用 `26000:26000`
- 所有后续新增 Docker 服务端口均从 `26000` 开始顺延分配
