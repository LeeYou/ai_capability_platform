#ifndef AI_CAPABILITY_PLATFORM_APPS_AI_PROD_CPP_PLUGIN_EXECUTOR_H
#define AI_CAPABILITY_PLATFORM_APPS_AI_PROD_CPP_PLUGIN_EXECUTOR_H

#include "capability_catalog.h"

#include "ai_platform/ai_plugin_api.h"
#include <nlohmann/json.hpp>

#include <map>
#include <mutex>
#include <string>
#include <unordered_map>
#include <vector>

struct PluginExecutionResult {
    nlohmann::json plugin_result = nlohmann::json::object();
    double infer_time_ms = 0.0;
};

class PluginExecutor {
public:
    PluginExecutor();
    ~PluginExecutor();

    void SyncEntries(const std::vector<CapabilityCatalogEntry>& entries);
    bool Execute(
        const CapabilityCatalogEntry& entry,
        std::size_t slot_index,
        const std::string& input_type,
        const std::string& payload,
        const nlohmann::json& options,
        const std::string& device,
        const std::string& request_id,
        PluginExecutionResult* result,
        std::string* error_message);

private:
    struct PluginBinding {
        std::string capability_name;
        std::string cache_key;
        std::string binary_path;
        std::string model_root;
        std::string device;
        int pool_size = 1;
        void* library_handle = nullptr;
        fn_ai_plugin_destroy destroy = nullptr;
        fn_ai_plugin_infer infer = nullptr;
        fn_ai_plugin_free_result free_result = nullptr;
        fn_ai_plugin_get_info get_info = nullptr;
        std::vector<AiPluginHandle> plugin_handles;
        int total_execute_count = 0;
        int failed_execute_count = 0;
        std::string last_request_id;
        std::string last_error_message;
    };

    bool EnsureBindingLoaded(
        const CapabilityCatalogEntry& entry,
        const std::string& device,
        PluginBinding** binding,
        std::string* error_message);
    static std::string BuildCacheKey(const std::string& capability_name, const std::string& device);
    static void UnloadBinding(PluginBinding* binding);

    std::mutex mutex;
    std::unordered_map<std::string, PluginBinding> bindings;
};

#endif
