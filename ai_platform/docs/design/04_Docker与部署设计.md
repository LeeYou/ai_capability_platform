# 04 — Docker 与部署设计

## 4.1 镜像构建策略

 本文档覆盖两类 Docker 交付：

 1. **AI 平台运行容器**：对客户交付，承载 HTTP 服务、多能力 Runtime、插件和模型。
 2. **内部授权签发服务容器**：仅内部部署，承载 License 签发 Web 服务，不对外客户交付。

采用**多阶段构建**（Multi-stage Build），将编译环境和运行环境分离：

```
┌──────────────────────────────────────────┐
│  Stage 1: Builder (编译阶段)              │
│  基础镜像: nvidia/cuda:12.2-devel-ubuntu22.04  │
│  安装: CMake, GCC, OpenCV-dev, ONNX Runtime    │
│  编译: 主服务 + 所有插件 SO                     │
└────────────────────┬─────────────────────┘
                     │ COPY 编译产物
                     ▼
┌──────────────────────────────────────────┐
│  Stage 2: Runtime (运行阶段)              │
│  基础镜像: nvidia/cuda:12.2-cudnn8-runtime-ubuntu22.04 │
│  安装: OpenCV-runtime, ONNX Runtime Runtime      │
│  复制: 主服务二进制、SO 插件、模型、配置、前端     │
└──────────────────────────────────────────┘
```

## 4.2 Dockerfile 设计

```dockerfile
# ============================================================
# Stage 1: Builder
# ============================================================
FROM nvidia/cuda:12.2.0-devel-ubuntu22.04 AS builder

ENV DEBIAN_FRONTEND=noninteractive
ENV CMAKE_VERSION=3.28.1

# 安装构建依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    cmake \
    git \
    wget \
    pkg-config \
    libopencv-dev \
    libssl-dev \
    libyaml-cpp-dev \
    && rm -rf /var/lib/apt/lists/*

# 安装 ONNX Runtime (GPU)
ARG ONNXRUNTIME_VERSION=1.17.0
RUN wget -q https://github.com/microsoft/onnxruntime/releases/download/v${ONNXRUNTIME_VERSION}/onnxruntime-linux-x64-gpu-${ONNXRUNTIME_VERSION}.tgz \
    && tar -xzf onnxruntime-linux-x64-gpu-${ONNXRUNTIME_VERSION}.tgz -C /opt/ \
    && rm onnxruntime-linux-x64-gpu-${ONNXRUNTIME_VERSION}.tgz

ENV ONNXRUNTIME_DIR=/opt/onnxruntime-linux-x64-gpu-${ONNXRUNTIME_VERSION}

# 复制源码
COPY . /build/src

# 编译
WORKDIR /build
RUN mkdir -p build && cd build \
    && cmake ../src \
       -DCMAKE_BUILD_TYPE=Release \
       -DONNXRUNTIME_DIR=${ONNXRUNTIME_DIR} \
       -DBUILD_PLUGINS=ON \
       -DBUILD_SERVER=ON \
    && make -j$(nproc) \
    && make install DESTDIR=/build/install

# ============================================================
# Stage 2: Runtime
# ============================================================
FROM nvidia/cuda:12.2.0-cudnn8-runtime-ubuntu22.04 AS runtime

ENV DEBIAN_FRONTEND=noninteractive
ENV NVIDIA_VISIBLE_DEVICES=all
ENV NVIDIA_DRIVER_CAPABILITIES=compute,utility

# 安装运行时依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    libopencv-core4.5d \
    libopencv-imgcodecs4.5d \
    libopencv-imgproc4.5d \
    libssl3 \
    libyaml-cpp0.7 \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# ONNX Runtime
ARG ONNXRUNTIME_VERSION=1.17.0
COPY --from=builder /opt/onnxruntime-linux-x64-gpu-${ONNXRUNTIME_VERSION}/lib /usr/local/lib/
RUN ldconfig

# 应用目录结构
RUN mkdir -p /app/bin /app/plugins /app/models /app/config /app/web \
    && mkdir -p /opt/ai_platform/plugins \
    && mkdir -p /opt/ai_platform/models \
    && mkdir -p /opt/ai_platform/license \
    && mkdir -p /opt/ai_platform/config \
    && mkdir -p /opt/ai_platform/logs

# 复制编译产物
COPY --from=builder /build/install/app/bin/ /app/bin/
COPY --from=builder /build/install/app/plugins/ /app/plugins/
COPY --from=builder /build/install/app/config/ /app/config/

# 复制模型包 (构建时嵌入)
COPY models/ /app/models/

# 复制前端静态文件
COPY web/dist/ /app/web/

# 复制启动脚本
COPY docker/entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

WORKDIR /app
EXPOSE 26000

HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD curl -f http://localhost:26000/api/v1/health || exit 1

ENTRYPOINT ["/app/entrypoint.sh"]
```

