#include "http_server.h"

#include <algorithm>
#include <cctype>
#include <chrono>
#include <cmath>
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <map>
#include <openssl/sha.h>
#include <random>
#include <sstream>
#include <string>
#include <thread>

namespace {

constexpr char kDefaultJsonContentType[] = "application/json; charset=utf-8";
constexpr char kInstanceIdHeader[] = "X-AI-Prod-Instance-Id";
constexpr char kPreferredDeviceHeader[] = "X-AI-Prod-Preferred-Device";
constexpr char kRuntimeRevisionIdHeader[] = "X-AI-Prod-Runtime-Revision-Id";
constexpr auto kDrainTimeout = std::chrono::seconds(5);
constexpr auto kRefreshRetryInterval = std::chrono::milliseconds(100);
constexpr int kRefreshRetryAttempts = 10;
constexpr int kMaxSimulateDelayMs = 2000;

struct AdminTransitionRequestPayload {
    std::string action = "reload";
    std::optional<int> target_revision_id;
};

struct InferRequestPayload {
    std::string input_type = "json";
    std::string payload;
    std::string prefer_device = "auto";
    nlohmann::json options = nlohmann::json::object();
    int simulate_delay_ms = 0;
};

std::string ToLowerCopy(const std::string& value) {
    std::string lowered = value;
    std::transform(
        lowered.begin(),
        lowered.end(),
        lowered.begin(),
        [](unsigned char ch) { return static_cast<char>(std::tolower(ch)); });
    return lowered;
}

bool ShouldForwardHeader(const std::string& key) {
    const std::string lowered = ToLowerCopy(key);
    return lowered != "host" &&
           lowered != "content-length" &&
           lowered != "transfer-encoding" &&
           lowered != "connection";
}

std::string EscapeJson(const std::string& value) {
    std::string escaped;
    escaped.reserve(value.size());
    for (char ch : value) {
        switch (ch) {
            case '\\':
                escaped += "\\\\";
                break;
            case '"':
                escaped += "\\\"";
                break;
            case '\n':
                escaped += "\\n";
                break;
            case '\r':
                escaped += "\\r";
                break;
            case '\t':
                escaped += "\\t";
                break;
            default:
                escaped += ch;
                break;
        }
    }
    return escaped;
}

void ApplyJsonErrorResponse(
    int status,
    const std::string& message,
    httplib::Response& response) {
    response.status = status;
    response.set_content(
        "{\"status\":\"error\",\"message\":\"" + EscapeJson(message) + "\"}",
        kDefaultJsonContentType);
}

nlohmann::json BuildLicenseStatusPayload(const LicenseStatusInfo& status) {
    return {
        {"valid", status.valid},
        {"reason", status.reason},
        {"checked_at_cst", status.checked_at_cst},
        {"customer_code", status.customer_code},
        {"capability_scope", status.capability_scope},
        {"version_constraints", status.version_constraints},
        {"hardware_fingerprint", status.hardware_fingerprint},
    };
}

std::string CurrentCstIsoString() {
    const auto now = std::time(nullptr) + 8 * 60 * 60;
    std::tm cst_time{};
#ifdef _WIN32
    gmtime_s(&cst_time, &now);
#else
    gmtime_r(&now, &cst_time);
#endif
    std::ostringstream output;
    output << std::put_time(&cst_time, "%Y-%m-%dT%H:%M:%S") << "+08:00";
    return output.str();
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
    output << std::put_time(&utc_time, "%Y-%m-%dT%H:%M:%S") << "Z";
    return output.str();
}

void AppendJsonLine(const std::string& path, const nlohmann::json& payload) {
    const std::filesystem::path log_path(path);
    if (!log_path.parent_path().empty()) {
        std::filesystem::create_directories(log_path.parent_path());
    }
    std::ofstream output(log_path, std::ios::app);
    if (!output.is_open()) {
        return;
    }
    output << payload.dump() << "\n";
}

void AppendAuditLog(
    const ProxyConfig& config,
    const std::string& action,
    const std::string& entity_type,
    const std::string& entity_id,
    const nlohmann::json& detail) {
    AppendJsonLine(
        config.audit_log_path,
        {
            {"happened_at_cst", CurrentCstIsoString()},
            {"action", action},
            {"entity_type", entity_type},
            {"entity_id", entity_id},
            {"detail", detail},
        });
}

bool ParseInferRequest(const std::string& body, InferRequestPayload* request, std::string* error_message) {
    try {
        const auto payload = nlohmann::json::parse(body.empty() ? "{}" : body);
        if (!payload.is_object()) {
            *error_message = "请求体必须是 JSON 对象。";
            return false;
        }
        request->input_type = payload.value("input_type", "json");
        request->payload = payload.value("payload", "");
        request->prefer_device = payload.value("prefer_device", "auto");
        request->options = payload.contains("options") ? payload["options"] : nlohmann::json::object();
        if (!request->options.is_object()) {
            *error_message = "options 必须是 JSON 对象。";
            return false;
        }
        if (request->payload.empty()) {
            *error_message = "payload 不能为空。";
            return false;
        }
        if (request->input_type != "json" && request->input_type != "image" &&
            request->input_type != "video" && request->input_type != "pdf") {
            *error_message = "input_type 不受支持。";
            return false;
        }
        if (request->prefer_device != "auto" && request->prefer_device != "gpu" &&
            request->prefer_device != "cpu") {
            *error_message = "prefer_device 不受支持。";
            return false;
        }
        if (request->options.contains("simulate_delay_ms") && request->options["simulate_delay_ms"].is_number_integer()) {
            request->simulate_delay_ms = std::clamp(request->options["simulate_delay_ms"].get<int>(), 0, kMaxSimulateDelayMs);
        }
        return true;
    } catch (const std::exception&) {
        *error_message = "请求体不是合法 JSON。";
        return false;
    }
}

std::string GenerateRequestId() {
    std::random_device device;
    std::mt19937 generator(device());
    std::uniform_int_distribution<int> distribution(0, 15);
    std::uniform_int_distribution<int> variant_distribution(8, 11);
    std::ostringstream output;
    output << std::hex;
    for (int index = 0; index < 8; ++index) output << distribution(generator);
    output << "-";
    for (int index = 0; index < 4; ++index) output << distribution(generator);
    output << "-4";
    for (int index = 0; index < 3; ++index) output << distribution(generator);
    output << "-";
    output << variant_distribution(generator);
    for (int index = 0; index < 3; ++index) output << distribution(generator);
    output << "-";
    for (int index = 0; index < 12; ++index) output << distribution(generator);
    return output.str();
}

std::string Sha256Hex(const std::string& value) {
    unsigned char digest[SHA256_DIGEST_LENGTH];
    SHA256(reinterpret_cast<const unsigned char*>(value.data()), value.size(), digest);
    std::ostringstream output;
    output << std::hex << std::setfill('0');
    for (unsigned char byte : digest) {
        output << std::setw(2) << static_cast<int>(byte);
    }
    return output.str();
}

std::string ResolveDevice(const InferRequestPayload& request, const CapabilityCatalogEntry& entry) {
    const bool gpu_available = entry.device_mode != "cpu";
    if (request.prefer_device == "gpu") {
        return gpu_available ? "gpu" : "cpu";
    }
    if (request.prefer_device == "cpu") {
        return "cpu";
    }
    return gpu_available ? "gpu" : "cpu";
}

nlohmann::json SerializeRevisionRecord(const RuntimeRevisionRecord& record) {
    nlohmann::json payload = {
        {"revision_id", record.id},
        {"revision_token", record.revision_token},
        {"action", record.action},
        {"status", record.status},
        {"license_valid", record.license_valid},
        {"capability_names", record.capability_names},
        {"source_summary", record.source_summary},
        {"detail", record.detail},
        {"created_at", record.created_at.empty() ? nullptr : nlohmann::json(record.created_at)},
    };
    if (record.rollback_of_revision_id.has_value()) {
        payload["rollback_of_revision_id"] = *record.rollback_of_revision_id;
    } else {
        payload["rollback_of_revision_id"] = nullptr;
    }
    return payload;
}

bool ParseAdminTransitionRequest(
    const std::string& body,
    bool rollback_route,
    AdminTransitionRequestPayload* payload,
    std::string* error_message) {
    try {
        const auto parsed = nlohmann::json::parse(body.empty() ? "{}" : body);
        if (!parsed.is_object()) {
            *error_message = "请求体必须是 JSON 对象。";
            return false;
        }
        payload->action = rollback_route ? "rollback" : parsed.value("action", "reload");
        if (payload->action != "reload" && payload->action != "rollback") {
            *error_message = "仅支持 reload/rollback。";
            return false;
        }
        if (parsed.contains("target_revision_id") && !parsed["target_revision_id"].is_null()) {
            if (!parsed["target_revision_id"].is_number_integer() || parsed["target_revision_id"].get<int>() < 1) {
                *error_message = "target_revision_id 必须是正整数。";
                return false;
            }
            payload->target_revision_id = parsed["target_revision_id"].get<int>();
        }
        if (payload->action == "rollback" && !payload->target_revision_id.has_value()) {
            *error_message = "rollback 需要 target_revision_id。";
            return false;
        }
        return true;
    } catch (const std::exception&) {
        *error_message = "请求体不是合法 JSON。";
        return false;
    }
}

}

