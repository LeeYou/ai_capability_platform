#ifndef AI_CAPABILITY_PLATFORM_APPS_AI_PROD_CPP_RUNTIME_RESOURCE_SCANNER_H
#define AI_CAPABILITY_PLATFORM_APPS_AI_PROD_CPP_RUNTIME_RESOURCE_SCANNER_H

#include <nlohmann/json.hpp>

#include <map>
#include <optional>
#include <string>

struct RuntimeCapabilityRecord {
    std::string capability_name;
    std::string model_root;
    std::string model_version;
    std::string backend_type;
    std::string plugin_root;
    std::string plugin_target;
    std::string build_mode;
    std::string binary_path;
    std::string active_source;
    int max_batch_size = 1;
    int instance_count = 0;
    nlohmann::json model_manifest = nlohmann::json::object();
    nlohmann::json plugin_manifest = nlohmann::json::object();
};

struct RuntimeResourceScanResult {
    std::map<std::string, RuntimeCapabilityRecord> capabilities;
    nlohmann::json source_summary = nlohmann::json::object();
};

class RuntimeResourceScanner {
public:
    static std::string DetectPlatformTarget();
    static RuntimeResourceScanResult ResolveSources(
        const std::string& host_root,
        const std::string& image_resource_root,
        const std::string& target_name);
};

nlohmann::json SerializeRuntimeCapabilityRecord(const RuntimeCapabilityRecord& record);
std::optional<RuntimeCapabilityRecord> DeserializeRuntimeCapabilityRecord(
    const nlohmann::json& payload,
    std::string* error_message);

#endif
