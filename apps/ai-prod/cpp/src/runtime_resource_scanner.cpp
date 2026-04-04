#include "runtime_resource_scanner.h"

#include <filesystem>
#include <fstream>
#include <sstream>
#include <set>
#include <algorithm>
#include <utility>
#include <vector>

namespace {

bool ReadRequiredString(
    const nlohmann::json& payload,
    const char* key,
    std::string* value,
    std::string* error_message) {
    if (!payload.contains(key) || !payload[key].is_string()) {
        if (error_message != nullptr) {
            *error_message = std::string("capability record 缺失字段：") + key;
        }
        return false;
    }
    *value = payload[key].get<std::string>();
    return true;
}

int ReadPositiveIntOrDefaultMinOne(const nlohmann::json& payload, const char* key, int fallback) {
    if (!payload.contains(key) || !payload[key].is_number_integer()) {
        return fallback;
    }
    return std::max(1, payload[key].get<int>());
}

int ReadNonNegativeIntOrDefault(const nlohmann::json& payload, const char* key, int fallback) {
    if (!payload.contains(key) || !payload[key].is_number_integer()) {
        return fallback;
    }
    return std::max(0, payload[key].get<int>());
}

bool ReadBooleanOrDefault(const nlohmann::json& payload, const char* key, bool fallback) {
    if (!payload.contains(key) || !payload[key].is_boolean()) {
        return fallback;
    }
    return payload[key].get<bool>();
}

int ExtractBatchSizeFromManifest(const nlohmann::json& manifest) {
    if (manifest.contains("max_batch_size") && manifest["max_batch_size"].is_number_integer()) {
        return std::max(1, manifest["max_batch_size"].get<int>());
    }
    if (manifest.contains("batch_size") && manifest["batch_size"].is_number_integer()) {
        return std::max(1, manifest["batch_size"].get<int>());
    }
    return 1;
}

std::vector<std::filesystem::path> SortedDirs(const std::filesystem::path& path) {
    if (!std::filesystem::exists(path)) {
        return {};
    }
    std::vector<std::filesystem::path> items;
    for (const auto& entry : std::filesystem::directory_iterator(path)) {
        if (entry.is_directory()) {
            items.push_back(entry.path());
        }
    }
    std::sort(items.begin(), items.end());
    return items;
}

nlohmann::json ReadJsonOrDefault(const std::filesystem::path& path, const nlohmann::json& fallback) {
    if (!std::filesystem::exists(path)) {
        return fallback;
    }
    std::ifstream input(path);
    if (!input.is_open()) {
        return fallback;
    }
    std::ostringstream buffer;
    buffer << input.rdbuf();
    try {
        const auto parsed = nlohmann::json::parse(buffer.str());
        return parsed.is_object() ? parsed : fallback;
    } catch (const std::exception&) {
        return fallback;
    }
}

struct ModelEntry {
    std::string model_root;
    std::string model_version;
    std::string backend_type;
    std::string declared_device_mode = "auto";
    int capability_priority = 100;
    int max_batch_size = 1;
    int min_batch_size = 1;
    int batch_wait_timeout_ms = -1;
    int instance_count = 0;
    int queue_wait_timeout_ms = -1;
    int max_pending_request_count = -1;
    int infer_timeout_ms = -1;
    int estimated_avg_infer_time_ms = -1;
    int p95_infer_time_ms = -1;
    int max_concurrent_requests = -1;
    bool supports_concurrent_infer = true;
    bool allow_resource_sharing = false;
    nlohmann::json manifest = nlohmann::json::object();
};

struct PluginEntry {
    std::string plugin_root;
    std::string plugin_target;
    std::string build_mode;
    std::string binary_path;
    std::string declared_device_mode = "auto";
    int capability_priority = 100;
    int max_batch_size = 1;
    int min_batch_size = 1;
    int batch_wait_timeout_ms = -1;
    int instance_count = 0;
    int queue_wait_timeout_ms = -1;
    int max_pending_request_count = -1;
    int infer_timeout_ms = -1;
    int estimated_avg_infer_time_ms = -1;
    int p95_infer_time_ms = -1;
    int max_concurrent_requests = -1;
    bool supports_concurrent_infer = true;
    bool allow_resource_sharing = false;
    nlohmann::json manifest = nlohmann::json::object();
};

std::map<std::string, ModelEntry> ScanModels(const std::filesystem::path& root) {
    std::map<std::string, ModelEntry> capability_map;
    for (const auto& capability_dir : SortedDirs(root)) {
        const auto versions = SortedDirs(capability_dir);
        if (versions.empty()) {
            continue;
        }
        const auto selected_version_dir = versions.back();
        const auto manifest = ReadJsonOrDefault(
            selected_version_dir / "manifest.json",
            {
                {"capability_name", capability_dir.filename().string()},
                {"model_version", selected_version_dir.filename().string()},
                {"backend_type", "onnxruntime"},
            });
        capability_map.emplace(
            capability_dir.filename().string(),
            ModelEntry{
                selected_version_dir.lexically_normal().string(),
                manifest.value("model_version", selected_version_dir.filename().string()),
                manifest.value("backend_type", std::string("onnxruntime")),
                manifest.value("device_mode", std::string("auto")),
                manifest.contains("capability_priority") && manifest["capability_priority"].is_number_integer()
                    ? manifest["capability_priority"].get<int>()
                    : 100,
                ExtractBatchSizeFromManifest(manifest),
                ReadPositiveIntOrDefaultMinOne(manifest, "min_batch_size", 1),
                ReadNonNegativeIntOrDefault(manifest, "batch_wait_timeout_ms", -1),
                manifest.contains("instance_count") && manifest["instance_count"].is_number_integer()
                    ? std::max(1, manifest["instance_count"].get<int>())
                    : 0,
                ReadNonNegativeIntOrDefault(manifest, "queue_wait_timeout_ms", -1),
                ReadNonNegativeIntOrDefault(manifest, "max_pending_request_count", -1),
                ReadNonNegativeIntOrDefault(manifest, "infer_timeout_ms", -1),
                ReadNonNegativeIntOrDefault(manifest, "estimated_avg_infer_time_ms", -1),
                ReadNonNegativeIntOrDefault(manifest, "p95_infer_time_ms", -1),
                ReadNonNegativeIntOrDefault(manifest, "max_concurrent_requests", -1),
                ReadBooleanOrDefault(manifest, "supports_concurrent_infer", true),
                ReadBooleanOrDefault(manifest, "allow_resource_sharing", false),
                manifest,
            });
    }
    return capability_map;
}

std::map<std::string, PluginEntry> ScanPlugins(const std::filesystem::path& root, const std::string& target_name) {
    std::map<std::string, PluginEntry> capability_map;
    const auto target_root = root / target_name;
    for (const auto& capability_dir : SortedDirs(target_root)) {
        const auto manifest = ReadJsonOrDefault(
            capability_dir / "manifest" / "manifest.json",
            {
                {"capability_name", capability_dir.filename().string()},
                {"target_name", target_name},
                {"build_mode", "template"},
                {"dependency_summary", nlohmann::json::object()},
            });
        std::string binary_path;
        const auto lib_dir = capability_dir / "lib";
        if (std::filesystem::exists(lib_dir)) {
            std::vector<std::filesystem::path> binaries;
            for (const auto& entry : std::filesystem::directory_iterator(lib_dir)) {
                if (entry.is_regular_file()) {
                    binaries.push_back(entry.path());
                }
            }
            std::sort(binaries.begin(), binaries.end());
            if (!binaries.empty()) {
                binary_path = binaries.front().lexically_normal().string();
            }
        }
        capability_map.emplace(
            capability_dir.filename().string(),
            PluginEntry{
                capability_dir.lexically_normal().string(),
                target_name,
                manifest.value("build_mode", std::string("template")),
                binary_path,
                manifest.value("device_mode", std::string("auto")),
                manifest.contains("capability_priority") && manifest["capability_priority"].is_number_integer()
                    ? manifest["capability_priority"].get<int>()
                    : 100,
                ReadPositiveIntOrDefaultMinOne(manifest, "max_batch_size", 1),
                ReadPositiveIntOrDefaultMinOne(manifest, "min_batch_size", 1),
                ReadNonNegativeIntOrDefault(manifest, "batch_wait_timeout_ms", -1),
                manifest.contains("instance_count") && manifest["instance_count"].is_number_integer()
                    ? std::max(1, manifest["instance_count"].get<int>())
                    : 0,
                ReadNonNegativeIntOrDefault(manifest, "queue_wait_timeout_ms", -1),
                ReadNonNegativeIntOrDefault(manifest, "max_pending_request_count", -1),
                ReadNonNegativeIntOrDefault(manifest, "infer_timeout_ms", -1),
                ReadNonNegativeIntOrDefault(manifest, "estimated_avg_infer_time_ms", -1),
                ReadNonNegativeIntOrDefault(manifest, "p95_infer_time_ms", -1),
                ReadNonNegativeIntOrDefault(manifest, "max_concurrent_requests", -1),
                ReadBooleanOrDefault(manifest, "supports_concurrent_infer", true),
                ReadBooleanOrDefault(manifest, "allow_resource_sharing", false),
                manifest,
            });
    }
    return capability_map;
}

}

