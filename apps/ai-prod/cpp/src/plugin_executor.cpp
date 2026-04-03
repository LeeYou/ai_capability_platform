#include "plugin_executor.h"

#include <algorithm>
#include <cstring>
#include <filesystem>
#include <string>

#ifdef _WIN32
#include <windows.h>
#else
#include <dlfcn.h>
#endif

namespace {

AiDeviceType ToAiDeviceType(const std::string& device) {
    return device == "gpu" ? AI_DEVICE_CUDA : AI_DEVICE_CPU;
}

void* OpenLibrary(const std::string& path) {
#ifdef _WIN32
    return LoadLibraryA(path.c_str());
#else
    return dlopen(path.c_str(), RTLD_LAZY);
#endif
}

void CloseLibrary(void* handle) {
    if (handle == nullptr) {
        return;
    }
#ifdef _WIN32
    FreeLibrary(static_cast<HMODULE>(handle));
#else
    dlclose(handle);
#endif
}

void* LoadSymbol(void* handle, const char* name) {
#ifdef _WIN32
    return reinterpret_cast<void*>(GetProcAddress(static_cast<HMODULE>(handle), name));
#else
    return dlsym(handle, name);
#endif
}

nlohmann::json ParsePluginResult(const AiPluginOutput& output) {
    if (output.result_json == nullptr || *output.result_json == '\0') {
        return nlohmann::json::object();
    }
    try {
        return nlohmann::json::parse(output.result_json);
    } catch (const std::exception&) {
        return nlohmann::json{
            {"raw_result", output.result_json},
        };
    }
}

}

PluginExecutor::PluginExecutor() = default;

PluginExecutor::~PluginExecutor() {
    std::lock_guard<std::mutex> guard(mutex);
    for (auto& item : bindings) {
        UnloadBinding(&item.second);
    }
}

void PluginExecutor::SyncEntries(const std::vector<CapabilityCatalogEntry>& entries) {
    std::lock_guard<std::mutex> guard(mutex);
    std::map<std::string, CapabilityCatalogEntry> next_entries;
    for (const auto& entry : entries) {
        next_entries.emplace(entry.capability_name, entry);
    }

    for (auto it = bindings.begin(); it != bindings.end();) {
        const auto entry_it = next_entries.find(it->second.capability_name);
        const bool remove_binding =
            entry_it == next_entries.end() ||
            entry_it->second.binary_path != it->second.binary_path ||
            entry_it->second.model_root != it->second.model_root ||
            entry_it->second.pool_size != it->second.pool_size;
        if (!remove_binding) {
            ++it;
            continue;
        }
        UnloadBinding(&it->second);
        it = bindings.erase(it);
    }
}

bool PluginExecutor::Execute(
    const CapabilityCatalogEntry& entry,
    std::size_t slot_index,
    const std::string& input_type,
    const std::string& payload,
    const nlohmann::json& options,
    const std::string& device,
    PluginExecutionResult* result,
    std::string* error_message) {
    std::lock_guard<std::mutex> guard(mutex);
    PluginBinding* binding = nullptr;
    if (!EnsureBindingLoaded(entry, device, &binding, error_message)) {
        return false;
    }
    if (binding == nullptr || slot_index >= binding->plugin_handles.size()) {
        if (error_message != nullptr) {
            *error_message = "插件实例槽位不可用。";
        }
        return false;
    }

    std::string params_json = options.dump();
    const std::string media_format = input_type;
    AiPluginInput input{};
    input.media_data = reinterpret_cast<const uint8_t*>(payload.data());
    input.media_size = payload.size();
    input.media_type =
        input_type == "video" ? AI_MEDIA_TYPE_VIDEO :
        (input_type == "image" ? AI_MEDIA_TYPE_IMAGE : AI_MEDIA_TYPE_FRAME_SEQUENCE);
    input.media_format = media_format.c_str();
    input.params_json = params_json.c_str();

    AiPluginOutput output{};
    const int rc = binding->infer(binding->plugin_handles[slot_index], &input, &output);
    if (rc != 0) {
        if (error_message != nullptr) {
            *error_message = output.error_message != nullptr && *output.error_message != '\0'
                ? output.error_message
                : "插件推理执行失败。";
        }
        if (binding->free_result != nullptr) {
            binding->free_result(&output);
        }
        return false;
    }

    result->plugin_result = ParsePluginResult(output);
    result->infer_time_ms = output.infer_time_ms;
    if (binding->free_result != nullptr) {
        binding->free_result(&output);
    }
    return true;
}