AiProdHttpServer::AiProdHttpServer(const ProxyConfig& config_value)
    : config(config_value),
      capabilityCatalog(config_value.runtime_snapshot_path),
      backendClient(config_value),
      licenseManager(
          config_value.license_root,
          config_value.hardware_features,
          config_value.license_auto_reload_interval_seconds),
      snapshotManager(config_value),
      server(std::make_unique<httplib::Server>()) {
    licenseManager.Initialize();
    licenseManager.StartAutoReloadMonitor();
    EnsureRuntimeReady();
    RegisterRoutes();
}

bool AiProdHttpServer::Start() {
    return server->listen(config.bind_host, config.bind_port);
}

void AiProdHttpServer::Stop() {
    server->stop();
}

bool AiProdHttpServer::EnsureRuntimeReady() {
    if (RefreshCatalogAndPools()) {
        std::string state_error;
        runtimeStateMachine.TransitionTo(RuntimeLifecycleState::kReady, &state_error);
        return true;
    }

    std::string state_error;
    if (!runtimeStateMachine.TransitionTo(RuntimeLifecycleState::kBootstrapping, &state_error)) {
        MarkRuntimeError(state_error);
        return false;
    }

    std::string bootstrap_error;
    if (!BootstrapRuntime(&bootstrap_error)) {
        MarkRuntimeError(bootstrap_error);
        AppendJsonLine(
            config.runtime_log_path,
            {
                {"event", "bootstrap_failed"},
                {"message", bootstrap_error},
            });
        AppendAuditLog(
            config,
            "bootstrap_failed",
            "runtime_revision",
            "bootstrap",
            {
                {"reason", bootstrap_error},
            });
        return false;
    }

    if (!RefreshCatalogAndPoolsWithRetry(kRefreshRetryAttempts, kRefreshRetryInterval, true)) {
        MarkRuntimeError("启动自举已完成，但 C++ 侧目录刷新失败。");
        return false;
    }
    runtimeStateMachine.TransitionTo(RuntimeLifecycleState::kReady, &state_error);
    return true;
}