std::string RuntimeResourceScanner::DetectPlatformTarget() {
#ifdef _WIN32
    return sizeof(void*) == 8 ? "windows_x86_64" : "windows_x86";
#elif defined(__aarch64__) || defined(_M_ARM64)
    return "linux_arm64";
#else
    return "linux_x86_64";
#endif
}

RuntimeResourceScanResult RuntimeResourceScanner::ResolveSources(
    const std::string& host_root,
    const std::string& image_resource_root,
    const std::string& target_name) {
    const auto host_models = ScanModels(std::filesystem::path(host_root) / "models");
    const auto image_models = ScanModels(std::filesystem::path(image_resource_root) / "models");
    const auto host_plugins = ScanPlugins(std::filesystem::path(host_root) / "libs", target_name);
    const auto image_plugins = ScanPlugins(std::filesystem::path(image_resource_root) / "libs", target_name);

    RuntimeResourceScanResult result;
    std::set<std::string> capability_names;
    for (const auto& item : host_models) capability_names.insert(item.first);
    for (const auto& item : image_models) capability_names.insert(item.first);
    for (const auto& item : host_plugins) capability_names.insert(item.first);
    for (const auto& item : image_plugins) capability_names.insert(item.first);

    for (const auto& capability_name : capability_names) {
        const auto host_model_it = host_models.find(capability_name);
        const auto image_model_it = image_models.find(capability_name);
        const auto host_plugin_it = host_plugins.find(capability_name);
        const auto image_plugin_it = image_plugins.find(capability_name);
        if ((host_model_it == host_models.end() && image_model_it == image_models.end()) ||
            (host_plugin_it == host_plugins.end() && image_plugin_it == image_plugins.end())) {
            continue;
        }

        const auto& model_entry = host_model_it != host_models.end() ? host_model_it->second : image_model_it->second;
        const auto& plugin_entry = host_plugin_it != host_plugins.end() ? host_plugin_it->second : image_plugin_it->second;
        result.capabilities.emplace(
            capability_name,
            RuntimeCapabilityRecord{
                capability_name,
                model_entry.model_root,
                model_entry.model_version,
                model_entry.backend_type,
                plugin_entry.plugin_root,
                plugin_entry.plugin_target,
                plugin_entry.build_mode,
                plugin_entry.binary_path,
                host_model_it != host_models.end() && host_plugin_it != host_plugins.end() ? "host" : "image",
                plugin_entry.declared_device_mode != "auto" ? plugin_entry.declared_device_mode : model_entry.declared_device_mode,
                plugin_entry.max_batch_size > 1 ? plugin_entry.max_batch_size : model_entry.max_batch_size,
                std::max(1, plugin_entry.min_batch_size > 1 ? plugin_entry.min_batch_size : model_entry.min_batch_size),
                plugin_entry.batch_wait_timeout_ms >= 0 ? plugin_entry.batch_wait_timeout_ms : model_entry.batch_wait_timeout_ms,
                plugin_entry.instance_count > 0 ? plugin_entry.instance_count : model_entry.instance_count,
                plugin_entry.queue_wait_timeout_ms >= 0 ? plugin_entry.queue_wait_timeout_ms : model_entry.queue_wait_timeout_ms,
                plugin_entry.max_pending_request_count >= 0 ? plugin_entry.max_pending_request_count : model_entry.max_pending_request_count,
                std::max(plugin_entry.capability_priority, model_entry.capability_priority),
                plugin_entry.infer_timeout_ms >= 0 ? plugin_entry.infer_timeout_ms : model_entry.infer_timeout_ms,
                plugin_entry.estimated_avg_infer_time_ms >= 0 ? plugin_entry.estimated_avg_infer_time_ms : model_entry.estimated_avg_infer_time_ms,
                plugin_entry.p95_infer_time_ms >= 0 ? plugin_entry.p95_infer_time_ms : model_entry.p95_infer_time_ms,
                plugin_entry.max_concurrent_requests >= 0 ? plugin_entry.max_concurrent_requests : model_entry.max_concurrent_requests,
                plugin_entry.supports_concurrent_infer && model_entry.supports_concurrent_infer,
                plugin_entry.allow_resource_sharing || model_entry.allow_resource_sharing,
                model_entry.manifest,
                plugin_entry.manifest,
            });
    }

    result.source_summary = {
        {"target_name", target_name},
        {"host_models", nlohmann::json::array()},
        {"host_plugins", nlohmann::json::array()},
        {"image_models", nlohmann::json::array()},
        {"image_plugins", nlohmann::json::array()},
    };
    for (const auto& item : host_models) result.source_summary["host_models"].push_back(item.first);
    for (const auto& item : host_plugins) result.source_summary["host_plugins"].push_back(item.first);
    for (const auto& item : image_models) result.source_summary["image_models"].push_back(item.first);
    for (const auto& item : image_plugins) result.source_summary["image_plugins"].push_back(item.first);
    return result;
}

