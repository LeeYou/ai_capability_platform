# 06 — Runtime 运行时设计

## 6.1 Runtime 职责

Runtime 是连接 HTTP 服务层与插件层的核心中间件，职责包括：

1. **插件生命周期管理** — dlopen/dlclose、接口绑定、版本校验
2. **能力实例池** — 创建/销毁/调度 PluginHandle 实例
3. **模型缓存** — 共享模型的加载与引用计数管理
4. **并发调度** — 请求分配实例、等待、超时控制
5. **Reload/Rollback** — 热更新插件或模型，失败自动回滚
6. **能力路由** — 根据 capability_id 定位插件和实例池
7. **健康监控** — 定期检查各能力健康状态

## 6.2 核心组件

```
Runtime (AiRuntime)
├── PluginManager       — 插件加载/卸载/查找
├── PoolManager         — 实例池创建/销毁/调度
├── PathResolver        — 目录优先级解析
├── ReloadController    — 热更新/回滚控制
├── HealthMonitor       — 健康监控
└── MetricsCollector    — 调用统计
```

## 6.3 核心类设计

### 6.3.1 AiRuntime — 主入口

```cpp
class AiRuntime {
public:
    // 初始化 Runtime，加载配置、扫描并加载所有已启用的插件
    bool initialize(const RuntimeConfig& config);
    
    // 关闭 Runtime，销毁所有实例和插件
    void shutdown();
    
    // ---- 推理调度 ----
    
    // 同步推理：获取实例 → 调用插件 → 归还实例
    InferResult infer(const InferRequest& request);
    
    // ---- 管理接口 ----
    
    // 获取所有已注册能力列表
    std::vector<CapabilityStatus> list_capabilities() const;
    
    // 获取单个能力状态
    CapabilityStatus get_capability_status(const std::string& capability_id) const;
    
    // 重新加载能力 (模型/插件/全部)
    ReloadResult reload(const std::string& capability_id, ReloadType type);
    
    // 回滚能力到上一个版本
    ReloadResult rollback(const std::string& capability_id);
    
    // ---- 状态 ----
    bool is_healthy() const;
    RuntimeStats get_stats() const;

private:
    std::unique_ptr<PluginManager>    plugin_mgr_;
    std::unique_ptr<PoolManager>      pool_mgr_;
    std::unique_ptr<PathResolver>     path_resolver_;
    std::unique_ptr<ReloadController> reload_ctrl_;
    std::unique_ptr<HealthMonitor>    health_monitor_;
    std::unique_ptr<MetricsCollector> metrics_;
    RuntimeConfig config_;
};
```

### 6.3.2 PluginManager — 插件管理器

```cpp
// 插件注册条目
struct PluginEntry {
    std::string capability_id;
    std::string so_path;
    std::string model_dir;
    void* dl_handle = nullptr;         // dlopen 句柄
    
    // 必选接口函数指针
    fn_ai_plugin_init       fn_init = nullptr;
    fn_ai_plugin_destroy    fn_destroy = nullptr;
    fn_ai_plugin_infer      fn_infer = nullptr;
    fn_ai_plugin_free_result fn_free_result = nullptr;
    fn_ai_plugin_reload     fn_reload = nullptr;
    fn_ai_plugin_get_info   fn_get_info = nullptr;
    
    // 可选接口
    fn_ai_plugin_warmup       fn_warmup = nullptr;
    fn_ai_plugin_health_check fn_health = nullptr;
    
    // 元信息
    std::string plugin_version;
    std::string model_version;
    std::string status;  // "loaded", "error", "unloaded"
};

class PluginManager {
public:
    // 加载单个插件 SO
    // 1. dlopen SO 文件
    // 2. dlsym 获取所有必选接口
    // 3. 校验 API 版本兼容性
    // 4. 注册到内部 map
    bool load_plugin(const std::string& capability_id,
                     const std::string& so_path,
                     const std::string& model_dir);
    
    // 卸载插件
    bool unload_plugin(const std::string& capability_id);
    
    // 替换插件 SO (用于热更新)
    // 返回旧 PluginEntry 用于回滚
    std::unique_ptr<PluginEntry> replace_plugin(
        const std::string& capability_id,
        const std::string& new_so_path);
    
    // 查找插件
    PluginEntry* find(const std::string& capability_id);
    const PluginEntry* find(const std::string& capability_id) const;
    
    // 列出所有已加载插件
    std::vector<std::string> list_loaded() const;

private:
    std::unordered_map<std::string, std::unique_ptr<PluginEntry>> plugins_;
    mutable std::shared_mutex mutex_;
    
    // dlsym 绑定辅助
    bool bind_functions(PluginEntry* entry);
    bool verify_api_version(PluginEntry* entry);
};
```

### 6.3.3 PoolManager — 实例池管理器