httplib::Headers AiProdHttpServer::BuildForwardHeaders(const httplib::Request& request) {
    httplib::Headers headers;
    for (const auto& header : request.headers) {
        if (ShouldForwardHeader(header.first)) {
            headers.emplace(header.first, header.second);
        }
    }
    return headers;
}

void AiProdHttpServer::ApplyBackendResponse(
    const BackendResponse& backend_response,
    httplib::Response& response) const {
    response.status = backend_response.status;
    response.set_content(
        backend_response.body,
        backend_response.content_type.empty() ? kDefaultJsonContentType : backend_response.content_type.c_str());
}

void AiProdHttpServer::ApplySnapshotOrBackendResponse(
    const SnapshotResponse& snapshot_response,
    const httplib::Request& request,
    httplib::Response& response) const {
    if (snapshot_response.ok) {
        response.status = 200;
        response.set_content(snapshot_response.body, kDefaultJsonContentType);
        return;
    }
    ApplyBackendResponse(backendClient.ForwardGet(request.path, BuildForwardHeaders(request)), response);
}

bool AiProdHttpServer::RefreshCatalogAndPools(bool force_rebuild) {
    std::lock_guard<std::mutex> guard(runtimeStateMutex);
    const bool snapshot_ready = capabilityCatalog.RefreshIfNeeded(config.snapshot_max_age_seconds);
    if (!snapshot_ready) {
        return false;
    }

    const int revision_id = capabilityCatalog.GetRevisionId();
    if (!force_rebuild && revision_id == activeCatalogRevisionId && !instancePools.empty()) {
        return true;
    }

    std::map<std::string, std::shared_ptr<InstancePool>> next_pools;
    for (const auto& entry : capabilityCatalog.ListEntries()) {
        auto pool = std::make_shared<InstancePool>();
        pool->Reset(
            entry.capability_name,
            entry.pool_size > 0 ? entry.pool_size : config.pool_size,
            entry.device_mode != "cpu");
        next_pools.emplace(entry.capability_name, std::move(pool));
    }
    instancePools = std::move(next_pools);
    activeCatalogRevisionId = revision_id;
    pluginExecutor.SyncEntries(capabilityCatalog.ListEntries());
    return true;
}

bool AiProdHttpServer::RefreshCatalogAndPoolsWithRetry(
    int attempts,
    std::chrono::milliseconds wait_interval,
    bool force_rebuild) {
    for (int attempt = 0; attempt < attempts; ++attempt) {
        if (RefreshCatalogAndPools(force_rebuild)) {
            return true;
        }
        std::this_thread::sleep_for(wait_interval);
    }
    return false;
}

nlohmann::json AiProdHttpServer::BuildCatalogPayload(bool snapshot_ready) const {
    std::lock_guard<std::mutex> guard(runtimeStateMutex);
    nlohmann::json items = nlohmann::json::array();
    for (const auto& entry : capabilityCatalog.ListEntries()) {
        int busy_count = 0;
        int total_size = entry.pool_size;
        const auto pool_it = instancePools.find(entry.capability_name);
        if (pool_it != instancePools.end() && pool_it->second) {
            busy_count = pool_it->second->GetBusyCount();
            total_size = pool_it->second->GetTotalSize();
        }
        items.push_back(
            {
                {"capability_name", entry.capability_name},
                {"plugin_target", entry.plugin_target},
                {"model_version", entry.model_version},
                {"backend_type", entry.backend_type},
                {"active_source", entry.active_source},
                {"device_mode", entry.device_mode},
                {"model_root", entry.model_root},
                {"binary_path", entry.binary_path},
                {"pool_size", total_size},
                {"busy_count", busy_count},
                {"draining", pool_it != instancePools.end() && pool_it->second ? pool_it->second->IsDraining() : false},
                {"revision_id", entry.revision_id},
            });
    }

    bool draining = false;
    for (const auto& item : instancePools) {
        if (item.second && item.second->IsDraining()) {
            draining = true;
            break;
        }
    }

    return {
        {"service", "ai-prod-cpp-http"},
        {"snapshot_ready", snapshot_ready},
        {"runtime_state", runtimeStateMachine.GetStateName()},
        {"runtime_state_error", runtimeStateMachine.GetLastError().empty()
                                    ? nlohmann::json(nullptr)
                                    : nlohmann::json(runtimeStateMachine.GetLastError())},
        {"draining", draining},
        {"runtime_revision_id", capabilityCatalog.GetRevisionId()},
        {"items", items},
    };
}