nlohmann::json SerializeRuntimeCapabilityRecord(const RuntimeCapabilityRecord& record) {
    return {
        {"capability_name", record.capability_name},
        {"model_root", record.model_root},
        {"model_version", record.model_version},
        {"backend_type", record.backend_type},
        {"plugin_root", record.plugin_root},
        {"plugin_target", record.plugin_target},
        {"build_mode", record.build_mode},
        {"binary_path", record.binary_path},
        {"active_source", record.active_source},
        {"declared_device_mode", record.declared_device_mode},
        {"capability_priority", record.capability_priority},
        {"max_batch_size", record.max_batch_size},
        {"min_batch_size", record.min_batch_size},
        {"batch_wait_timeout_ms", record.batch_wait_timeout_ms},
        {"instance_count", record.instance_count},
        {"queue_wait_timeout_ms", record.queue_wait_timeout_ms},
        {"max_pending_request_count", record.max_pending_request_count},
        {"infer_timeout_ms", record.infer_timeout_ms},
        {"estimated_avg_infer_time_ms", record.estimated_avg_infer_time_ms},
        {"p95_infer_time_ms", record.p95_infer_time_ms},
        {"max_concurrent_requests", record.max_concurrent_requests},
        {"supports_concurrent_infer", record.supports_concurrent_infer},
        {"allow_resource_sharing", record.allow_resource_sharing},
        {"model_manifest", record.model_manifest},
        {"plugin_manifest", record.plugin_manifest},
    };
}

