#include "reload_controller.h"

#include <chrono>
#include <thread>

namespace ai_platform {

namespace {

constexpr int kDrainWaitRetryCount = 20;
constexpr auto kDrainWaitInterval = std::chrono::milliseconds(50);

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

bool wait_for_pool_drain(const PoolManager& pool_manager, const std::string& capability_id) {
    for (int i = 0; i < kDrainWaitRetryCount; ++i) {
        if (pool_manager.can_drain(capability_id)) {
            return true;
        }
        std::this_thread::sleep_for(kDrainWaitInterval);
    }
    return pool_manager.can_drain(capability_id);
}

bool wait_for_all_pools_drain(const PoolManager& pool_manager) {
    for (int i = 0; i < kDrainWaitRetryCount; ++i) {
        if (pool_manager.can_drain_all()) {
            return true;
        }
        std::this_thread::sleep_for(kDrainWaitInterval);
    }
    return pool_manager.can_drain_all();
}

}

ReloadController::ReloadController(PluginManager& plugin_manager, PoolManager& pool_manager)
    : plugin_manager_(plugin_manager), pool_manager_(pool_manager) {
}

RuntimeReloadResult ReloadController::build_reload_failure_result(const std::string& capability_id,
                                                                  RuntimeReloadType reload_type,
                                                                  const std::string& target_model_dir,
                                                                  const std::string& current_stage,
                                                                  const std::string& message) const {
    RuntimeReloadResult result;
    result.capability_id = capability_id;
    result.reload_type = to_reload_type_name(reload_type);
    result.target_model_dir = target_model_dir;
    result.current_stage = current_stage;
    result.message = message;
    return result;
}

RuntimeReloadResult ReloadController::reload_capability(const std::string& capability_id,
                                                        RuntimeReloadType reload_type,
                                                        const std::string& target_model_dir) const {
    RuntimeReloadResult result;
    result.capability_id = capability_id;
    result.reload_type = to_reload_type_name(reload_type);
    result.target_model_dir = target_model_dir;
    result.current_stage = "prepare";

    if (!pool_manager_.begin_drain(capability_id)) {
        result.message = "capability not found";
        return result;
    }

    result.current_stage = "drain";
    if (!wait_for_pool_drain(pool_manager_, capability_id)) {
        pool_manager_.end_drain(capability_id);
        result.message = "capability drain timeout";
        return result;
    }

    result.current_stage = "reload";
    const PluginReloadResult plugin_result = plugin_manager_.reload_plugin(capability_id, reload_type, target_model_dir);
    if (!plugin_result.ok) {
        pool_manager_.end_drain(capability_id);
        result.rolled_back = true;
        result.restored_previous_state = true;
        result.previous_model_dir = plugin_result.previous_model_dir;
        result.current_model_dir = plugin_result.current_model_dir;
        result.target_model_dir = plugin_result.target_model_dir;
        result.message = plugin_result.message;
        result.failed_capability_ids.push_back(capability_id);
        RuntimeReloadFailureDetail failure_detail;
        failure_detail.capability_id = capability_id;
        failure_detail.reload_reason = "reload_failed";
        failure_detail.reload_failed_stage = "reload";
        failure_detail.previous_model_dir = plugin_result.previous_model_dir;
        failure_detail.current_model_dir = plugin_result.current_model_dir;
        failure_detail.target_model_dir = plugin_result.target_model_dir;
        failure_detail.message = plugin_result.message;
        result.reload_failure_details.push_back(failure_detail);
        return result;
    }

    result.current_stage = "complete";
    pool_manager_.rebuild(plugin_manager_.plugins());
    result.ok = true;
    result.previous_model_dir = plugin_result.previous_model_dir;
    result.current_model_dir = plugin_result.current_model_dir;
    result.target_model_dir = plugin_result.target_model_dir;
    result.message = plugin_result.message;
    result.reloaded_capability_ids.push_back(capability_id);
    return result;
}

RuntimeReloadResult ReloadController::reload_all_capabilities(RuntimeReloadType reload_type, const std::string& target_model_dir) const {
    RuntimeReloadResult result;
    result.reloaded_all = true;
    result.reload_type = to_reload_type_name(reload_type);
    result.target_model_dir = target_model_dir;
    result.current_stage = "prepare";

    if (!pool_manager_.begin_drain_all()) {
        result.message = "no capability available";
        return result;
    }

    result.current_stage = "drain";
    if (!wait_for_all_pools_drain(pool_manager_)) {
        pool_manager_.end_drain_all();
        result.message = "capability drain timeout";
        return result;
    }

    result.current_stage = "reload";
    const std::vector<PluginReloadResult> plugin_results = plugin_manager_.reload_all(reload_type, target_model_dir);
    bool all_ok = true;
    for (const auto& plugin_result : plugin_results) {
        if (plugin_result.ok) {
            result.reloaded_capability_ids.push_back(plugin_result.capability_id);
        } else {
            all_ok = false;
            result.failed_capability_ids.push_back(plugin_result.capability_id);
            RuntimeReloadFailureDetail failure_detail;
            failure_detail.capability_id = plugin_result.capability_id;
            failure_detail.reload_reason = "reload_failed";
            failure_detail.reload_failed_stage = "reload";
            failure_detail.previous_model_dir = plugin_result.previous_model_dir;
            failure_detail.current_model_dir = plugin_result.current_model_dir;
            failure_detail.target_model_dir = plugin_result.target_model_dir;
            failure_detail.message = plugin_result.message;
            result.reload_failure_details.push_back(failure_detail);
        }
    }

    if (!all_ok) {
        pool_manager_.end_drain_all();
        result.rolled_back = true;
        result.restored_previous_state = true;
        result.message = "partial reload failed";
        return result;
    }

    result.current_stage = "complete";
    pool_manager_.rebuild(plugin_manager_.plugins());
    result.ok = true;
    if (!plugin_results.empty()) {
        result.previous_model_dir = plugin_results.front().previous_model_dir;
        result.current_model_dir = plugin_results.front().current_model_dir;
        result.target_model_dir = plugin_results.front().target_model_dir;
    }
    result.message = "all capabilities reloaded";
    return result;
}

RuntimeReloadResult ReloadController::rollback_capability(const std::string& capability_id) const {
    RuntimeReloadResult result;
    result.capability_id = capability_id;
    result.reload_type = to_reload_type_name(RuntimeReloadType::kModel);
    result.current_stage = "prepare";

    const PluginRuntimeEntry* plugin = plugin_manager_.get_plugin(capability_id);
    if (plugin == nullptr) {
        result.rollback_reason = "capability_not_found";
        result.rollback_failed_stage = "lookup";
        result.message = "capability not found";
        return result;
    }

    const std::string rollback_source_model_dir = plugin->model_dir;
    const std::string rollback_target_model_dir = plugin->previous_model_dir;
    result.current_model_dir = rollback_source_model_dir;
    result.previous_model_dir = rollback_target_model_dir;
    result.target_model_dir = rollback_target_model_dir;
    result.rollback_source_model_dir = rollback_source_model_dir;
    result.rollback_target_model_dir = rollback_target_model_dir;

    if (plugin->previous_model_dir.empty()) {
        result.rollback_reason = "previous_model_dir_unavailable";
        result.rollback_failed_stage = "prepare";
        result.message = "previous model dir not available";
        return result;
    }

    result = reload_capability(capability_id, RuntimeReloadType::kModel, rollback_target_model_dir);
    if (!result.ok) {
        result.rollback_reason = "reload_failed";
        result.rollback_failed_stage = "reload";
        result.rollback_source_model_dir = rollback_source_model_dir;
        result.rollback_target_model_dir = rollback_target_model_dir;
        return result;
    }

    result.current_stage = "complete";
    result.rollback_performed = true;
    result.restored_previous_state = true;
    result.previous_model_dir = rollback_source_model_dir;
    result.current_model_dir = rollback_target_model_dir;
    result.target_model_dir = rollback_target_model_dir;
    result.rollback_source_model_dir = rollback_source_model_dir;
    result.rollback_target_model_dir = rollback_target_model_dir;
    result.rollback_reason.clear();
    result.rollback_failed_stage.clear();
    result.message = "rollback completed";
    return result;
}

RuntimeReloadResult ReloadController::rollback_all_capabilities(const std::vector<CapabilityInfo>& capabilities) const {
    RuntimeReloadResult result;
    result.rollback_all = true;
    result.reload_type = to_reload_type_name(RuntimeReloadType::kModel);
    result.current_stage = "prepare";

    if (capabilities.empty()) {
        result.message = "no capability available";
        return result;
    }

    for (const auto& capability : capabilities) {
        const RuntimeReloadResult rollback_result = rollback_capability(capability.capability_id);
        if (rollback_result.ok) {
            result.rolled_back_capability_ids.push_back(capability.capability_id);
            continue;
        }

        result.failed_capability_ids.push_back(capability.capability_id);
        RuntimeRollbackFailureDetail failure_detail;
        failure_detail.capability_id = capability.capability_id;
        failure_detail.rollback_reason = rollback_result.rollback_reason;
        failure_detail.rollback_failed_stage = rollback_result.rollback_failed_stage;
        failure_detail.previous_model_dir = rollback_result.previous_model_dir;
        failure_detail.current_model_dir = rollback_result.current_model_dir;
        failure_detail.target_model_dir = rollback_result.target_model_dir;
        failure_detail.message = rollback_result.message;
        result.rollback_failure_details.push_back(failure_detail);
        if (result.rollback_reason.empty()) {
            result.rollback_reason = rollback_result.rollback_reason;
        }
        if (result.rollback_failed_stage.empty()) {
            result.rollback_failed_stage = rollback_result.rollback_failed_stage;
        }
    }

    result.current_stage = "complete";
    result.rollback_performed = !result.rolled_back_capability_ids.empty();
    result.rolled_back = result.rollback_performed;
    result.ok = result.failed_capability_ids.empty();
    result.restored_previous_state = result.ok;
    if (result.ok) {
        result.message = "all capabilities rolled back";
        return result;
    }
    if (!result.rolled_back_capability_ids.empty()) {
        result.message = "partial rollback failed";
        return result;
    }
    result.message = "rollback all failed";
    return result;
}

}