std::shared_ptr<InstancePool> AiProdHttpServer::GetInstancePool(const std::string& capability_name) const {
    std::lock_guard<std::mutex> guard(runtimeStateMutex);
    const auto it = instancePools.find(capability_name);
    if (it == instancePools.end()) {
        return {};
    }
    return it->second;
}

std::vector<std::shared_ptr<InstancePool>> AiProdHttpServer::ListInstancePools() const {
    std::lock_guard<std::mutex> guard(runtimeStateMutex);
    std::vector<std::shared_ptr<InstancePool>> pools;
    pools.reserve(instancePools.size());
    for (const auto& entry : instancePools) {
        if (entry.second) {
            pools.push_back(entry.second);
        }
    }
    return pools;
}

void AiProdHttpServer::BeginDrainOnPools(const std::vector<std::shared_ptr<InstancePool>>& pools) {
    for (const auto& pool : pools) {
        if (pool) {
            pool->BeginDrain();
        }
    }
}

void AiProdHttpServer::EndDrainOnPools(const std::vector<std::shared_ptr<InstancePool>>& pools) {
    for (const auto& pool : pools) {
        if (pool) {
            pool->EndDrain();
        }
    }
}

bool AiProdHttpServer::WaitForPoolsIdle(
    const std::vector<std::shared_ptr<InstancePool>>& pools,
    std::chrono::milliseconds timeout) {
    const auto deadline = std::chrono::steady_clock::now() + timeout;
    for (const auto& pool : pools) {
        if (!pool) {
            continue;
        }
        const auto now = std::chrono::steady_clock::now();
        if (now >= deadline) {
            return false;
        }
        if (!pool->WaitForIdle(std::chrono::duration_cast<std::chrono::milliseconds>(deadline - now))) {
            return false;
        }
    }
    return true;
}

void AiProdHttpServer::HandleInferRequest(
    const httplib::Request& request,
    httplib::Response& response) {
    const std::string capability_name =
        request.matches.size() > 1 ? request.matches[1].str() : std::string();
    if (!RefreshCatalogAndPools()) {
        const auto content_type = request.get_header_value("Content-Type");
        auto headers = BuildForwardHeaders(request);
        ApplyBackendResponse(
            backendClient.ForwardPost(request.path, request.body, content_type, headers),
            response);
        return;
    }

    const auto catalog_entry = capabilityCatalog.GetEntry(capability_name);
    if (!catalog_entry.has_value()) {
        ApplyJsonErrorResponse(404, "能力不存在或未装载。", response);
        return;
    }

    if (!licenseManager.QuickCheck(capability_name, catalog_entry->model_version)) {
        AppendAuditLog(
            config,
            "infer_license_rejected",
            "capability",
            capability_name,
            {
                {"reason", "当前 license 未授权该能力或版本。"},
                {"model_version", catalog_entry->model_version},
            });
        ApplyJsonErrorResponse(403, "当前 license 未授权该能力或版本。", response);
        return;
    }

    const auto pool = GetInstancePool(capability_name);
    if (!pool) {
        ApplyJsonErrorResponse(503, "能力实例池不可用。", response);
        return;
    }

    if (pool->IsDraining()) {
        ApplyJsonErrorResponse(503, "能力正在切换，请稍后重试。", response);
        return;
    }

    const auto lease = pool->Acquire();
    if (!lease.has_value()) {
        if (pool->IsDraining()) {
            ApplyJsonErrorResponse(503, "能力正在切换，请稍后重试。", response);
            return;
        }
        ApplyJsonErrorResponse(503, "能力实例池繁忙，请稍后重试。", response);
        return;
    }

    InferRequestPayload infer_request;
    std::string parse_error;
    if (!ParseInferRequest(request.body, &infer_request, &parse_error)) {
        pool->Release(lease->slot_index);
        ApplyJsonErrorResponse(400, parse_error, response);
        return;
    }

    const std::string device = ResolveDevice(infer_request, *catalog_entry);
    const std::string request_id = GenerateRequestId();
    if (infer_request.simulate_delay_ms > 0) {
        std::this_thread::sleep_for(std::chrono::milliseconds(infer_request.simulate_delay_ms));
    }

    PluginExecutionResult plugin_result;
    std::string plugin_error;
    const bool plugin_ok = pluginExecutor.Execute(
        *catalog_entry,
        static_cast<std::size_t>(lease->slot_index),
        infer_request.input_type,
        infer_request.payload,
        infer_request.options,
        device,
        &plugin_result,
        &plugin_error);
    const bool released = pool->Release(lease->slot_index);
    (void)released;
    if (!plugin_ok) {
        ApplyJsonErrorResponse(503, plugin_error.empty() ? "能力插件执行失败。" : plugin_error, response);
        return;
    }

    const std::string digest = Sha256Hex(
        capability_name + "|" + catalog_entry->model_version + "|" + infer_request.input_type + "|" +
        infer_request.payload + "|" + plugin_result.plugin_result.dump());

    const nlohmann::json payload = {
        {"request_id", request_id},
        {"capability_name", capability_name},
        {"model_version", catalog_entry->model_version},
        {"backend_type", catalog_entry->backend_type},
        {"plugin_target", catalog_entry->plugin_target},
        {"device", device},
        {"runtime_revision_id", catalog_entry->revision_id},
        {"license_valid", true},
        {"result", {
            {"summary", capability_name + " 推理完成"},
            {"digest", digest},
            {"score", std::round((static_cast<double>(std::stoi(digest.substr(0, 4), nullptr, 16)) / 65535.0) * 10000.0) / 10000.0},
            {"input_type", infer_request.input_type},
            {"payload_size", infer_request.payload.size()},
            {"instance_id", lease->instance_id},
            {"fallback_applied", infer_request.prefer_device == "gpu" && device == "cpu"},
            {"infer_time_ms", plugin_result.infer_time_ms},
            {"plugin_result", plugin_result.plugin_result},
        }},
    };

    AppendJsonLine(
        config.runtime_log_path,
        {
            {"event", "infer"},
            {"request_id", request_id},
            {"capability_name", capability_name},
            {"device", device},
            {"runtime_revision_id", catalog_entry->revision_id},
        });
    AppendAuditLog(
        config,
        "infer",
        "capability",
        capability_name,
        {
            {"request_id", request_id},
            {"device", device},
            {"instance_id", lease->instance_id},
        });

    response.status = 200;
    response.set_content(payload.dump(), kDefaultJsonContentType);
}

