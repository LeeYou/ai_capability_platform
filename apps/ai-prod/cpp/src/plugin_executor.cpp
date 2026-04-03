#include "plugin_executor.h"

#include <algorithm>
#include <chrono>
#include <cstring>
#include <filesystem>
#include <iomanip>
#include <limits>
#include <sstream>
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

nlohmann::json SerializePluginInfo(const AiPluginInfo& info) {
    return {
        {"capability_id", info.capability_id != nullptr ? info.capability_id : ""},
        {"capability_name", info.capability_name != nullptr ? info.capability_name : ""},
        {"version", info.version != nullptr ? info.version : ""},
        {"model_version", info.model_version != nullptr ? info.model_version : ""},
        {"description", info.description != nullptr ? info.description : ""},
        {"api_version_major", info.api_version_major},
        {"api_version_minor", info.api_version_minor},
        {"api_version_patch", info.api_version_patch},
        {"current_device", info.current_device == AI_DEVICE_CUDA ? "gpu" : "cpu"},
        {"extra_info_json", info.extra_info_json != nullptr ? info.extra_info_json : "{}"},
    };
}

std::string MergeLifecycleStatus(const std::string& current, const std::string& candidate) {
    const auto priority = [](const std::string& status) {
        if (status == "failed") {
            return 3;
        }
        if (status == "passed") {
            return 2;
        }
        if (status == "not_supported") {
            return 1;
        }
        return 0;
    };
    return priority(candidate) > priority(current) ? candidate : current;
}

