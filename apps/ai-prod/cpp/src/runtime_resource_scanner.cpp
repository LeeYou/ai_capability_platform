#include "runtime_resource_scanner.h"

#include <filesystem>
#include <fstream>
#include <sstream>
#include <set>
#include <algorithm>
#include <system_error>
#include <utility>
#include <vector>

namespace {

struct ScanFailure {
    std::string capability_name;
    std::string manifest_type;
    std::string manifest_path;
    std::string reason;
};

template <typename T>
struct ScanCollection {
    std::map<std::string, T> items;
    std::vector<ScanFailure> failures;
};

void AppendFailure(
    std::vector<ScanFailure>* failures,
    const std::string& capability_name,
    const std::string& manifest_type,
    const std::filesystem::path& manifest_path,
    const std::string& reason) {
    failures->push_back(
        ScanFailure{
            capability_name,
            manifest_type,
            manifest_path.lexically_normal().string(),
            reason,
        });
}

std::filesystem::path NormalizeExistingPath(const std::filesystem::path& path) {
    std::error_code error_code;
    const auto canonical_path = std::filesystem::weakly_canonical(path, error_code);
    if (!error_code) {
        return canonical_path.lexically_normal();
    }
    return path.lexically_normal();
}

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

bool ReadRequiredInteger(
    const nlohmann::json& payload,
    const char* key,
    int* value,
    std::string* error_message) {
    if (!payload.contains(key) || !payload[key].is_number_integer()) {
        if (error_message != nullptr) {
            *error_message = std::string("manifest 缺失整数字段：") + key;
        }
        return false;
    }
    *value = payload[key].get<int>();
    return true;
}

bool ReadRequiredBoolean(
    const nlohmann::json& payload,
    const char* key,
    bool* value,
    std::string* error_message) {
    if (!payload.contains(key) || !payload[key].is_boolean()) {
        if (error_message != nullptr) {
            *error_message = std::string("manifest 缺失布尔字段：") + key;
        }
        return false;
    }
    *value = payload[key].get<bool>();
    return true;
}

bool ReadRequiredObject(
    const nlohmann::json& payload,
    const char* key,
    nlohmann::json* value,
    std::string* error_message) {
    if (!payload.contains(key) || !payload[key].is_object()) {
        if (error_message != nullptr) {
            *error_message = std::string("manifest 缺失对象字段：") + key;
        }
        return false;
    }
    *value = payload[key];
    return true;
}

bool ReadRequiredArray(
    const nlohmann::json& payload,
    const char* key,
    nlohmann::json* value,
    std::string* error_message) {
    if (!payload.contains(key) || !payload[key].is_array()) {
        if (error_message != nullptr) {
            *error_message = std::string("manifest 缺失数组字段：") + key;
        }
        return false;
    }
    *value = payload[key];
    return true;
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

bool ValidatePathUnderRoot(
    const std::filesystem::path& root_path,
    const std::filesystem::path& candidate_path,
    const char* label,
    std::string* error_message) {
    const auto normalized_root = NormalizeExistingPath(root_path);
    const auto normalized_candidate = NormalizeExistingPath(candidate_path);
    if (normalized_candidate != normalized_root) {
        const auto candidate_string = normalized_candidate.string();
        const auto root_string = normalized_root.string();
        if (candidate_string.rfind(root_string + std::filesystem::path::preferred_separator, 0) != 0) {
            if (error_message != nullptr) {
                *error_message = std::string(label) + " 必须位于模型目录内。";
            }
            return false;
        }
    }
    return true;
}

bool ResolveManifestPath(
    const std::filesystem::path& base_path,
    const std::string& raw_path,
    std::filesystem::path* resolved_path,
    std::string* error_message) {
    if (raw_path.empty()) {
        if (error_message != nullptr) {
            *error_message = "manifest 路径不能为空。";
        }
        return false;
    }
    const auto candidate = std::filesystem::path(raw_path);
    *resolved_path = candidate.is_absolute() ? candidate : base_path / candidate;
    if (!std::filesystem::exists(*resolved_path)) {
        if (error_message != nullptr) {
            *error_message = std::string("manifest 依赖文件不存在：") + resolved_path->string();
        }
        return false;
    }
    return ValidatePathUnderRoot(base_path, *resolved_path, "manifest 依赖文件", error_message);
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

std::optional<nlohmann::json> ReadJsonObject(const std::filesystem::path& path, std::string* error_message) {
    if (!std::filesystem::exists(path)) {
        if (error_message != nullptr) {
            *error_message = "manifest 文件不存在。";
        }
        return std::nullopt;
    }
    std::ifstream input(path);
    if (!input.is_open()) {
        if (error_message != nullptr) {
            *error_message = "manifest 文件无法打开。";
        }
        return std::nullopt;
    }
    std::ostringstream buffer;
    buffer << input.rdbuf();
    try {
        const auto parsed = nlohmann::json::parse(buffer.str());
        if (!parsed.is_object()) {
            if (error_message != nullptr) {
                *error_message = "manifest 顶层必须是对象。";
            }
            return std::nullopt;
        }
        return parsed;
    } catch (const std::exception& exception) {
        if (error_message != nullptr) {
            *error_message = std::string("manifest 解析失败：") + exception.what();
        }
        return std::nullopt;
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

bool ValidateModelManifest(
    const std::filesystem::path& capability_dir,
    const std::filesystem::path& selected_version_dir,
    const nlohmann::json& manifest,
    ModelEntry* entry,
    std::string* error_message) {
    std::string capability_name;
    std::string task_type;
    std::string model_version;
    std::string task_name;
    std::string backend_type;
    std::string artifact_path_value;
    std::string status;
    std::string checksum;
    int source_train_task_id = 0;
    nlohmann::json preprocessing;
    nlohmann::json thresholds;
    nlohmann::json labels;
    nlohmann::json validation;
    nlohmann::json runtime_contract;
    nlohmann::json delivery_metadata;
    if (!ReadRequiredString(manifest, "capability_name", &capability_name, error_message) ||
        !ReadRequiredString(manifest, "task_type", &task_type, error_message) ||
        !ReadRequiredString(manifest, "model_version", &model_version, error_message) ||
        !ReadRequiredInteger(manifest, "source_train_task_id", &source_train_task_id, error_message) ||
        !ReadRequiredString(manifest, "task_name", &task_name, error_message) ||
        !ReadRequiredString(manifest, "backend_type", &backend_type, error_message) ||
        !ReadRequiredString(manifest, "artifact_path", &artifact_path_value, error_message) ||
        !ReadRequiredString(manifest, "status", &status, error_message) ||
        !ReadRequiredString(manifest, "checksum", &checksum, error_message) ||
        !ReadRequiredObject(manifest, "preprocessing", &preprocessing, error_message) ||
        !ReadRequiredObject(manifest, "thresholds", &thresholds, error_message) ||
        !ReadRequiredArray(manifest, "labels", &labels, error_message) ||
        !ReadRequiredObject(manifest, "validation", &validation, error_message) ||
        !ReadRequiredObject(manifest, "runtime_contract", &runtime_contract, error_message) ||
        !ReadRequiredObject(manifest, "delivery_metadata", &delivery_metadata, error_message)) {
        return false;
    }
    if (capability_name != capability_dir.filename().string()) {
        if (error_message != nullptr) {
            *error_message = "模型包 manifest capability_name 与目录名不一致。";
        }
        return false;
    }
    if (model_version != selected_version_dir.filename().string()) {
        if (error_message != nullptr) {
            *error_message = "模型包 manifest model_version 与目录版本不一致。";
        }
        return false;
    }
    if (status != "ready") {
        if (error_message != nullptr) {
            *error_message = "模型包 manifest status 必须为 ready。";
        }
        return false;
    }
    if (labels.empty()) {
        if (error_message != nullptr) {
            *error_message = "模型包 manifest labels 不能为空。";
        }
        return false;
    }
    for (const auto& label_item : labels) {
        if (!label_item.is_string() || label_item.get<std::string>().empty()) {
            if (error_message != nullptr) {
                *error_message = "模型包 manifest labels 必须全部为非空字符串。";
            }
            return false;
        }
    }
    if (!preprocessing.contains("input_type") || !preprocessing["input_type"].is_string() ||
        !preprocessing.contains("resize") || !preprocessing["resize"].is_object() ||
        !preprocessing.contains("normalize") || !preprocessing["normalize"].is_object()) {
        if (error_message != nullptr) {
            *error_message = "模型包 manifest preprocessing 缺失必需字段。";
        }
        return false;
    }
    if (!thresholds.contains("score_threshold") || !thresholds.contains("nms_threshold")) {
        if (error_message != nullptr) {
            *error_message = "模型包 manifest thresholds 缺失必需字段。";
        }
        return false;
    }
    if (!validation.contains("artifacts") || !validation["artifacts"].is_array()) {
        if (error_message != nullptr) {
            *error_message = "模型包 manifest validation.artifacts 缺失。";
        }
        return false;
    }
    std::filesystem::path artifact_root;
    if (!ResolveManifestPath(selected_version_dir, artifact_path_value, &artifact_root, error_message)) {
        return false;
    }
    if (NormalizeExistingPath(artifact_root) != NormalizeExistingPath(selected_version_dir)) {
        if (error_message != nullptr) {
            *error_message = "模型包 manifest artifact_path 与实际模型目录不一致。";
        }
        return false;
    }
    if (!runtime_contract.contains("task_type") || !runtime_contract["task_type"].is_string() ||
        runtime_contract["task_type"].get<std::string>() != task_type) {
        if (error_message != nullptr) {
            *error_message = "模型包 manifest runtime_contract.task_type 与 task_type 不一致。";
        }
        return false;
    }
    if (!runtime_contract.contains("runtime_inputs") || !runtime_contract["runtime_inputs"].is_object()) {
        if (error_message != nullptr) {
            *error_message = "模型包 manifest runtime_contract.runtime_inputs 缺失。";
        }
        return false;
    }
    const auto runtime_inputs = runtime_contract["runtime_inputs"];
    std::string preprocess_path_value;
    std::string labels_path_value;
    if (!ReadRequiredString(runtime_inputs, "preprocess_path", &preprocess_path_value, error_message) ||
        !ReadRequiredString(runtime_inputs, "labels_path", &labels_path_value, error_message)) {
        return false;
    }
    std::filesystem::path resolved_preprocess_path;
    std::filesystem::path resolved_labels_path;
    if (!ResolveManifestPath(selected_version_dir, preprocess_path_value, &resolved_preprocess_path, error_message) ||
        !ResolveManifestPath(selected_version_dir, labels_path_value, &resolved_labels_path, error_message)) {
        return false;
    }
    for (const auto& artifact_item : validation["artifacts"]) {
        if (!artifact_item.is_string()) {
            if (error_message != nullptr) {
                *error_message = "模型包 manifest validation.artifacts 必须全部为字符串。";
            }
            return false;
        }
        std::filesystem::path resolved_artifact_path;
        if (!ResolveManifestPath(
                selected_version_dir,
                artifact_item.get<std::string>(),
                &resolved_artifact_path,
                error_message)) {
            return false;
        }
    }

    entry->model_root = selected_version_dir.lexically_normal().string();
    entry->model_version = model_version;
    entry->backend_type = backend_type;
    entry->declared_device_mode = manifest.value("device_mode", std::string("auto"));
    entry->capability_priority =
        manifest.contains("capability_priority") && manifest["capability_priority"].is_number_integer()
            ? manifest["capability_priority"].get<int>()
            : 100;
    entry->max_batch_size = ExtractBatchSizeFromManifest(manifest);
    entry->min_batch_size = ReadPositiveIntOrDefaultMinOne(manifest, "min_batch_size", 1);
    entry->batch_wait_timeout_ms = ReadNonNegativeIntOrDefault(manifest, "batch_wait_timeout_ms", -1);
    entry->instance_count =
        manifest.contains("instance_count") && manifest["instance_count"].is_number_integer()
            ? std::max(1, manifest["instance_count"].get<int>())
            : 0;
    entry->queue_wait_timeout_ms = ReadNonNegativeIntOrDefault(manifest, "queue_wait_timeout_ms", -1);
    entry->max_pending_request_count = ReadNonNegativeIntOrDefault(manifest, "max_pending_request_count", -1);
    entry->infer_timeout_ms = ReadNonNegativeIntOrDefault(manifest, "infer_timeout_ms", -1);
    entry->estimated_avg_infer_time_ms = ReadNonNegativeIntOrDefault(manifest, "estimated_avg_infer_time_ms", -1);
    entry->p95_infer_time_ms = ReadNonNegativeIntOrDefault(manifest, "p95_infer_time_ms", -1);
    entry->max_concurrent_requests = ReadNonNegativeIntOrDefault(manifest, "max_concurrent_requests", -1);
    entry->supports_concurrent_infer = ReadBooleanOrDefault(manifest, "supports_concurrent_infer", true);
    entry->allow_resource_sharing = ReadBooleanOrDefault(manifest, "allow_resource_sharing", false);
    entry->manifest = manifest;
    return true;
}

bool ValidatePluginManifest(
    const std::filesystem::path& capability_dir,
    const std::string& target_name,
    const nlohmann::json& manifest,
    const std::string& binary_path,
    PluginEntry* entry,
    std::string* error_message) {
    std::string capability_name;
    std::string model_version;
    std::string manifest_target_name;
    std::string artifact_format;
    std::string build_mode;
    std::string toolchain_name;
    std::string customer_code;
    int issue_record_id = 0;
    bool jni_enabled = false;
    nlohmann::json dependency_summary;
    if (!ReadRequiredString(manifest, "capability_name", &capability_name, error_message) ||
        !ReadRequiredString(manifest, "model_version", &model_version, error_message) ||
        !ReadRequiredString(manifest, "target_name", &manifest_target_name, error_message) ||
        !ReadRequiredString(manifest, "artifact_format", &artifact_format, error_message) ||
        !ReadRequiredString(manifest, "build_mode", &build_mode, error_message) ||
        !ReadRequiredString(manifest, "toolchain_name", &toolchain_name, error_message) ||
        !ReadRequiredBoolean(manifest, "jni_enabled", &jni_enabled, error_message) ||
        !ReadRequiredString(manifest, "customer_code", &customer_code, error_message) ||
        !ReadRequiredInteger(manifest, "issue_record_id", &issue_record_id, error_message) ||
        !ReadRequiredObject(manifest, "dependency_summary", &dependency_summary, error_message)) {
        return false;
    }
    if (capability_name != capability_dir.filename().string()) {
        if (error_message != nullptr) {
            *error_message = "插件 manifest capability_name 与目录名不一致。";
        }
        return false;
    }
    if (manifest_target_name != target_name) {
        if (error_message != nullptr) {
            *error_message = "插件 manifest target_name 与当前目标平台不一致。";
        }
        return false;
    }
    std::string dependency_runtime;
    std::string dependency_abi;
    bool dependency_license_required = false;
    bool dependency_build_params_controlled = false;
    if (!ReadRequiredString(dependency_summary, "runtime", &dependency_runtime, error_message) ||
        !ReadRequiredString(dependency_summary, "abi", &dependency_abi, error_message) ||
        !ReadRequiredBoolean(
            dependency_summary,
            "license_required",
            &dependency_license_required,
            error_message) ||
        !ReadRequiredBoolean(
            dependency_summary,
            "build_params_controlled",
            &dependency_build_params_controlled,
            error_message)) {
        return false;
    }
    if (binary_path.empty() || !std::filesystem::exists(binary_path)) {
        if (error_message != nullptr) {
            *error_message = "插件二进制不存在。";
        }
        return false;
    }
    const auto binary_extension = std::filesystem::path(binary_path).extension().string();
    if ((artifact_format == "so" && binary_extension != ".so") ||
        (artifact_format == "dll" && binary_extension != ".dll")) {
        if (error_message != nullptr) {
            *error_message = "插件 manifest artifact_format 与二进制扩展名不一致。";
        }
        return false;
    }

    entry->plugin_root = capability_dir.lexically_normal().string();
    entry->plugin_target = manifest_target_name;
    entry->build_mode = build_mode;
    entry->binary_path = NormalizeExistingPath(binary_path).string();
    entry->declared_device_mode = manifest.value("device_mode", std::string("auto"));
    entry->capability_priority =
        manifest.contains("capability_priority") && manifest["capability_priority"].is_number_integer()
            ? manifest["capability_priority"].get<int>()
            : 100;
    entry->max_batch_size = ReadPositiveIntOrDefaultMinOne(manifest, "max_batch_size", 1);
    entry->min_batch_size = ReadPositiveIntOrDefaultMinOne(manifest, "min_batch_size", 1);
    entry->batch_wait_timeout_ms = ReadNonNegativeIntOrDefault(manifest, "batch_wait_timeout_ms", -1);
    entry->instance_count =
        manifest.contains("instance_count") && manifest["instance_count"].is_number_integer()
            ? std::max(1, manifest["instance_count"].get<int>())
            : 0;
    entry->queue_wait_timeout_ms = ReadNonNegativeIntOrDefault(manifest, "queue_wait_timeout_ms", -1);
    entry->max_pending_request_count = ReadNonNegativeIntOrDefault(manifest, "max_pending_request_count", -1);
    entry->infer_timeout_ms = ReadNonNegativeIntOrDefault(manifest, "infer_timeout_ms", -1);
    entry->estimated_avg_infer_time_ms = ReadNonNegativeIntOrDefault(manifest, "estimated_avg_infer_time_ms", -1);
    entry->p95_infer_time_ms = ReadNonNegativeIntOrDefault(manifest, "p95_infer_time_ms", -1);
    entry->max_concurrent_requests = ReadNonNegativeIntOrDefault(manifest, "max_concurrent_requests", -1);
    entry->supports_concurrent_infer = ReadBooleanOrDefault(manifest, "supports_concurrent_infer", true);
    entry->allow_resource_sharing = ReadBooleanOrDefault(manifest, "allow_resource_sharing", false);
    entry->manifest = manifest;
    return true;
}

ScanCollection<ModelEntry> ScanModels(const std::filesystem::path& root) {
    ScanCollection<ModelEntry> scanned;
    for (const auto& capability_dir : SortedDirs(root)) {
        const auto versions = SortedDirs(capability_dir);
        if (versions.empty()) {
            continue;
        }
        const auto selected_version_dir = versions.back();
        const auto manifest_path = selected_version_dir / "manifest.json";
        std::string error_message;
        const auto manifest = ReadJsonObject(manifest_path, &error_message);
        if (!manifest.has_value()) {
            AppendFailure(
                &scanned.failures,
                capability_dir.filename().string(),
                "model_manifest",
                manifest_path,
                error_message);
            continue;
        }
        ModelEntry entry;
        if (!ValidateModelManifest(
                capability_dir,
                selected_version_dir,
                *manifest,
                &entry,
                &error_message)) {
            AppendFailure(
                &scanned.failures,
                capability_dir.filename().string(),
                "model_manifest",
                manifest_path,
                error_message);
            continue;
        }
        scanned.items.emplace(capability_dir.filename().string(), std::move(entry));
    }
    return scanned;
}

ScanCollection<PluginEntry> ScanPlugins(const std::filesystem::path& root, const std::string& target_name) {
    ScanCollection<PluginEntry> scanned;
    const auto target_root = root / target_name;
    for (const auto& capability_dir : SortedDirs(target_root)) {
        const auto manifest_path = capability_dir / "manifest" / "manifest.json";
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
        std::string error_message;
        const auto manifest = ReadJsonObject(manifest_path, &error_message);
        if (!manifest.has_value()) {
            AppendFailure(
                &scanned.failures,
                capability_dir.filename().string(),
                "plugin_manifest",
                manifest_path,
                error_message);
            continue;
        }
        PluginEntry entry;
        if (!ValidatePluginManifest(
                capability_dir,
                target_name,
                *manifest,
                binary_path,
                &entry,
                &error_message)) {
            AppendFailure(
                &scanned.failures,
                capability_dir.filename().string(),
                "plugin_manifest",
                manifest_path,
                error_message);
            continue;
        }
        scanned.items.emplace(capability_dir.filename().string(), std::move(entry));
    }
    return scanned;
}

nlohmann::json SerializeFailures(const std::vector<ScanFailure>& failures) {
    nlohmann::json payload = nlohmann::json::array();
    for (const auto& failure : failures) {
        payload.push_back(
            {
                {"capability_name", failure.capability_name},
                {"manifest_type", failure.manifest_type},
                {"manifest_path", failure.manifest_path},
                {"reason", failure.reason},
            });
    }
    return payload;
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
    std::vector<ScanFailure> invalid_capability_failures;
    std::set<std::string> capability_names;
    for (const auto& item : host_models.items) capability_names.insert(item.first);
    for (const auto& item : image_models.items) capability_names.insert(item.first);
    for (const auto& item : host_plugins.items) capability_names.insert(item.first);
    for (const auto& item : image_plugins.items) capability_names.insert(item.first);

    for (const auto& capability_name : capability_names) {
        const auto host_model_it = host_models.items.find(capability_name);
        const auto image_model_it = image_models.items.find(capability_name);
        const auto host_plugin_it = host_plugins.items.find(capability_name);
        const auto image_plugin_it = image_plugins.items.find(capability_name);
        if ((host_model_it == host_models.items.end() && image_model_it == image_models.items.end()) ||
            (host_plugin_it == host_plugins.items.end() && image_plugin_it == image_plugins.items.end())) {
            continue;
        }

        const auto& model_entry =
            host_model_it != host_models.items.end() ? host_model_it->second : image_model_it->second;
        const auto& plugin_entry =
            host_plugin_it != host_plugins.items.end() ? host_plugin_it->second : image_plugin_it->second;
        const auto plugin_model_version = plugin_entry.manifest.value("model_version", std::string());
        if (plugin_model_version != model_entry.model_version) {
            AppendFailure(
                &invalid_capability_failures,
                capability_name,
                "capability_contract",
                std::filesystem::path(plugin_entry.plugin_root) / "manifest" / "manifest.json",
                "插件 manifest model_version 与模型包 manifest 不一致。");
            continue;
        }
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
                host_model_it != host_models.items.end() && host_plugin_it != host_plugins.items.end() ? "host" : "image",
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
        {"host_model_failures", SerializeFailures(host_models.failures)},
        {"host_plugin_failures", SerializeFailures(host_plugins.failures)},
        {"image_model_failures", SerializeFailures(image_models.failures)},
        {"image_plugin_failures", SerializeFailures(image_plugins.failures)},
        {"invalid_capability_failures", SerializeFailures(invalid_capability_failures)},
    };
    for (const auto& item : host_models.items) result.source_summary["host_models"].push_back(item.first);
    for (const auto& item : host_plugins.items) result.source_summary["host_plugins"].push_back(item.first);
    for (const auto& item : image_models.items) result.source_summary["image_models"].push_back(item.first);
    for (const auto& item : image_plugins.items) result.source_summary["image_plugins"].push_back(item.first);
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