std::optional<nlohmann::json> AiProdHttpServer::ExecuteRuntimeTransition(
    const std::string& action,
    std::optional<int> target_revision_id,
    std::string* error_message) {
    const auto scan_result = RuntimeResourceScanner::ResolveSources(
        config.host_root,
        config.image_resource_root,
        RuntimeResourceScanner::DetectPlatformTarget());
    std::map<std::string, RuntimeCapabilityRecord> selected_capabilities = scan_result.capabilities;

    RevisionStore revision_store(config.database_path);
    if (!revision_store.EnsureSchema(error_message)) {
        return std::nullopt;
    }

    std::optional<int> rollback_of_revision_id;
    if (action == "rollback") {
        const auto source_revision = revision_store.GetRevision(*target_revision_id, error_message);
        if (!source_revision.has_value()) {
            *error_message = "目标 revision 不存在。";
            return std::nullopt;
        }
        rollback_of_revision_id = source_revision->id;
        std::map<std::string, RuntimeCapabilityRecord> filtered_capabilities;
        for (const auto& capability_item : source_revision->capability_names) {
            if (!capability_item.is_string()) {
                continue;
            }
            const auto capability_it = scan_result.capabilities.find(capability_item.get<std::string>());
            if (capability_it != scan_result.capabilities.end()) {
                filtered_capabilities.emplace(capability_it->first, capability_it->second);
            }
        }
        selected_capabilities = std::move(filtered_capabilities);
    }

    const auto current_license_status = licenseManager.GetStatus();
    if (!current_license_status.valid) {
        *error_message = "license 未授权或已失效，无法执行运行时切换。";
        return std::nullopt;
    }

    for (const auto& capability_entry : selected_capabilities) {
        if (!licenseManager.QuickCheck(capability_entry.first, capability_entry.second.model_version)) {
            AppendAuditLog(
                config,
                action + "_license_rejected",
                "capability",
                capability_entry.first,
                {
                    {"reason", "当前 license 未授权该能力或版本。"},
                    {"model_version", capability_entry.second.model_version},
                });
            *error_message = "当前 license 未覆盖目标能力或版本。";
            return std::nullopt;
        }
    }

    nlohmann::json capability_names = nlohmann::json::array();
    nlohmann::json snapshot_capabilities = nlohmann::json::array();
    for (const auto& capability_entry : selected_capabilities) {
        capability_names.push_back(capability_entry.first);
    }

    const nlohmann::json license_status = {
        {"valid", current_license_status.valid},
        {"reason", current_license_status.reason},
        {"checked_at_cst", current_license_status.checked_at_cst},
        {"customer_code", current_license_status.customer_code},
        {"capability_scope", current_license_status.capability_scope},
        {"version_constraints", current_license_status.version_constraints},
        {"hardware_fingerprint", current_license_status.hardware_fingerprint},
    };

    nlohmann::json detail = {
        {"license_status", license_status},
    };
    if (rollback_of_revision_id.has_value()) {
        detail["rollback_to"] = *rollback_of_revision_id;
    }

    const auto revision = revision_store.CreateRevision(
        GenerateRequestId(),
        action,
        "active",
        scan_result.source_summary,
        capability_names,
        true,
        detail,
        rollback_of_revision_id,
        error_message);
    if (!revision.has_value()) {
        return std::nullopt;
    }

    for (const auto& capability_entry : selected_capabilities) {
        snapshot_capabilities.push_back(
            {
                {"capability_name", capability_entry.first},
                {"plugin_target", capability_entry.second.plugin_target},
                {"model_version", capability_entry.second.model_version},
                {"backend_type", capability_entry.second.backend_type},
                {"active_source", capability_entry.second.active_source},
                {"model_root", capability_entry.second.model_root},
                {"binary_path", capability_entry.second.binary_path},
                {"device_mode", config.gpu_available ? "gpu/cpu" : "cpu"},
                {"pool_size", config.pool_size},
                {"revision_id", revision->id},
            });
    }

    nlohmann::json snapshot_payload = {
        {"snapshot_version", 1},
        {"updated_at_utc", CurrentUtcIsoString()},
        {"revision_id", revision->id},
        {"revision_token", revision->revision_token},
        {"capability_names", capability_names},
        {"capability_count", static_cast<int>(selected_capabilities.size())},
        {"capabilities", snapshot_capabilities},
        {"source_summary", scan_result.source_summary},
        {"license_status", {
            {"valid", current_license_status.valid},
            {"reason", current_license_status.reason},
            {"checked_at_cst", current_license_status.checked_at_cst},
            {"customer_code", current_license_status.customer_code},
            {"capability_scope", current_license_status.capability_scope},
            {"version_constraints", current_license_status.version_constraints},
            {"hardware_fingerprint", current_license_status.hardware_fingerprint},
            {"runtime_revision_id", revision->id},
        }},
        {"service_name", "ai-prod"},
        {"company_name", "北京爱知之星科技股份有限公司（Agile Star）"},
        {"company_domain", "agilestar.cn"},
    };
    if (!snapshotManager.WriteSnapshot(snapshot_payload)) {
        *error_message = "runtime snapshot 写入失败。";
        return std::nullopt;
    }

    AppendJsonLine(
        config.runtime_log_path,
        {
            {"event", action},
            {"revision_id", revision->id},
            {"active_capability_count", static_cast<int>(selected_capabilities.size())},
        });
    AppendAuditLog(
        config,
        action,
        "runtime_revision",
        std::to_string(revision->id),
        {
            {"active_capability_count", static_cast<int>(selected_capabilities.size())},
        });

    const auto operation = revision_store.CreateOperation(
        action,
        "completed",
        {
            {"active_capability_count", static_cast<int>(selected_capabilities.size())},
        },
        revision->id,
        error_message);
    if (!operation.has_value()) {
        return std::nullopt;
    }

    return nlohmann::json{
        {"operation_id", operation->id},
        {"revision", SerializeRevisionRecord(*revision)},
        {"active_capability_count", static_cast<int>(selected_capabilities.size())},
    };
}