## 4.3 容器启动脚本 (entrypoint.sh)

```bash
#!/bin/bash
set -e

echo "=========================================="
echo "  AI Capability Platform"
echo "  Version: ${APP_VERSION:-dev}"
echo "  Starting at: $(date)"
echo "=========================================="

# ---- 1. 环境检测 ----
echo "[INIT] Detecting runtime environment..."

# 检测 CUDA 可用性
DEVICE_MODE="cpu"
if command -v nvidia-smi &> /dev/null; then
    if nvidia-smi &> /dev/null; then
        GPU_NAME=$(nvidia-smi --query-gpu=name --format=csv,noheader,nounits 2>/dev/null | head -1)
        GPU_MEM=$(nvidia-smi --query-gpu=memory.total --format=csv,noheader,nounits 2>/dev/null | head -1)
        echo "[INIT] GPU detected: ${GPU_NAME} (${GPU_MEM} MiB)"
        DEVICE_MODE="cuda"
    else
        echo "[INIT] nvidia-smi found but GPU not accessible, falling back to CPU"
    fi
else
    echo "[INIT] No NVIDIA GPU detected, using CPU mode"
fi

export AI_DEVICE_MODE=${AI_DEVICE_MODE:-$DEVICE_MODE}
echo "[INIT] Device mode: ${AI_DEVICE_MODE}"

# ---- 2. 目录检查 ----
echo "[INIT] Checking directories..."

# 宿主机挂载目录
HOST_DIRS=(
    "/opt/ai_platform/plugins"
    "/opt/ai_platform/models"
    "/opt/ai_platform/license"
    "/opt/ai_platform/config"
    "/opt/ai_platform/logs"
)
for dir in "${HOST_DIRS[@]}"; do
    if [ -d "$dir" ]; then
        echo "[INIT]   Host dir found: $dir ($(ls -1 $dir 2>/dev/null | wc -l) items)"
    else
        echo "[INIT]   Host dir missing: $dir (will use builtin)"
        mkdir -p "$dir"
    fi
done

# ---- 3. License 检查 ----
echo "[INIT] Checking license..."
LICENSE_FILE="/opt/ai_platform/license/license.dat"
if [ ! -f "$LICENSE_FILE" ]; then
    LICENSE_FILE="/app/config/license.dat"
fi

if [ -f "$LICENSE_FILE" ]; then
    echo "[INIT] License file found: $LICENSE_FILE"
else
    echo "[WARN] No license file found! Platform will start in restricted mode."
fi

# ---- 4. 启动主服务 ----
echo "[INIT] Starting AI Platform Server..."
exec /app/bin/ai_platform_server \
    --config /app/config/platform.yaml \
    --device ${AI_DEVICE_MODE} \
    --license ${LICENSE_FILE:-""} \
    "$@"
```

## 4.4 Docker Compose 部署模板

 ### 端口规划规范

 所有 Docker 交付容器在宿主机上的端口映射**统一从 `26000` 开始**，按服务类型顺延分配，`26000` 之前端口统一不用。

 推荐规划：

 | 端口 | 服务 |
 |------|------|
 | `26000` | AI 平台主 HTTP 服务 |
 | `26001` | 预留：后续管理服务/辅助服务 |
 | `26010` | 内部授权签发 Web 服务 |

