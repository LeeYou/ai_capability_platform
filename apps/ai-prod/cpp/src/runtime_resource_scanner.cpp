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
    nlohmann::json manifest = nlohmann::json::object();
};

struct PluginEntry {
    std::string plugin_root;
    std::string plugin_target;
    std::string build_mode;
    std::string binary_path;
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