void AiProdHttpServer::MarkRuntimeError(const std::string& error_message) {
    runtimeStateMachine.MarkError(error_message);
}

void AiProdHttpServer::HandleAdminTransitionRequest(
    const httplib::Request& request,
    httplib::Response& response,
    bool rollback) {
    std::unique_lock<std::mutex> transition_guard(runtimeTransitionMutex, std::try_to_lock);
    if (!transition_guard.owns_lock()) {
        ApplyJsonErrorResponse(409, "已有运行时切换任务正在执行。", response);
        return;
    }
    AdminTransitionRequestPayload transition_request;
    std::string parse_error;
    if (!ParseAdminTransitionRequest(request.body, rollback, &transition_request, &parse_error)) {
        ApplyJsonErrorResponse(400, parse_error, response);
        return;
    }

    if (!licenseManager.GetStatus().valid) {
        ApplyJsonErrorResponse(403, "license 未授权或已失效，无法执行运行时切换。", response);
        return;
    }

    for (const auto& entry : capabilityCatalog.ListEntries()) {
        if (!licenseManager.QuickCheck(entry.capability_name, entry.model_version)) {
            ApplyJsonErrorResponse(403, "当前 license 未覆盖已装载能力，无法执行运行时切换。", response);
            return;
        }
    }

    std::string state_error;
    if (!runtimeStateMachine.TransitionTo(RuntimeLifecycleState::kDraining, &state_error)) {
        ApplyJsonErrorResponse(409, state_error, response);
        return;
    }
    const auto pools = ListInstancePools();
    BeginDrainOnPools(pools);
    if (!WaitForPoolsIdle(pools, std::chrono::duration_cast<std::chrono::milliseconds>(kDrainTimeout))) {
        EndDrainOnPools(pools);
        runtimeStateMachine.TransitionTo(RuntimeLifecycleState::kReady, &state_error);
        ApplyJsonErrorResponse(503, "当前仍有推理请求执行中，暂时无法切换运行时。", response);
        return;
    }

    if (!runtimeStateMachine.TransitionTo(RuntimeLifecycleState::kTransitioning, &state_error)) {
        EndDrainOnPools(pools);
        runtimeStateMachine.TransitionTo(RuntimeLifecycleState::kReady, nullptr);
        ApplyJsonErrorResponse(409, state_error, response);
        return;
    }
    std::string transition_error;
    const auto transition_result = ExecuteRuntimeTransition(
        transition_request.action,
        transition_request.target_revision_id,
        &transition_error);
    if (!transition_result.has_value()) {
        EndDrainOnPools(pools);
        runtimeStateMachine.TransitionTo(RuntimeLifecycleState::kReady, nullptr);
        const int status_code =
            transition_error.find("license") != std::string::npos || transition_error.find("未覆盖") != std::string::npos
                ? 403
                : 400;
        ApplyJsonErrorResponse(status_code, transition_error.empty() ? "运行时切换失败。" : transition_error, response);
        return;
    }

    if (!RefreshCatalogAndPoolsWithRetry(kRefreshRetryAttempts, kRefreshRetryInterval, true)) {
        EndDrainOnPools(pools);
        MarkRuntimeError("运行时切换已完成，但 C++ 侧目录刷新失败。");
        ApplyJsonErrorResponse(502, "运行时切换已完成，但 C++ 侧目录刷新失败。", response);
        return;
    }
    EndDrainOnPools(pools);
    runtimeStateMachine.TransitionTo(RuntimeLifecycleState::kReady, nullptr);
    response.status = 200;
    response.set_content(transition_result->dump(), kDefaultJsonContentType);
}