std::optional<RuntimeCapabilityRecord> DeserializeRuntimeCapabilityRecord(
    const nlohmann::json& payload,
    std::string* error_message) {
    if (!payload.is_object()) {
        if (error_message != nullptr) {
            *error_message = "capability record 必须是对象。";
        }
        return std::nullopt;
    }

    RuntimeCapabilityRecord record;
    if (!ReadRequiredString(payload, "capability_name", &record.capability_name, error_message) ||
        !ReadRequiredString(payload, "model_root", &record.model_root, error_message) ||
        !ReadRequiredString(payload, "model_version", &record.model_version, error_message) ||
        !ReadRequiredString(payload, "backend_type", &record.backend_type, error_message) ||
        !ReadRequiredString(payload, "plugin_root", &record.plugin_root, error_message) ||
        !ReadRequiredString(payload, "plugin_target", &record.plugin_target, error_message) ||
        !ReadRequiredString(payload, "build_mode", &record.build_mode, error_message) ||
        !ReadRequiredString(payload, "binary_path", &record.binary_path, error_message) ||
        !ReadRequiredString(payload, "active_source", &record.active_source, error_message)) {
        return std::nullopt;
    }
    record.declared_device_mode = payload.value("declared_device_mode", std::string("auto"));
    record.capability_priority =
        payload.contains("capability_priority") && payload["capability_priority"].is_number_integer()
            ? payload["capability_priority"].get<int>()
            : 100;
    record.max_batch_size = payload.contains("max_batch_size") && payload["max_batch_size"].is_number_integer()
                                ? std::max(1, payload["max_batch_size"].get<int>())
                                : 1;
    record.min_batch_size = payload.contains("min_batch_size") && payload["min_batch_size"].is_number_integer()
                                ? std::max(1, payload["min_batch_size"].get<int>())
                                : 1;
    record.batch_wait_timeout_ms =
        payload.contains("batch_wait_timeout_ms") && payload["batch_wait_timeout_ms"].is_number_integer()
            ? std::max(0, payload["batch_wait_timeout_ms"].get<int>())
            : -1;
    record.instance_count = payload.contains("instance_count") && payload["instance_count"].is_number_integer()
                                ? std::max(1, payload["instance_count"].get<int>())
                                : 0;
    record.queue_wait_timeout_ms =
        payload.contains("queue_wait_timeout_ms") && payload["queue_wait_timeout_ms"].is_number_integer()
            ? std::max(0, payload["queue_wait_timeout_ms"].get<int>())
            : -1;
    record.max_pending_request_count =
        payload.contains("max_pending_request_count") && payload["max_pending_request_count"].is_number_integer()
            ? std::max(0, payload["max_pending_request_count"].get<int>())
            : -1;
    record.infer_timeout_ms =
        payload.contains("infer_timeout_ms") && payload["infer_timeout_ms"].is_number_integer()
            ? std::max(0, payload["infer_timeout_ms"].get<int>())
            : -1;
    record.estimated_avg_infer_time_ms =
        payload.contains("estimated_avg_infer_time_ms") && payload["estimated_avg_infer_time_ms"].is_number_integer()
            ? std::max(0, payload["estimated_avg_infer_time_ms"].get<int>())
            : -1;
    record.p95_infer_time_ms =
        payload.contains("p95_infer_time_ms") && payload["p95_infer_time_ms"].is_number_integer()
            ? std::max(0, payload["p95_infer_time_ms"].get<int>())
            : -1;
    record.max_concurrent_requests =
        payload.contains("max_concurrent_requests") && payload["max_concurrent_requests"].is_number_integer()
            ? std::max(0, payload["max_concurrent_requests"].get<int>())
            : -1;
    record.supports_concurrent_infer = payload.value("supports_concurrent_infer", true);
    record.allow_resource_sharing = payload.value("allow_resource_sharing", false);

    if (payload.contains("model_manifest")) {
        if (!payload["model_manifest"].is_object()) {
            if (error_message != nullptr) {
                *error_message = "model_manifest 必须是对象。";
            }
            return std::nullopt;
        }
        record.model_manifest = payload["model_manifest"];
    }
    if (payload.contains("plugin_manifest")) {
        if (!payload["plugin_manifest"].is_object()) {
            if (error_message != nullptr) {
                *error_message = "plugin_manifest 必须是对象。";
            }
            return std::nullopt;
        }
        record.plugin_manifest = payload["plugin_manifest"];
    }
    return record;
}
