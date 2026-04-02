#include "ai_runtime.h"

#include "app_paths.h"
#include "reload_controller.h"

#include <chrono>
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <sstream>
#include <thread>
#include <vector>

namespace ai_platform {

namespace {

std::string build_runtime_audit_timestamp() {
    const auto now = std::chrono::system_clock::now();
    const std::time_t now_time = std::chrono::system_clock::to_time_t(now);
    std::tm utc_time{};
#ifdef _WIN32
    gmtime_s(&utc_time, &now_time);
#else
    gmtime_r(&now_time, &utc_time);
#endif
    std::ostringstream oss;
    oss << std::put_time(&utc_time, "%Y-%m-%dT%H:%M:%SZ");
    return oss.str();
}

std::string to_reload_type_name(RuntimeReloadType reload_type) {
    switch (reload_type) {
        case RuntimeReloadType::kModel:
            return "model";
        case RuntimeReloadType::kPlugin:
            return "plugin";
        case RuntimeReloadType::kAll:
        default:
            return "all";
    }
}

void append_runtime_audit_log(const std::string& event_name, const RuntimeReloadResult& result) {
    const std::filesystem::path audit_log_path(app_paths().runtime_audit_log);
    const auto parent = audit_log_path.parent_path();
    if (!parent.empty()) {
        std::filesystem::create_directories(parent);
    }

    std::ofstream output(audit_log_path, std::ios::app);
    if (!output.is_open()) {
        return;
    }

    output << '[' << build_runtime_audit_timestamp() << "] [RUNTIME] event=" << event_name
           << " capability_id=" << result.capability_id
           << " reload_type=" << result.reload_type
           << " previous_model_dir=" << result.previous_model_dir
           << " current_model_dir=" << result.current_model_dir
           << " target_model_dir=" << result.target_model_dir
           << " rollback_performed=" << (result.rollback_performed ? "true" : "false")
           << " rollback_source_model_dir=" << result.rollback_source_model_dir
           << " rollback_target_model_dir=" << result.rollback_target_model_dir
           << " rollback_reason=" << result.rollback_reason
           << " rollback_failed_stage=" << result.rollback_failed_stage
           << " ok=" << (result.ok ? "true" : "false")
           << " rolled_back=" << (result.rolled_back ? "true" : "false")
           << " restored_previous_state=" << (result.restored_previous_state ? "true" : "false")
           << " reloaded_all=" << (result.reloaded_all ? "true" : "false")
           << " rollback_all=" << (result.rollback_all ? "true" : "false")
           << " rolled_back_count=" << result.rolled_back_capability_ids.size()
           << " reloaded_count=" << result.reloaded_capability_ids.size()
           << " failed_count=" << result.failed_capability_ids.size()
           << " message=" << result.message;

    if (!result.rolled_back_capability_ids.empty()) {
        output << " rolled_back_capability_ids=";
        for (std::size_t i = 0; i < result.rolled_back_capability_ids.size(); ++i) {
            if (i > 0) {
                output << ',';
            }
            output << result.rolled_back_capability_ids[i];
        }
    }
    if (!result.reloaded_capability_ids.empty()) {
        output << " reloaded_capability_ids=";
        for (std::size_t i = 0; i < result.reloaded_capability_ids.size(); ++i) {
            if (i > 0) {
                output << ',';
            }
            output << result.reloaded_capability_ids[i];
        }
    }
    if (!result.failed_capability_ids.empty()) {
        output << " failed_capability_ids=";
        for (std::size_t i = 0; i < result.failed_capability_ids.size(); ++i) {
            if (i > 0) {
                output << ',';
            }
            output << result.failed_capability_ids[i];
        }
    }
    if (!result.reload_failure_details.empty()) {
        output << " reload_failure_details=";
        for (std::size_t i = 0; i < result.reload_failure_details.size(); ++i) {
            if (i > 0) {
                output << ';';
            }
            const auto& detail = result.reload_failure_details[i];
            output << detail.capability_id << ':'
                   << detail.reload_reason << ':'
                   << detail.reload_failed_stage << ':'
                   << detail.current_model_dir << ':'
                   << detail.previous_model_dir << ':'
                   << detail.target_model_dir;
        }
    }
    if (!result.rollback_failure_details.empty()) {
        output << " rollback_failure_details=";
        for (std::size_t i = 0; i < result.rollback_failure_details.size(); ++i) {
            if (i > 0) {
                output << ';';
            }
            const auto& detail = result.rollback_failure_details[i];
            output << detail.capability_id << ':'
                   << detail.rollback_reason << ':'
                   << detail.rollback_failed_stage << ':'
                   << detail.current_model_dir << ':'
                   << detail.previous_model_dir << ':'
                   << detail.target_model_dir;
        }
    }
    output << std::endl;
}

}

AiRuntime::AiRuntime()
    : reload_controller_(std::make_unique<ReloadController>(plugin_manager_, pool_manager_)) {
}

AiRuntime::~AiRuntime() = default;

bool AiRuntime::initialize() {
    initialized_ = plugin_manager_.load_default_plugins();
    if (initialized_) {
        pool_manager_.rebuild(plugin_manager_.plugins());
        std::lock_guard<std::mutex> lock(metrics_mutex_);
        metrics_by_capability_.clear();
        for (const auto& pair : plugin_manager_.plugins()) {
            CapabilityMetricsInfo metrics;
            metrics.capability_id = pair.first;
            metrics_by_capability_[pair.first] = metrics;
        }
    }
    return initialized_;
}

RuntimeReloadResult AiRuntime::reload_capability(const std::string& capability_id, RuntimeReloadType reload_type, const std::string& target_model_dir) {
    if (!initialized_) {
        RuntimeReloadResult result;
        result.capability_id = capability_id;
        result.reload_type = to_reload_type_name(reload_type);
        result.target_model_dir = target_model_dir;
        result.current_stage = "prepare";
        result.message = "runtime not initialized";
        append_runtime_audit_log("reload_capability_failure", result);
        return result;
    }
    RuntimeReloadResult result = reload_controller_->reload_capability(capability_id, reload_type, target_model_dir);
    if (!result.ok) {
        append_runtime_audit_log("reload_capability_failure", result);
        return result;
    }
    append_runtime_audit_log("reload_capability_success", result);
    return result;
}

RuntimeReloadResult AiRuntime::reload_all_capabilities(RuntimeReloadType reload_type, const std::string& target_model_dir) {
    if (!initialized_) {
        RuntimeReloadResult result;
        result.reloaded_all = true;
        result.reload_type = to_reload_type_name(reload_type);
        result.target_model_dir = target_model_dir;
        result.current_stage = "prepare";
        result.message = "runtime not initialized";
        append_runtime_audit_log("reload_all_failure", result);
        return result;
    }
    RuntimeReloadResult result = reload_controller_->reload_all_capabilities(reload_type, target_model_dir);
    if (!result.ok) {
        append_runtime_audit_log("reload_all_failure", result);
        return result;
    }
    append_runtime_audit_log("reload_all_success", result);
    return result;
}

RuntimeReloadResult AiRuntime::rollback_capability(const std::string& capability_id) {
    RuntimeReloadResult result = reload_controller_->rollback_capability(capability_id);
    if (!result.ok) {
        append_runtime_audit_log("rollback_capability_failure", result);
        return result;
    }
    append_runtime_audit_log("rollback_capability_success", result);
    return result;
}

RuntimeReloadResult AiRuntime::rollback_all_capabilities() {
    if (!initialized_) {
        RuntimeReloadResult result;
        result.rollback_all = true;
        result.reload_type = to_reload_type_name(RuntimeReloadType::kModel);
        result.current_stage = "prepare";
        result.message = "runtime not initialized";
        append_runtime_audit_log("rollback_all_failure", result);
        return result;
    }
    RuntimeReloadResult result = reload_controller_->rollback_all_capabilities(list_capabilities());
    if (result.ok) {
        append_runtime_audit_log("rollback_all_success", result);
        return result;
    }
    if (!result.rolled_back_capability_ids.empty()) {
        append_runtime_audit_log("rollback_all_partial_failure", result);
        return result;
    }
    append_runtime_audit_log("rollback_all_failure", result);
    return result;
}

std::size_t AiRuntime::capability_count() const {
    return plugin_manager_.plugins().size();
}

InferResult AiRuntime::infer(const InferRequest& request) {
    InferResult result;
    result.request_id = request.request_id;
    record_request_metric(request.capability_id, request.timestamp);

    auto* pool = pool_manager_.get_pool(request.capability_id);
    if (!initialized_ || pool == nullptr) {
        result.code = -200;
        result.message = "capability not found";
        result.data_json = "null";
        result.cost_ms = 0.0;
        record_infer_result_metric(request.capability_id, result.code, result.cost_ms, request.timestamp);
        return result;
    }

    const auto lease = pool->acquire();
    auto* plugin = lease.plugin;
    if (plugin == nullptr) {
        result.code = -201;
        result.message = "capability busy";
        result.data_json = "null";
        result.cost_ms = 0.0;
        record_busy_reject_metric(request.capability_id);
        record_infer_result_metric(request.capability_id, result.code, result.cost_ms, request.timestamp);
        return result;
    }

    AiPluginInput input{};
    std::vector<AiImage> plugin_images;

    if (!request.images.empty()) {
        plugin_images.reserve(request.images.size());
        for (const auto& image : request.images) {
            AiImage plugin_image{};
            plugin_image.data = image.data.empty() ? nullptr : image.data.data();
            plugin_image.data_size = image.data.size();
            plugin_images.push_back(plugin_image);
        }
        input.images = plugin_images.data();
        input.image_count = static_cast<int>(plugin_images.size());
        input.media_type = (request.capability_id == "liveness_action" && request.images.size() > 1)
            ? AI_MEDIA_TYPE_FRAME_SEQUENCE
            : AI_MEDIA_TYPE_IMAGE;
    } else {
        input.images = nullptr;
        input.image_count = 0;
        input.media_type = request.media.empty() ? AI_MEDIA_TYPE_IMAGE : AI_MEDIA_TYPE_VIDEO;
    }

    if (!request.media.empty()) {
        const auto& media = request.media.front();
        input.media_data = media.data.empty() ? nullptr : media.data.data();
        input.media_size = media.data.size();
        input.media_format = media.format.empty() ? nullptr : media.format.c_str();
        if (media.media_type == "video") {
            input.media_type = AI_MEDIA_TYPE_VIDEO;
        }
    } else {
        input.media_data = nullptr;
        input.media_size = 0;
        input.media_format = nullptr;
    }

    input.params_json = request.params_json.c_str();

    AiPluginOutput output{};
    const int rc = plugin->infer(plugin->plugin_handle, &input, &output);
    result.code = rc;
    result.message = (rc == 0) ? "success" : "plugin infer failed";
    result.data_json = output.result_json ? output.result_json : "null";
    result.cost_ms = output.infer_time_ms;

    if (plugin->free_result != nullptr) {
        plugin->free_result(&output);
    }
    pool->release(lease);
    record_infer_result_metric(request.capability_id, result.code, result.cost_ms, request.timestamp);
    return result;
}

std::vector<CapabilityInfo> AiRuntime::list_capabilities() const {
    std::vector<CapabilityInfo> capabilities;
    for (const auto& pair : plugin_manager_.plugins()) {
        const auto& plugin = pair.second;
        const auto* pool = pool_manager_.get_pool(plugin.capability_id);
        const std::size_t pool_size = (pool == nullptr) ? 0U : pool->size();
        const std::size_t busy_count = (pool == nullptr) ? 0U : pool->busy_count();
        const bool ready = pool != nullptr && pool->is_ready();
        const bool draining = pool != nullptr && pool->is_draining();
        capabilities.push_back({
            plugin.capability_id,
            plugin.plugin_info.capability_name ? plugin.plugin_info.capability_name : plugin.capability_id,
            plugin.plugin_info.version ? plugin.plugin_info.version : "unknown",
            plugin.plugin_info.model_version ? plugin.plugin_info.model_version : "unknown",
            plugin.model_dir,
            plugin.plugin_info.description ? plugin.plugin_info.description : "",
            plugin.library_path,
            plugin.device == AI_DEVICE_CUDA ? "cuda" : "cpu",
            plugin.max_batch_size,
            plugin.plugin_info.current_device == AI_DEVICE_CUDA ? "cuda" : "cpu",
            draining ? "draining" : (ready ? "ready" : "not_ready"),
            pool_size,
            busy_count,
            ready,
            draining
        });
    }
    return capabilities;
}

std::vector<CapabilityMetricsInfo> AiRuntime::list_metrics() const {
    std::lock_guard<std::mutex> lock(metrics_mutex_);
    std::vector<CapabilityMetricsInfo> metrics;
    metrics.reserve(metrics_by_capability_.size());
    for (const auto& pair : metrics_by_capability_) {
        metrics.push_back(pair.second);
    }
    return metrics;
}

RuntimeDiagnosticsInfo AiRuntime::get_diagnostics() const {
    RuntimeDiagnosticsInfo diagnostics;
    diagnostics.initialized = initialized_;
    diagnostics.plugin_load = plugin_manager_.get_load_diagnostics();
    diagnostics.capabilities = list_capabilities();
    diagnostics.metrics = list_metrics();
    diagnostics.capability_count = diagnostics.capabilities.size();
    for (const auto& capability : diagnostics.capabilities) {
        diagnostics.total_pool_size += capability.pool_size;
        diagnostics.total_busy_count += capability.busy_count;
        if (capability.ready) {
            ++diagnostics.ready_capability_count;
        }
        if (capability.draining) {
            ++diagnostics.draining_capability_count;
        }
    }
    return diagnostics;
}

void AiRuntime::record_request_metric(const std::string& capability_id, std::int64_t timestamp) {
    std::lock_guard<std::mutex> lock(metrics_mutex_);
    auto& metrics = metrics_by_capability_[capability_id];
    metrics.capability_id = capability_id;
    ++metrics.request_count;
    metrics.last_request_timestamp = timestamp;
}

void AiRuntime::record_busy_reject_metric(const std::string& capability_id) {
    std::lock_guard<std::mutex> lock(metrics_mutex_);
    auto& metrics = metrics_by_capability_[capability_id];
    metrics.capability_id = capability_id;
    ++metrics.busy_reject_count;
}

void AiRuntime::record_infer_result_metric(const std::string& capability_id, int code, double cost_ms, std::int64_t timestamp) {
    std::lock_guard<std::mutex> lock(metrics_mutex_);
    auto& metrics = metrics_by_capability_[capability_id];
    metrics.capability_id = capability_id;
    if (code == 0) {
        ++metrics.success_count;
        metrics.last_success_timestamp = timestamp;
    } else {
        ++metrics.failure_count;
        metrics.last_failure_timestamp = timestamp;
        metrics.last_error_code = code;
    }
    metrics.total_cost_ms += cost_ms;
    if (metrics.success_count > 0) {
        metrics.avg_cost_ms = metrics.total_cost_ms / static_cast<double>(metrics.success_count);
    }
}

}
