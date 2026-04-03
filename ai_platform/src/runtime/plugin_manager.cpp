#include "plugin_manager.h"

#include "app_paths.h"
#include "model_package.h"

#ifdef _WIN32
#include <windows.h>
#else
#include <dlfcn.h>
#endif

#include <cstring>
#include <filesystem>
#include <fstream>
#include <iostream>

#include <cctype>

namespace ai_platform {

namespace {

constexpr const char* kTestReloadFailPrefix = "__test_fail_reload__:";

PluginLoadFailureInfo build_load_failure(const std::string& capability_id,
                                         const std::string& library_path,
                                         const std::string& model_dir,
                                         const std::string& stage,
                                         const std::string& message) {
    PluginLoadFailureInfo failure;
    failure.capability_id = capability_id;
    failure.library_path = library_path;
    failure.model_dir = model_dir;
    failure.stage = stage;
    failure.message = message;
    return failure;
}

std::string trim_copy(const std::string& value) {
    std::size_t start = 0;
    while (start < value.size() && std::isspace(static_cast<unsigned char>(value[start])) != 0) {
        ++start;
    }

    std::size_t end = value.size();
    while (end > start && std::isspace(static_cast<unsigned char>(value[end - 1])) != 0) {
        --end;
    }

    return value.substr(start, end - start);
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

bool is_test_reload_fail_target(const std::string& target_model_dir) {
    return target_model_dir.rfind(kTestReloadFailPrefix, 0) == 0;
}

std::string get_test_reload_fail_capability_id(const std::string& target_model_dir) {
    if (!is_test_reload_fail_target(target_model_dir)) {
        return std::string();
    }
    return target_model_dir.substr(std::strlen(kTestReloadFailPrefix));
}

std::string resolve_model_dir_for_reload_target(const std::string& capability_id,
                                                const std::string& current_model_dir,
                                                const std::string& requested_target_model_dir,
                                                bool* used_capability_subdir,
                                                ModelPackageValidationResult* validation_result) {
    *used_capability_subdir = false;
    const std::string candidate_model_dir = requested_target_model_dir.empty() ? current_model_dir : requested_target_model_dir;
    *validation_result = validate_model_package(capability_id, candidate_model_dir);
    if (validation_result->ok || requested_target_model_dir.empty()) {
        return candidate_model_dir;
    }

    const std::filesystem::path capability_subdir = std::filesystem::path(requested_target_model_dir) / capability_id;
    *validation_result = validate_model_package(capability_id, capability_subdir.string());
    if (validation_result->ok) {
        *used_capability_subdir = true;
        return capability_subdir.string();
    }

    return candidate_model_dir;
}

}

PluginManager::PluginManager() = default;

PluginManager::~PluginManager() {
    unload_all();
}

bool PluginManager::load_default_plugins() {
    unload_all();
    load_diagnostics_ = PluginLoadDiagnostics{};
    load_diagnostics_.registry_path = resolve_registry_path();
    return load_registry_plugins();
}

PluginReloadResult PluginManager::reload_plugin(const std::string& capability_id, RuntimeReloadType reload_type, const std::string& target_model_dir) {
    auto* plugin = get_plugin(capability_id);
    if (plugin == nullptr) {
        std::cerr << "PluginManager: reload failed, capability not found: " << capability_id << std::endl;
        return PluginReloadResult{false, capability_id, to_reload_type_name(reload_type), std::string(), std::string(), target_model_dir, "capability not found"};
    }
    if (plugin->reload == nullptr || plugin->plugin_handle == nullptr) {
        std::cerr << "PluginManager: reload not supported for capability: " << capability_id << std::endl;
        return PluginReloadResult{false, capability_id, to_reload_type_name(reload_type), plugin->previous_model_dir, plugin->model_dir, target_model_dir, "plugin reload not supported"};
    }

    const bool is_test_fail_target = is_test_reload_fail_target(target_model_dir);
    const std::string test_fail_capability_id = get_test_reload_fail_capability_id(target_model_dir);
    if (is_test_fail_target && test_fail_capability_id == capability_id) {
        std::cerr << "PluginManager: reload failed by test failpoint for capability: " << capability_id << std::endl;
        return PluginReloadResult{false, capability_id, to_reload_type_name(reload_type), plugin->previous_model_dir, plugin->model_dir, target_model_dir, "plugin reload returned non-zero"};
    }

    const std::string previous_model_dir = plugin->model_dir;
    const bool ignore_test_fail_target_model_dir = is_test_fail_target && test_fail_capability_id != capability_id;
    const std::string effective_target_model_dir = ignore_test_fail_target_model_dir ? std::string() : target_model_dir;
    ModelPackageValidationResult validation_result;
    bool used_capability_subdir = false;
    const std::string effective_model_dir = resolve_model_dir_for_reload_target(
        capability_id,
        plugin->model_dir,
        effective_target_model_dir,
        &used_capability_subdir,
        &validation_result);
    const bool model_dir_changed = !effective_target_model_dir.empty() && effective_model_dir != plugin->model_dir;
    if (reload_type == RuntimeReloadType::kModel || reload_type == RuntimeReloadType::kAll) {
        if (!validation_result.ok) {
            std::cerr << "PluginManager: reload failed model package validation for capability: " << capability_id << std::endl;
            return PluginReloadResult{false, capability_id, to_reload_type_name(reload_type), plugin->previous_model_dir, plugin->model_dir, effective_target_model_dir, "model package validation failed: " + validation_result.message};
        }
    }
    const char* reload_model_dir = nullptr;
    if (reload_type == RuntimeReloadType::kModel || reload_type == RuntimeReloadType::kAll) {
        reload_model_dir = effective_model_dir.c_str();
    }

    const int rc = plugin->reload(plugin->plugin_handle, reload_model_dir);
    if (rc != 0) {
        std::cerr << "PluginManager: reload failed for capability: " << capability_id << std::endl;
        return PluginReloadResult{false, capability_id, to_reload_type_name(reload_type), plugin->previous_model_dir, previous_model_dir, effective_target_model_dir, "plugin reload returned non-zero"};
    }
    if (reload_model_dir != nullptr) {
        if (model_dir_changed) {
            plugin->previous_model_dir = previous_model_dir;
        }
        plugin->model_dir = reload_model_dir;
    }
    if (plugin->get_info != nullptr) {
        std::memset(&plugin->plugin_info, 0, sizeof(plugin->plugin_info));
        plugin->get_info(plugin->plugin_handle, &plugin->plugin_info);
    }
    std::cout << "PluginManager: reloaded capability " << capability_id << std::endl;
    return PluginReloadResult{true, capability_id, to_reload_type_name(reload_type), plugin->previous_model_dir, plugin->model_dir, effective_target_model_dir, to_reload_type_name(reload_type) + " reloaded"};
}

std::vector<PluginReloadResult> PluginManager::reload_all(RuntimeReloadType reload_type, const std::string& target_model_dir) {
    std::vector<PluginReloadResult> results;
    results.reserve(plugins_.size());
    for (const auto& pair : plugins_) {
        results.push_back(reload_plugin(pair.first, reload_type, target_model_dir));
    }
    return results;
}

void PluginManager::unload_all() {
    for (auto& pair : plugins_) {
        auto& plugin = pair.second;
        if (plugin.destroy != nullptr && plugin.plugin_handle != nullptr) {
            plugin.destroy(plugin.plugin_handle);
            plugin.plugin_handle = nullptr;
        }
        if (plugin.library_handle != nullptr) {
#ifdef _WIN32
            FreeLibrary(static_cast<HMODULE>(plugin.library_handle));
#else
            dlclose(plugin.library_handle);
#endif
            plugin.library_handle = nullptr;
        }
    }
    plugins_.clear();
}

PluginRuntimeEntry* PluginManager::get_plugin(const std::string& capability_id) {
    const auto it = plugins_.find(capability_id);
    if (it == plugins_.end()) {
        return nullptr;
    }
    return &it->second;
}

const PluginRuntimeEntry* PluginManager::get_plugin(const std::string& capability_id) const {
    const auto it = plugins_.find(capability_id);
    if (it == plugins_.end()) {
        return nullptr;
    }
    return &it->second;
}

const std::unordered_map<std::string, PluginRuntimeEntry>& PluginManager::plugins() const {
    return plugins_;
}

PluginLoadDiagnostics PluginManager::get_load_diagnostics() const {
    return load_diagnostics_;
}

bool PluginManager::load_registry_plugins() {
    load_diagnostics_.registry_path = resolve_registry_path();
    std::ifstream registry_file(load_diagnostics_.registry_path);
    if (!registry_file.is_open()) {
        load_diagnostics_.last_error = "failed to open registry file";
        std::cerr << "PluginManager: failed to open registry file: " << load_diagnostics_.registry_path << std::endl;
        return false;
    }

    load_diagnostics_.registry_opened = true;

    bool loaded_any = false;
    std::string line;
    while (std::getline(registry_file, line)) {
        if (line.empty() || line[0] == '#') {
            continue;
        }
        const auto delimiter = line.find('=');
        if (delimiter == std::string::npos) {
            std::cerr << "PluginManager: skip invalid registry line: " << line << std::endl;
            continue;
        }
        const std::string capability_id = trim_copy(line.substr(0, delimiter));
        const std::string config_value = trim_copy(line.substr(delimiter + 1));
        ++load_diagnostics_.configured_count;
        std::vector<std::string> parts;
        std::size_t start = 0;
        while (start <= config_value.size()) {
            const auto next = config_value.find('|', start);
            if (next == std::string::npos) {
                parts.push_back(trim_copy(config_value.substr(start)));
                break;
            }
            parts.push_back(trim_copy(config_value.substr(start, next - start)));
            start = next + 1;
        }

        const std::string library_path = parts.empty() ? "" : parts[0];
        const std::string model_dir = parts.size() > 1 && !parts[1].empty() ? parts[1] : ("models/" + capability_id);
        const AiDeviceType device = (parts.size() > 2 && parts[2] == "cuda") ? AI_DEVICE_CUDA : AI_DEVICE_CPU;
        const int max_batch_size = (parts.size() > 3 && !parts[3].empty()) ? std::stoi(parts[3]) : 1;
        const int instance_count = (parts.size() > 4 && !parts[4].empty()) ? std::stoi(parts[4]) : 1;
        const bool loaded = load_plugin(capability_id, library_path, model_dir, device, max_batch_size, instance_count);
        if (loaded) {
            loaded_any = true;
            ++load_diagnostics_.loaded_count;
            load_diagnostics_.loaded_capability_ids.push_back(capability_id);
        }
    }

    if (!loaded_any) {
        if (load_diagnostics_.last_error.empty()) {
            load_diagnostics_.last_error = "no plugin loaded from registry";
        }
        std::cerr << "PluginManager: no plugin loaded from registry" << std::endl;
    }
    return loaded_any;
}

bool PluginManager::load_plugin(const std::string& capability_id, const std::string& library_path, const std::string& model_dir, AiDeviceType device, int max_batch_size, int instance_count) {
    PluginRuntimeEntry plugin;
    plugin.capability_id = capability_id;
    plugin.library_path = library_path;
    plugin.model_dir = model_dir;
    plugin.previous_model_dir.clear();
    plugin.device = device;
    plugin.max_batch_size = max_batch_size;
    plugin.instance_count = instance_count > 0 ? instance_count : 1;
    if (plugin.library_path.empty()) {
        load_diagnostics_.last_error = "empty library path";
        load_diagnostics_.failures.push_back(build_load_failure(capability_id, library_path, model_dir, "validate", "empty library path"));
        std::cerr << "PluginManager: empty library path for capability: " << capability_id << std::endl;
        return false;
    }

    const ModelPackageValidationResult validation_result = validate_model_package(capability_id, plugin.model_dir);
    if (!validation_result.ok) {
        load_diagnostics_.last_error = "model package validation failed";
        load_diagnostics_.failures.push_back(build_load_failure(capability_id, library_path, model_dir, "validate_model_package", validation_result.message));
        std::cerr << "PluginManager: model package validation failed for capability " << capability_id << ": " << validation_result.message << std::endl;
        return false;
    }

#ifdef _WIN32
    HMODULE module = LoadLibraryA(plugin.library_path.c_str());
    if (module == nullptr) {
        load_diagnostics_.last_error = "failed to load library";
        load_diagnostics_.failures.push_back(build_load_failure(capability_id, library_path, model_dir, "load_library", "failed to load library"));
        std::cerr << "PluginManager: failed to load library for capability " << capability_id << ": " << plugin.library_path << std::endl;
        return false;
    }
    plugin.library_handle = module;
    plugin.init = reinterpret_cast<fn_ai_plugin_init>(GetProcAddress(module, "ai_plugin_init"));
    plugin.destroy = reinterpret_cast<fn_ai_plugin_destroy>(GetProcAddress(module, "ai_plugin_destroy"));
    plugin.infer = reinterpret_cast<fn_ai_plugin_infer>(GetProcAddress(module, "ai_plugin_infer"));
    plugin.free_result = reinterpret_cast<fn_ai_plugin_free_result>(GetProcAddress(module, "ai_plugin_free_result"));
    plugin.reload = reinterpret_cast<fn_ai_plugin_reload>(GetProcAddress(module, "ai_plugin_reload"));
    plugin.get_info = reinterpret_cast<fn_ai_plugin_get_info>(GetProcAddress(module, "ai_plugin_get_info"));
#else
    void* module = dlopen(plugin.library_path.c_str(), RTLD_LAZY);
    if (module == nullptr) {
        load_diagnostics_.last_error = "failed to load library";
        load_diagnostics_.failures.push_back(build_load_failure(capability_id, library_path, model_dir, "load_library", "failed to load library"));
        std::cerr << "PluginManager: failed to load library for capability " << capability_id << ": " << plugin.library_path << std::endl;
        return false;
    }
    plugin.library_handle = module;
    plugin.init = reinterpret_cast<fn_ai_plugin_init>(dlsym(module, "ai_plugin_init"));
    plugin.destroy = reinterpret_cast<fn_ai_plugin_destroy>(dlsym(module, "ai_plugin_destroy"));
    plugin.infer = reinterpret_cast<fn_ai_plugin_infer>(dlsym(module, "ai_plugin_infer"));
    plugin.free_result = reinterpret_cast<fn_ai_plugin_free_result>(dlsym(module, "ai_plugin_free_result"));
    plugin.reload = reinterpret_cast<fn_ai_plugin_reload>(dlsym(module, "ai_plugin_reload"));
    plugin.get_info = reinterpret_cast<fn_ai_plugin_get_info>(dlsym(module, "ai_plugin_get_info"));
#endif

    if (!plugin.init || !plugin.destroy || !plugin.infer || !plugin.free_result || !plugin.get_info) {
        load_diagnostics_.last_error = "incomplete plugin symbols";
        load_diagnostics_.failures.push_back(build_load_failure(capability_id, library_path, model_dir, "resolve_symbols", "incomplete plugin symbols"));
        std::cerr << "PluginManager: incomplete plugin symbols for capability: " << capability_id << std::endl;
        unload_all();
        return false;
    }

    AiPluginInitParams init_params{};
    init_params.model_dir = plugin.model_dir.c_str();
    init_params.device = plugin.device;
    init_params.device_id = 0;
    init_params.max_batch_size = plugin.max_batch_size;
    init_params.extra_config = "{}";
    init_params.log_level = 3;

    if (plugin.init(&init_params, &plugin.plugin_handle) != 0) {
        load_diagnostics_.last_error = "plugin init failed";
        load_diagnostics_.failures.push_back(build_load_failure(capability_id, library_path, model_dir, "plugin_init", "plugin init failed"));
        std::cerr << "PluginManager: plugin init failed for capability: " << capability_id << std::endl;
        unload_all();
        return false;
    }

    std::memset(&plugin.plugin_info, 0, sizeof(plugin.plugin_info));
    plugin.get_info(plugin.plugin_handle, &plugin.plugin_info);
    plugins_[plugin.capability_id] = plugin;
    std::cout << "PluginManager: loaded capability " << plugin.capability_id << " from " << plugin.library_path << std::endl;
    return true;
}

std::string PluginManager::resolve_registry_path() const {
    return app_paths().plugins_registry;
}

}