bool PluginExecutor::EnsureBindingLoaded(
    const CapabilityCatalogEntry& entry,
    const std::string& device,
    PluginBinding** binding,
    std::string* error_message) {
    const std::string cache_key = BuildCacheKey(entry.capability_name, device);
    const auto found = bindings.find(cache_key);
    if (found != bindings.end()) {
        *binding = &found->second;
        return true;
    }

    if (entry.binary_path.empty() || !std::filesystem::exists(entry.binary_path)) {
        if (error_message != nullptr) {
            *error_message = "能力插件二进制不存在。";
        }
        return false;
    }
    if (entry.model_root.empty() || !std::filesystem::exists(entry.model_root)) {
        if (error_message != nullptr) {
            *error_message = "能力模型目录不存在。";
        }
        return false;
    }

    PluginBinding next_binding;
    next_binding.capability_name = entry.capability_name;
    next_binding.cache_key = cache_key;
    next_binding.binary_path = entry.binary_path;
    next_binding.model_root = entry.model_root;
    next_binding.device = device;
    next_binding.pool_size = std::max(1, entry.pool_size);
    next_binding.library_handle = OpenLibrary(entry.binary_path);
    if (next_binding.library_handle == nullptr) {
        if (error_message != nullptr) {
            *error_message = "能力插件动态库加载失败。";
        }
        return false;
    }

    const auto init = reinterpret_cast<fn_ai_plugin_init>(LoadSymbol(next_binding.library_handle, "ai_plugin_init"));
    next_binding.destroy = reinterpret_cast<fn_ai_plugin_destroy>(LoadSymbol(next_binding.library_handle, "ai_plugin_destroy"));
    next_binding.infer = reinterpret_cast<fn_ai_plugin_infer>(LoadSymbol(next_binding.library_handle, "ai_plugin_infer"));
    next_binding.free_result = reinterpret_cast<fn_ai_plugin_free_result>(LoadSymbol(next_binding.library_handle, "ai_plugin_free_result"));
    next_binding.get_info = reinterpret_cast<fn_ai_plugin_get_info>(LoadSymbol(next_binding.library_handle, "ai_plugin_get_info"));
    if (init == nullptr || next_binding.destroy == nullptr || next_binding.infer == nullptr ||
        next_binding.free_result == nullptr || next_binding.get_info == nullptr) {
        if (error_message != nullptr) {
            *error_message = "能力插件缺少必要导出符号。";
        }
        UnloadBinding(&next_binding);
        return false;
    }

    for (int index = 0; index < next_binding.pool_size; ++index) {
        AiPluginInitParams init_params{};
        init_params.model_dir = next_binding.model_root.c_str();
        init_params.device = ToAiDeviceType(device);
        init_params.device_id = 0;
        init_params.max_batch_size = 1;
        init_params.extra_config = "{}";
        init_params.log_level = 3;
        AiPluginHandle plugin_handle = nullptr;
        if (init(&init_params, &plugin_handle) != 0 || plugin_handle == nullptr) {
            if (error_message != nullptr) {
                *error_message = "能力插件初始化失败。";
            }
            UnloadBinding(&next_binding);
            return false;
        }
        next_binding.plugin_handles.push_back(plugin_handle);
    }

    const auto inserted = bindings.emplace(cache_key, std::move(next_binding));
    *binding = &inserted.first->second;
    return true;
}

std::string PluginExecutor::BuildCacheKey(const std::string& capability_name, const std::string& device) {
    return capability_name + "|" + device;
}

void PluginExecutor::UnloadBinding(PluginBinding* binding) {
    if (binding == nullptr) {
        return;
    }
    if (binding->destroy != nullptr) {
        for (auto* plugin_handle : binding->plugin_handles) {
            if (plugin_handle != nullptr) {
                binding->destroy(plugin_handle);
            }
        }
    }
    binding->plugin_handles.clear();
    CloseLibrary(binding->library_handle);
    binding->library_handle = nullptr;
    binding->destroy = nullptr;
    binding->infer = nullptr;
    binding->free_result = nullptr;
    binding->get_info = nullptr;
}
