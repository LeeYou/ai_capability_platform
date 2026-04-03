#ifndef AI_PLATFORM_AI_RUNTIME_H
#define AI_PLATFORM_AI_RUNTIME_H

#include "ai_platform/ai_types.h"
#include "pool_manager.h"
#include "plugin_manager.h"

#include <memory>
#include <mutex>
#include <string>
#include <unordered_map>
#include <vector>

namespace ai_platform {

class ReloadController;

struct RuntimeReloadFailureDetail {
    std::string capability_id;
    std::string reload_reason;
    std::string reload_failed_stage;
    std::string previous_model_dir;
    std::string current_model_dir;
    std::string target_model_dir;
    std::string message;
};

struct RuntimeRollbackFailureDetail {
    std::string capability_id;
    std::string rollback_reason;
    std::string rollback_failed_stage;
    std::string previous_model_dir;
    std::string current_model_dir;
    std::string target_model_dir;
    std::string message;
};

struct RuntimeReloadResult {
    bool ok = false;
    bool rolled_back = false;
    bool restored_previous_state = false;
    bool rollback_performed = false;
    bool reloaded_all = false;
    bool rollback_all = false;
    std::string capability_id;
    std::string reload_type;
    std::string previous_model_dir;
    std::string current_model_dir;
    std::string target_model_dir;
    std::string rollback_source_model_dir;
    std::string rollback_target_model_dir;
    std::string rollback_reason;
    std::string rollback_failed_stage;
    std::string current_stage;
    std::string message;
    std::vector<std::string> rolled_back_capability_ids;
    std::vector<std::string> reloaded_capability_ids;
    std::vector<std::string> failed_capability_ids;
    std::vector<RuntimeReloadFailureDetail> reload_failure_details;
    std::vector<RuntimeRollbackFailureDetail> rollback_failure_details;
};

struct CapabilityMetricsInfo {
    std::string capability_id;
    std::size_t request_count = 0;
    std::size_t success_count = 0;
    std::size_t failure_count = 0;
    std::size_t busy_reject_count = 0;
    double total_cost_ms = 0.0;
    double avg_cost_ms = 0.0;
    std::int64_t last_request_timestamp = 0;
    std::int64_t last_success_timestamp = 0;
    std::int64_t last_failure_timestamp = 0;
    int last_error_code = 0;
};

struct CapabilityInfo {
    std::string capability_id;
    std::string name;
    std::string version;
    std::string model_version;
    std::string model_dir;
    std::string description;
    std::string library_path;
    std::string configured_device;
    int max_batch_size = 1;
    std::string device;
    std::string status;
    std::size_t pool_size = 0;
    std::size_t busy_count = 0;
    bool ready = false;
    bool draining = false;
};

struct RuntimeDiagnosticsInfo {
    bool initialized = false;
    std::size_t capability_count = 0;
    std::size_t ready_capability_count = 0;
    std::size_t draining_capability_count = 0;
    std::size_t total_pool_size = 0;
    std::size_t total_busy_count = 0;
    PluginLoadDiagnostics plugin_load{};
    std::vector<CapabilityInfo> capabilities;
    std::vector<CapabilityMetricsInfo> metrics;
};

class AiRuntime {
public:
    AiRuntime();
    ~AiRuntime();

    bool initialize();
    RuntimeReloadResult reload_capability(const std::string& capability_id, RuntimeReloadType reload_type = RuntimeReloadType::kAll, const std::string& target_model_dir = std::string());
    RuntimeReloadResult reload_all_capabilities(RuntimeReloadType reload_type = RuntimeReloadType::kAll, const std::string& target_model_dir = std::string());
    RuntimeReloadResult rollback_capability(const std::string& capability_id);
    RuntimeReloadResult rollback_all_capabilities();
    InferResult infer(const InferRequest& request);
    std::size_t capability_count() const;
    std::vector<CapabilityInfo> list_capabilities() const;
    std::vector<CapabilityMetricsInfo> list_metrics() const;
    RuntimeDiagnosticsInfo get_diagnostics() const;

private:
    void record_request_metric(const std::string& capability_id, std::int64_t timestamp);
    void record_busy_reject_metric(const std::string& capability_id);
    void record_infer_result_metric(const std::string& capability_id, int code, double cost_ms, std::int64_t timestamp);

    PluginManager plugin_manager_;
    PoolManager pool_manager_;
    std::unique_ptr<ReloadController> reload_controller_;
    mutable std::mutex metrics_mutex_;
    std::unordered_map<std::string, CapabilityMetricsInfo> metrics_by_capability_;
    bool initialized_ = false;
};

}

#endif