```yaml
# docker-compose.yml — 生产部署模板
version: "3.8"

services:
  ai-platform:
    image: ai-platform:latest
    container_name: ai-platform
    restart: unless-stopped
    
    # GPU 支持
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]
    
    ports:
      - "26000:26000"
    
    volumes:
      # 宿主机挂载目录 — 用于现场更新
      - /opt/ai_platform/plugins:/opt/ai_platform/plugins
      - /opt/ai_platform/models:/opt/ai_platform/models
      - /opt/ai_platform/license:/opt/ai_platform/license
      - /opt/ai_platform/config:/opt/ai_platform/config
      - /opt/ai_platform/logs:/opt/ai_platform/logs
    
    environment:
      - AI_DEVICE_MODE=auto        # auto | cuda | cpu
      - AI_LOG_LEVEL=info
      - AI_WORKERS=8
      - TZ=Asia/Shanghai
    
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:26000/api/v1/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 60s
    
    logging:
      driver: json-file
      options:
        max-size: "100m"
        max-file: "3"
```

### 纯 CPU 模式 (无 GPU 宿主机)

```yaml
# docker-compose.cpu.yml
version: "3.8"

services:
  ai-platform:
    image: ai-platform:latest
    container_name: ai-platform
    restart: unless-stopped
    
    # 不配置 GPU 资源
    ports:
      - "26000:26000"
    
    volumes:
      - /opt/ai_platform/plugins:/opt/ai_platform/plugins
      - /opt/ai_platform/models:/opt/ai_platform/models
      - /opt/ai_platform/license:/opt/ai_platform/license
      - /opt/ai_platform/config:/opt/ai_platform/config
      - /opt/ai_platform/logs:/opt/ai_platform/logs
    
    environment:
      - AI_DEVICE_MODE=cpu
      - AI_LOG_LEVEL=info
      - TZ=Asia/Shanghai
```

## 4.5 宿主机挂载目录规范

```
/opt/ai_platform/                      ← 宿主机根目录
├── plugins/                           ← SO 插件覆盖目录
│   ├── libcap_face_detect.so          ← 覆盖镜像内置版本
│   ├── libcap_face_recognize.so
│   └── .versions/                     ← 历史版本 (用于回滚)
│       ├── libcap_face_detect.so.v1.0.0
│       └── libcap_face_detect.so.v1.1.0
│
├── models/                            ← 模型覆盖目录
│   ├── face_detect/
│   │   ├── current -> v2             ← 当前版本软链接
│   │   ├── v1/
│   │   │   ├── model.onnx
│   │   │   ├── manifest.yaml
│   │   │   └── config.yaml
│   │   └── v2/                       ← 新版本
│   │       ├── model.onnx
│   │       ├── manifest.yaml
│   │       └── config.yaml
│   └── face_recognize/
│       ├── current -> v1
│       └── v1/
│
├── license/                           ← 授权文件目录
│   ├── license.dat                    ← 当前授权文件
│   ├── machine_fingerprint.txt        ← 机器指纹 (只读)
│   └── .backup/                       ← 历史授权备份
│
├── config/                            ← 配置覆盖目录
│   ├── platform.yaml                  ← 覆盖主配置
│   └── capabilities/                  ← 能力级配置覆盖
│       ├── face_detect.yaml
│       └── face_recognize.yaml
│
└── logs/                              ← 日志落地目录
    ├── platform.log                   ← 主服务日志
    ├── platform.log.1                 ← 历史日志 (轮转)
    ├── access.log                     ← 访问日志
    └── audit.log                      ← 审计日志 (授权相关)
```

## 4.6 目录加载优先级逻辑

Runtime 加载资源时统一遵循以下优先级：

```
宿主机挂载目录 → 镜像内置目录 → 报错

具体实现：
```