void AiProdHttpServer::HandleLicenseStatusRequest(
    const httplib::Request&,
    httplib::Response& response) const {
    response.status = 200;
    response.set_content(
        BuildLicenseStatusPayload(licenseManager.GetStatus()).dump(),
        kDefaultJsonContentType);
}

void AiProdHttpServer::HandleLicenseReloadRequest(
    const httplib::Request&,
    httplib::Response& response) {
    if (licenseManager.Reload()) {
        response.status = 200;
        response.set_content(
            nlohmann::json{
                {"status", "ok"},
                {"license_status", BuildLicenseStatusPayload(licenseManager.GetStatus())},
            }.dump(),
            kDefaultJsonContentType);
        return;
    }

    const auto failure_status = licenseManager.GetLastReloadFailureStatus();
    response.status = 400;
    response.set_content(
        nlohmann::json{
            {"status", "error"},
            {"message", failure_status.reason},
            {"license_status", BuildLicenseStatusPayload(failure_status)},
        }.dump(),
        kDefaultJsonContentType);
}

bool AiProdHttpServer::BootstrapRuntime(std::string* error_message) {
    auto set_error = [&](const std::string& message) {
        if (error_message != nullptr) {
            *error_message = message;
        }
    };
    const auto scan_result = RuntimeResourceScanner::ResolveSources(
        config.host_root,
        config.image_resource_root,
        RuntimeResourceScanner::DetectPlatformTarget());
    const auto& selected_capabilities = scan_result.capabilities;
    if (selected_capabilities.empty()) {
        set_error("未发现可用能力资源，无法完成启动自举。");
        return false;
    }

    const auto current_license_status = licenseManager.GetStatus();
    if (!current_license_status.valid) {
        set_error("license 未授权或已失效，无法完成启动自举。");
        return false;
    }

    for (const auto& capability_entry : selected_capabilities) {
        if (!licenseManager.QuickCheck(capability_entry.first, capability_entry.second.model_version)) {
            AppendAuditLog(
                config,
                "bootstrap_license_rejected",
                "capability",
                capability_entry.first,
                {
                    {"reason", "当前 license 未授权该能力或版本。"},
                    {"model_version", capability_entry.second.model_version},
                });
            set_error("当前 license 未覆盖启动阶段目标能力或版本。");
            return false;
        }
    }

    RevisionStore revision_store(config.database_path);
    if (!revision_store.EnsureSchema(error_message)) {
        return false;
    }

    nlohmann::json capability_names = nlohmann::json::array();
    nlohmann::json snapshot_capabilities = nlohmann::json::array();
    for (const auto& capability_entry : selected_capabilities) {
        capability_names.push_back(capability_entry.first);
    }

    const nlohmann::json license_status = {
        {"valid", current_license_status.valid},
        {"reason", current_license_status.reason},
        {"checked_at_cst", current_license_status.checked_at_cst},
        {"customer_code", current_license_status.customer_code},
        {"capability_scope", current_license_status.capability_scope},
        {"version_constraints", current_license_status.version_constraints},
        {"hardware_fingerprint", current_license_status.hardware_fingerprint},
        {"validated_capability_names", capability_names},
        {"validation_action", "bootstrap"},
        {"validation_entity_id", "bootstrap"},
    };

    const auto revision = revision_store.CreateRevision(
        GenerateRequestId(),
        "bootstrap",
        "active",
        scan_result.source_summary,
        capability_names,
        true,
        {
            {"license_status", license_status},
        },
        std::nullopt,
        error_message);
    if (!revision.has_value()) {
        return false;
    }

    for (const auto& capability_entry : selected_capabilities) {
        snapshot_capabilities.push_back(
            {
                {"capability_name", capability_entry.first},
                {"plugin_target", capability_entry.second.plugin_target},
                {"model_version", capability_entry.second.model_version},
                {"backend_type", capability_entry.second.backend_type},
                {"active_source", capability_entry.second.active_source},
                {"model_root", capability_entry.second.model_root},
                {"binary_path", capability_entry.second.binary_path},
                {"device_mode", config.gpu_available ? "gpu/cpu" : "cpu"},
                {"pool_size", config.pool_size},
                {"revision_id", revision->id},
            });
    }

    nlohmann::json snapshot_payload = {
        {"snapshot_version", 1},
        {"updated_at_utc", CurrentUtcIsoString()},
        {"revision_id", revision->id},
        {"revision_token", revision->revision_token},
        {"capability_names", capability_names},
        {"capability_count", static_cast<int>(selected_capabilities.size())},
        {"capabilities", snapshot_capabilities},
        {"source_summary", scan_result.source_summary},
        {"license_status", {
            {"valid", current_license_status.valid},
            {"reason", current_license_status.reason},
            {"checked_at_cst", current_license_status.checked_at_cst},
            {"customer_code", current_license_status.customer_code},
            {"capability_scope", current_license_status.capability_scope},
            {"version_constraints", current_license_status.version_constraints},
            {"hardware_fingerprint", current_license_status.hardware_fingerprint},
            {"validated_capability_names", capability_names},
            {"validation_action", "bootstrap"},
            {"validation_entity_id", "bootstrap"},
            {"runtime_revision_id", revision->id},
        }},
        {"service_name", "ai-prod"},
        {"company_name", "北京爱知之星科技股份有限公司（Agile Star）"},
        {"company_domain", "agilestar.cn"},
    };
    if (!snapshotManager.WriteSnapshot(snapshot_payload)) {
        set_error("runtime snapshot 启动写入失败。");
        return false;
    }

    AppendJsonLine(
        config.runtime_log_path,
        {
            {"event", "bootstrap"},
            {"revision_id", revision->id},
            {"capability_count", static_cast<int>(selected_capabilities.size())},
            {"license_valid", current_license_status.valid},
        });
    AppendAuditLog(
        config,
        "bootstrap",
        "runtime_revision",
        std::to_string(revision->id),
        {
            {"capability_count", static_cast<int>(selected_capabilities.size())},
            {"license_valid", current_license_status.valid},
        });

    const auto operation = revision_store.CreateOperation(
        "bootstrap",
        "completed",
        {
            {"active_capability_count", static_cast<int>(selected_capabilities.size())},
        },
        revision->id,
        error_message);
    return operation.has_value();
}

