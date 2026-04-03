#ifndef AI_PLATFORM_PLUGIN_MANAGER_H
#define AI_PLATFORM_PLUGIN_MANAGER_H

#include "ai_platform/ai_plugin_api.h"

#include <string>
#include <unordered_map>
#include <vector>

namespace ai_platform {

enum class RuntimeReloadType {
    kAll,
    kPlugin,
    kModel
};

struct PluginReloadResult {
    bool ok = false;
    std::string capability_id;
    std::string reload_type;
    std::string previous_model_dir;
    std::string current_model_dir;
    std::string target_model_dir;
    std::string message;
};

struct PluginLoadFailureInfo {
    std::string capability_id;
    std::string library_path;
    std::string model_dir;
    std::string stage;
    std::string message;
};

struct PluginLoadDiagnostics {
    bool registry_opened = false;
    std::string registry_path;
    std::string last_error;
    std::size_t configured_count = 0;
    std::size_t loaded_count = 0;
    std::vector<std::string> loaded_capability_ids;
    std::vector<PluginLoadFailureInfo> failures;
};

struct PluginRuntimeEntry {
    std::string capability_id;
    std::string library_path;
    std::string model_dir;
    std::string previous_model_dir;
    AiDeviceType device = AI_DEVICE_CPU;
    int max_batch_size = 1;
    int instance_count = 1;
    void* library_handle = nullptr;
    AiPluginHandle plugin_handle = nullptr;
    fn_ai_plugin_init init = nullptr;
    fn_ai_plugin_destroy destroy = nullptr;
    fn_ai_plugin_infer infer = nullptr;
    fn_ai_plugin_free_result free_result = nullptr;
    fn_ai_plugin_reload reload = nullptr;
    fn_ai_plugin_get_info get_info = nullptr;
    AiPluginInfo plugin_info{};
};

class PluginManager {
public:
    PluginManager();
    ~PluginManager();

    bool load_default_plugins();
    PluginReloadResult reload_plugin(const std::string& capability_id, RuntimeReloadType reload_type, const std::string& target_model_dir = std::string());
    std::vector<PluginReloadResult> reload_all(RuntimeReloadType reload_type, const std::string& target_model_dir = std::string());
    void unload_all();

    PluginRuntimeEntry* get_plugin(const std::string& capability_id);
    const PluginRuntimeEntry* get_plugin(const std::string& capability_id) const;
    const std::unordered_map<std::string, PluginRuntimeEntry>& plugins() const;
    PluginLoadDiagnostics get_load_diagnostics() const;

private:
    bool load_registry_plugins();
    bool load_plugin(const std::string& capability_id, const std::string& library_path, const std::string& model_dir, AiDeviceType device, int max_batch_size, int instance_count);
    std::string resolve_registry_path() const;

    std::unordered_map<std::string, PluginRuntimeEntry> plugins_;
    PluginLoadDiagnostics load_diagnostics_;
};

}

#endif