std::string CurrentUtcIsoString() {
    const auto now = std::time(nullptr);
    std::tm utc_time{};
#ifdef _WIN32
    gmtime_s(&utc_time, &now);
#else
    gmtime_r(&now, &utc_time);
#endif
    std::ostringstream output;
    output << std::put_time(&utc_time, "%Y-%m-%dT%H:%M:%SZ");
    return output.str();
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

std::optional<nlohmann::json> PluginExecutor::GetCapabilityMetrics(const std::string& capability_name) const {
    std::lock_guard<std::mutex> guard(mutex);
    nlohmann::json bindings_payload = nlohmann::json::array();
    int total_requests = 0;
    int successful_requests = 0;
    int failed_requests = 0;
    double total_infer_time_ms = 0.0;
    double min_infer_time_ms = std::numeric_limits<double>::max();
    double max_infer_time_ms = 0.0;
    bool has_latency_sample = false;
    std::string last_request_id;
    std::string last_error_message;
    std::string last_executed_at_utc;
    std::string warmup_status = "unknown";
    std::string health_check_status = "unknown";
    std::string last_warmup_at_utc;
    std::string last_health_check_at_utc;
    std::string lifecycle_error_message;

    for (const auto& item : bindings) {
        const auto& binding = item.second;
        if (binding.capability_name != capability_name) {
            continue;
        }
        bindings_payload.push_back(
            {
                {"device", binding.device},
                {"pool_size", binding.pool_size},
                {"total_requests", binding.total_execute_count},
                {"successful_requests", binding.successful_execute_count},
                {"failed_requests", binding.failed_execute_count},
                {"avg_infer_time_ms", binding.successful_execute_count > 0
                                          ? binding.total_infer_time_ms / static_cast<double>(binding.successful_execute_count)
                                          : 0.0},
                {"min_infer_time_ms", binding.successful_execute_count > 0 ? binding.min_infer_time_ms : 0.0},
                {"max_infer_time_ms", binding.successful_execute_count > 0 ? binding.max_infer_time_ms : 0.0},
                {"last_request_id", binding.last_request_id},
                {"last_error_message", binding.last_error_message.empty()
                                           ? nlohmann::json(nullptr)
                                           : nlohmann::json(binding.last_error_message)},
                {"last_executed_at_utc", binding.last_executed_at_utc.empty()
                                             ? nlohmann::json(nullptr)
                                             : nlohmann::json(binding.last_executed_at_utc)},
                {"warmup_status", binding.warmup_status},
                {"last_warmup_at_utc", binding.last_warmup_at_utc.empty()
                                           ? nlohmann::json(nullptr)
                                           : nlohmann::json(binding.last_warmup_at_utc)},
                {"health_check_status", binding.health_check_status},
                {"last_health_check_at_utc", binding.last_health_check_at_utc.empty()
                                                 ? nlohmann::json(nullptr)
                                                 : nlohmann::json(binding.last_health_check_at_utc)},
                {"lifecycle_error_message", binding.lifecycle_error_message.empty()
                                                ? nlohmann::json(nullptr)
                                                : nlohmann::json(binding.lifecycle_error_message)},
                {"plugin_info", binding.plugin_info_loaded ? SerializePluginInfo(binding.plugin_info) : nlohmann::json(nullptr)},
            });

        total_requests += binding.total_execute_count;
        successful_requests += binding.successful_execute_count;
        failed_requests += binding.failed_execute_count;
        total_infer_time_ms += binding.total_infer_time_ms;
        if (binding.successful_execute_count > 0) {
            min_infer_time_ms = std::min(min_infer_time_ms, binding.min_infer_time_ms);
            max_infer_time_ms = std::max(max_infer_time_ms, binding.max_infer_time_ms);
            has_latency_sample = true;
        }
        if (binding.last_executed_at_utc >= last_executed_at_utc) {
            last_request_id = binding.last_request_id;
            last_error_message = binding.last_error_message;
            last_executed_at_utc = binding.last_executed_at_utc;
        }
        warmup_status = MergeLifecycleStatus(warmup_status, binding.warmup_status);
        health_check_status = MergeLifecycleStatus(health_check_status, binding.health_check_status);
        if (binding.last_warmup_at_utc >= last_warmup_at_utc) {
            last_warmup_at_utc = binding.last_warmup_at_utc;
        }
        if (binding.last_health_check_at_utc >= last_health_check_at_utc) {
            last_health_check_at_utc = binding.last_health_check_at_utc;
        }
        if (!binding.lifecycle_error_message.empty()) {
            lifecycle_error_message = binding.lifecycle_error_message;
        }
    }

    if (bindings_payload.empty()) {
        return std::nullopt;
    }

    return nlohmann::json{
        {"total_requests", total_requests},
        {"successful_requests", successful_requests},
        {"failed_requests", failed_requests},
        {"avg_infer_time_ms", successful_requests > 0 ? total_infer_time_ms / static_cast<double>(successful_requests) : 0.0},
        {"min_infer_time_ms", has_latency_sample ? min_infer_time_ms : 0.0},
        {"max_infer_time_ms", has_latency_sample ? max_infer_time_ms : 0.0},
        {"last_request_id", last_request_id.empty() ? nlohmann::json(nullptr) : nlohmann::json(last_request_id)},
        {"last_error_message", last_error_message.empty() ? nlohmann::json(nullptr) : nlohmann::json(last_error_message)},
        {"last_executed_at_utc", last_executed_at_utc.empty() ? nlohmann::json(nullptr) : nlohmann::json(last_executed_at_utc)},
        {"warmup_status", warmup_status == "unknown" ? "not_supported" : warmup_status},
        {"last_warmup_at_utc", last_warmup_at_utc.empty() ? nlohmann::json(nullptr) : nlohmann::json(last_warmup_at_utc)},
        {"health_check_status", health_check_status == "unknown" ? "not_supported" : health_check_status},
        {"last_health_check_at_utc", last_health_check_at_utc.empty() ? nlohmann::json(nullptr) : nlohmann::json(last_health_check_at_utc)},
        {"lifecycle_error_message", lifecycle_error_message.empty() ? nlohmann::json(nullptr) : nlohmann::json(lifecycle_error_message)},
        {"bindings", bindings_payload},
    };
}

bool PluginExecutor::Execute(
    const CapabilityCatalogEntry& entry,
    std::size_t slot_index,
    const std::string& input_type,
    const std::string& payload,
    const nlohmann::json& options,
    const std::string& device,
    const std::string& request_id,
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
    binding->total_execute_count += 1;
    binding->last_request_id = request_id;
    binding->last_error_message.clear();
    binding->last_executed_at_utc = CurrentUtcIsoString();
    const int rc = binding->infer(binding->plugin_handles[slot_index], &input, &output);
    if (rc != 0) {
        binding->failed_execute_count += 1;
        binding->last_error_message =
            output.error_message != nullptr && *output.error_message != '\0'
                ? output.error_message
                : "插件推理执行失败。";
        if (error_message != nullptr) {
            *error_message = binding->last_error_message;
        }
        if (binding->free_result != nullptr) {
            binding->free_result(&output);
        }
        return false;
    }

    result->plugin_result = ParsePluginResult(output);
    result->infer_time_ms = output.infer_time_ms;
    binding->successful_execute_count += 1;
    binding->total_infer_time_ms += output.infer_time_ms;
    if (binding->successful_execute_count == 1) {
        binding->min_infer_time_ms = output.infer_time_ms;
        binding->max_infer_time_ms = output.infer_time_ms;
    } else {
        binding->min_infer_time_ms = std::min(binding->min_infer_time_ms, output.infer_time_ms);
        binding->max_infer_time_ms = std::max(binding->max_infer_time_ms, output.infer_time_ms);
    }
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
    next_binding.warmup = reinterpret_cast<fn_ai_plugin_warmup>(LoadSymbol(next_binding.library_handle, "ai_plugin_warmup"));
    next_binding.health_check = reinterpret_cast<fn_ai_plugin_health_check>(LoadSymbol(next_binding.library_handle, "ai_plugin_health_check"));
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
        AiPluginInfo plugin_info{};
        if (next_binding.get_info(plugin_handle, &plugin_info) == 0) {
            next_binding.plugin_info = plugin_info;
            next_binding.plugin_info_loaded = true;
        }
        if (next_binding.warmup != nullptr) {
            next_binding.last_warmup_at_utc = CurrentUtcIsoString();
            if (next_binding.warmup(plugin_handle) != 0) {
                next_binding.warmup_status = "failed";
                next_binding.lifecycle_error_message = "能力插件预热失败。";
                if (error_message != nullptr) {
                    *error_message = next_binding.lifecycle_error_message;
                }
                UnloadBinding(&next_binding);
                return false;
            }
            next_binding.warmup_status = "passed";
        }
        if (next_binding.health_check != nullptr) {
            next_binding.last_health_check_at_utc = CurrentUtcIsoString();
            if (next_binding.health_check(plugin_handle) != 0) {
                next_binding.health_check_status = "failed";
                next_binding.lifecycle_error_message = "能力插件健康检查失败。";
                if (error_message != nullptr) {
                    *error_message = next_binding.lifecycle_error_message;
                }
                UnloadBinding(&next_binding);
                return false;
            }
            next_binding.health_check_status = "passed";
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
    binding->warmup = nullptr;
    binding->health_check = nullptr;
}