```cpp
// 单个能力的实例池
class CapabilityPool {
public:
    explicit CapabilityPool(const std::string& capability_id, int pool_size);
    ~CapabilityPool();
    
    // 获取一个可用实例 (阻塞等待，超时返回 nullptr)
    AiPluginHandle acquire(int timeout_ms = 5000);
    
    // 归还实例
    void release(AiPluginHandle handle);
    
    // 获取池状态
    int available_count() const;
    int total_count() const;
    int busy_count() const;
    
    // 排空：等待所有实例归还 (用于 reload 前)
    bool drain(int timeout_ms = 30000);
    
    // 原子替换所有实例 (用于 reload)
    // 调用前必须先 drain
    void replace_all(std::vector<AiPluginHandle> new_handles,
                     fn_ai_plugin_destroy destroy_fn);
    
    // 销毁所有实例
    void destroy_all(fn_ai_plugin_destroy destroy_fn);
    
    // 状态
    std::string status() const;  // "ready", "draining", "reloading"

private:
    std::string capability_id_;
    std::queue<AiPluginHandle> available_;
    std::set<AiPluginHandle> in_use_;
    std::vector<AiPluginHandle> all_handles_;
    
    mutable std::mutex mutex_;
    std::condition_variable cv_available_;  // 等待可用实例
    std::condition_variable cv_drained_;    // 等待全部归还
    
    std::atomic<std::string> status_{"ready"};
    int pool_size_;
};

class PoolManager {
public:
    // 为能力创建实例池
    bool create_pool(const std::string& capability_id,
                     PluginEntry* plugin,
                     int pool_size,
                     const AiPluginInitParams& init_params);
    
    // 销毁实例池
    void destroy_pool(const std::string& capability_id);
    
    // 获取实例池
    CapabilityPool* get_pool(const std::string& capability_id);
    
    // 获取所有池的状态
    std::map<std::string, PoolStatus> get_all_status() const;

private:
    std::unordered_map<std::string, std::unique_ptr<CapabilityPool>> pools_;
    mutable std::shared_mutex mutex_;
};
```

### 6.3.4 ReloadController — 热更新控制器

```cpp
enum class ReloadType {
    MODEL,    // 仅更新模型
    PLUGIN,   // 更新 SO 插件 (含模型重新加载)
    ALL       // 全部更新
};

struct ReloadResult {
    bool success;
    std::string message;
    std::string old_version;
    std::string new_version;
    double cost_ms;
};

class ReloadController {
public:
    ReloadController(PluginManager* plugin_mgr, PoolManager* pool_mgr,
                     PathResolver* path_resolver);
    
    // 执行热更新
    ReloadResult reload(const std::string& capability_id, ReloadType type);
    
    // 回滚到上一版本
    ReloadResult rollback(const std::string& capability_id);

private:
    // 模型更新流程
    ReloadResult reload_model(const std::string& capability_id);
    
    // 插件更新流程
    ReloadResult reload_plugin(const std::string& capability_id);
    
    // 创建新实例集合
    std::vector<AiPluginHandle> create_new_instances(
        PluginEntry* plugin, int count,
        const AiPluginInitParams& params);
    
    PluginManager* plugin_mgr_;
    PoolManager* pool_mgr_;
    PathResolver* path_resolver_;
    
    // 回滚信息
    struct RollbackInfo {
        std::string old_so_path;
        std::string old_model_dir;
        std::string old_version;
    };
    std::unordered_map<std::string, RollbackInfo> rollback_map_;
    std::mutex rollback_mutex_;
};
```

## 6.4 推理调度流程

```
AiRuntime::infer(request)
│
├── 1. 查找 PluginEntry
│   └── plugin_mgr_->find(request.capability_id)
│       └── 未找到 → 返回 ERROR_CAPABILITY_NOT_FOUND
│
├── 2. 检查能力状态
│   └── entry->status != "loaded" → 返回 ERROR_CAPABILITY_DISABLED
│
├── 3. 从实例池获取 handle
│   └── pool_mgr_->get_pool(id)->acquire(timeout)
│       └── 超时 → 返回 ERROR_POOL_EXHAUSTED (503)
│
├── 4. 准备插件输入
│   ├── 解码 base64 图像数据
│   ├── 构建 AiImage 数组
│   └── 构建 AiPluginInput
│
├── 5. 调用插件推理
│   └── entry->fn_infer(handle, &input, &output)
│       └── 失败 → 记录错误，继续到步骤 6
│
├── 6. 归还 handle 到实例池
│   └── pool->release(handle)  // 无论成功失败都归还
│
├── 7. 处理结果
│   ├── 成功 → 解析 output.result_json，构建 InferResult
│   ├── 失败 → 构建错误 InferResult
│   └── 释放 → entry->fn_free_result(&output)
│
├── 8. 记录指标
│   └── metrics_->record(capability_id, cost_ms, success)
│
└── 9. 返回 InferResult
```

## 6.5 Reload 详细流程