```cpp
// 路径解析器
class PathResolver {
public:
    // 获取插件 SO 路径
    std::string resolve_plugin_path(const std::string& capability_id) {
        std::string so_name = "libcap_" + capability_id + ".so";
        
        // 1. 优先: 宿主机挂载目录
        std::string host_path = host_plugin_dir_ + "/" + so_name;
        if (file_exists(host_path)) {
            LOG_INFO("Using host plugin: {}", host_path);
            return host_path;
        }
        
        // 2. 回退: 镜像内置目录
        std::string builtin_path = builtin_plugin_dir_ + "/" + so_name;
        if (file_exists(builtin_path)) {
            LOG_INFO("Using builtin plugin: {}", builtin_path);
            return builtin_path;
        }
        
        LOG_ERROR("Plugin not found: {}", so_name);
        return "";
    }
    
    // 获取模型目录路径
    std::string resolve_model_dir(const std::string& capability_id) {
        // 1. 优先: 宿主机目录 / capability / current (软链接)
        std::string host_dir = host_model_dir_ + "/" + capability_id + "/current";
        if (dir_exists(host_dir)) {
            return host_dir;
        }
        
        // 2. 回退: 镜像内置目录
        std::string builtin_dir = builtin_model_dir_ + "/" + capability_id;
        if (dir_exists(builtin_dir)) {
            return builtin_dir;
        }
        
        return "";
    }
};
```

## 4.7 镜像版本管理

| 标签格式 | 示例 | 说明 |
|---------|------|------|
| `ai-platform:latest` | — | 最新稳定版 |
| `ai-platform:<version>` | `ai-platform:1.2.0` | 语义化版本 |
| `ai-platform:<version>-cuda12.2` | — | 含 CUDA 版本标记 |
| `ai-platform:<version>-cpu` | — | 纯 CPU 版本 (可选) |

 ### 多平台镜像策略

 统一采用“**源码一套，按目标平台分别构建**”策略：

 | 目标平台 | 交付方式 | 说明 |
 |---------|---------|------|
 | Linux x86_64 | Docker 平台镜像 / SO | 首期主交付平台 |
 | Windows x86_64 | DLL + 模型包 | 单能力交付 |
 | Linux ARM64 | SO + 模型包 / ARM Docker | 二期或后续扩展 |

 对于 ARM 平台，Docker 基础镜像、ONNX Runtime 和 OpenCV 依赖需要重新适配构建，模型包规范保持不变。

 ## 4.8 内部授权签发服务 Docker

 内部授权签发服务独立部署，不与客户运行容器混用。

 ```yaml
 # docker-compose.license-issuer.yml
 version: "3.8"
 
 services:
   license-issuer:
     image: ai-license-issuer:latest
     container_name: ai-license-issuer
     restart: unless-stopped
     ports:
       - "26010:26010"
     volumes:
       - /opt/ai_license_issuer/config:/app/config
       - /opt/ai_license_issuer/data:/app/data
       - /opt/ai_license_issuer/keys:/app/keys:ro
       - /opt/ai_license_issuer/logs:/app/logs
     environment:
       - ISSUER_PORT=26010
       - TZ=Asia/Shanghai
 ```

 该服务要求：

 - **仅内网访问**。
 - **仅内部账号可登录**。
 - **私钥不进入客户环境**。
 - **不能复用客户运行镜像**。

## 4.9 镜像大小优化策略

| 策略 | 预估节省 |
|------|---------|
| 多阶段构建，不包含编译工具链 | ~2GB |
| 只安装 OpenCV 运行时库 | ~500MB |
| 模型文件使用 ONNX 量化版 (FP16/INT8) | ~50% 模型大小 |
| 清理 apt 缓存 | ~200MB |
| 使用 `.dockerignore` 排除无关文件 | 视情况 |

预估最终镜像大小：
- 基础层 (CUDA Runtime + cuDNN): ~3.5GB
- 应用层 (服务 + SO + 依赖库): ~500MB
- 模型层 (17个能力): ~2-5GB (取决于模型大小)
- **总计: ~6-9GB**