void AiProdHttpServer::RegisterRoutes() {
    server->Get("/", [&](const httplib::Request&, httplib::Response& response) {
        std::ostringstream payload;
        payload << "{"
                << "\"service\":\"ai-prod-cpp-http\","
                << "\"mode\":\"proxy\","
                << "\"backend\":\"" << EscapeJson(build_backend_base_url(config)) << "\","
                << "\"bind\":\"" << EscapeJson(config.bind_host + ":" + std::to_string(config.bind_port)) << "\""
                << "}";
        response.set_content(payload.str(), kDefaultJsonContentType);
    });

    server->Get("/api/v1/health", [&](const httplib::Request& request, httplib::Response& response) {
        ApplySnapshotOrBackendResponse(snapshotManager.BuildHealthResponse(), request, response);
    });
    server->Get("/api/v1/capabilities", [&](const httplib::Request& request, httplib::Response& response) {
        ApplySnapshotOrBackendResponse(snapshotManager.BuildCapabilitiesResponse(), request, response);
    });
    server->Get("/api/v1/license/status", [&](const httplib::Request& request, httplib::Response& response) {
        HandleLicenseStatusRequest(request, response);
    });
    server->Get("/api/v1/admin/catalog", [&](const httplib::Request&, httplib::Response& response) {
        const bool snapshot_ready = RefreshCatalogAndPools();
        response.status = 200;
        response.set_content(BuildCatalogPayload(snapshot_ready).dump(), kDefaultJsonContentType);
    });
    server->Post("/api/v1/admin/reload", [&](const httplib::Request& request, httplib::Response& response) {
        HandleAdminTransitionRequest(request, response, false);
    });
    server->Post("/api/v1/admin/rollback", [&](const httplib::Request& request, httplib::Response& response) {
        HandleAdminTransitionRequest(request, response, true);
    });
    server->Post("/api/v1/admin/license-reload", [&](const httplib::Request& request, httplib::Response& response) {
        HandleLicenseReloadRequest(request, response);
    });
    server->Post(R"(/api/v1/infer/([^/]+))", [&](const httplib::Request& request, httplib::Response& response) {
        HandleInferRequest(request, response);
    });
}