### 6.5.1 模型更新流程

```
ReloadController::reload_model(capability_id)
│
├── 1. 获取 PluginEntry 和 CapabilityPool
│
├── 2. 解析新模型目录
│   └── path_resolver_->resolve_model_dir(capability_id)
│   └── 校验 manifest.yaml、checksum
│
├── 3. 标记池状态为 "draining"
│
├── 4. 排空实例池
│   └── pool->drain(timeout=30s)
│   └── 超时 → 恢复状态，返回失败
│
├── 5. 对每个 handle 调用 plugin->reload(handle, new_model_dir)
│   └── 任一失败 → 对已 reload 的 handle 回滚
│
├── 6. 预热
│   └── 对每个 handle 调用 plugin->warmup(handle)
│
├── 7. 恢复池状态为 "ready"
│
├── 8. 保存回滚信息
│
└── 9. 返回成功
```

### 6.5.2 插件 SO 更新流程

```
ReloadController::reload_plugin(capability_id)
│
├── 1. 解析新 SO 路径和模型目录
│
├── 2. 标记池为 "draining"
│
├── 3. 排空实例池
│
├── 4. 销毁旧实例
│   └── pool->destroy_all(old_entry->fn_destroy)
│
├── 5. 替换插件 SO
│   └── plugin_mgr_->replace_plugin(id, new_so_path)
│   └── 失败 → 用旧 SO 重建实例，返回失败
│
├── 6. 用新插件创建新实例
│   └── create_new_instances(new_entry, pool_size, params)
│   └── 失败 → 恢复旧 SO + 旧实例，返回失败
│
├── 7. 替换实例池
│   └── pool->replace_all(new_handles, new_entry->fn_destroy)
│
├── 8. 预热
│
├── 9. 恢复池状态
│
├── 10. 卸载旧 SO (dlclose)
│
└── 11. 保存回滚信息，返回成功
```

## 6.6 健康监控

```cpp
class HealthMonitor {
public:
    // 启动监控线程
    void start(int check_interval_seconds = 60);
    void stop();
    
    // 获取整体健康状态
    HealthStatus get_overall_status() const;
    
    // 获取单个能力健康状态
    CapabilityHealth get_capability_health(const std::string& id) const;

private:
    void monitor_loop();
    
    // 对每个能力:
    // 1. 检查池是否有可用实例
    // 2. 获取一个实例做 health_check
    // 3. 检查最近 N 次推理的错误率
    // 4. 检查平均推理耗时是否异常
    void check_capability(const std::string& id);
    
    struct CapabilityHealth {
        std::string status;       // "healthy", "degraded", "unhealthy"
        int available_instances;
        double error_rate_1min;
        double avg_latency_ms;
        std::string last_error;
        int64_t last_check_time;
    };
    
    std::unordered_map<std::string, CapabilityHealth> health_map_;
    std::thread monitor_thread_;
    std::atomic<bool> running_{false};
};
```

## 6.7 指标收集

```cpp
struct CapabilityMetrics {
    std::string capability_id;
    
    // 计数器
    std::atomic<uint64_t> total_requests{0};
    std::atomic<uint64_t> success_count{0};
    std::atomic<uint64_t> error_count{0};
    
    // 耗时统计 (滑动窗口)
    double avg_latency_ms;
    double p50_latency_ms;
    double p95_latency_ms;
    double p99_latency_ms;
    double max_latency_ms;
    
    // 并发
    std::atomic<int> current_inflight{0};
    int peak_inflight;
    
    // 实例池
    int pool_total;
    int pool_available;
};

class MetricsCollector {
public:
    void record(const std::string& capability_id,
                double latency_ms, bool success);
    
    CapabilityMetrics get_metrics(const std::string& capability_id) const;
    std::vector<CapabilityMetrics> get_all_metrics() const;
    
    // 导出为 JSON (供管理接口使用)
    nlohmann::json export_json() const;
};
```

## 6.8 配置结构

```cpp
struct RuntimeConfig {
    // 设备
    AiDeviceType device = AI_DEVICE_CPU;
    int gpu_device_id = 0;
    size_t gpu_memory_limit_mb = 4096;
    
    // 路径
    std::string host_plugin_dir;
    std::string host_model_dir;
    std::string builtin_plugin_dir;
    std::string builtin_model_dir;
    
    // 默认池大小
    int default_pool_size = 2;
    
    // 超时
    int acquire_timeout_ms = 5000;
    int reload_drain_timeout_ms = 30000;
    int plugin_load_timeout_ms = 60000;
    
    // 各能力独立配置
    struct CapabilityConfig {
        bool enabled = true;
        int pool_size = -1;       // -1 表示使用默认值
        std::string model_version;
    };
    std::unordered_map<std::string, CapabilityConfig> capabilities;
    
    // 健康检查
    int health_check_interval_seconds = 60;
};
```
