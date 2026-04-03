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
    RefreshCatalogAndPools();
    RegisterRoutes();
}

bool AiProdHttpServer::Start() {
    return server->listen(config.bind_host, config.bind_port);
}

void AiProdHttpServer::Stop() {
    server->stop();
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
    const std::string digest = Sha256Hex(
        capability_name + "|" + catalog_entry->model_version + "|" + infer_request.input_type + "|" +
        infer_request.payload + "|" + infer_request.options.dump());

    if (infer_request.simulate_delay_ms > 0) {
        std::this_thread::sleep_for(std::chrono::milliseconds(infer_request.simulate_delay_ms));
    }

    const bool released = pool->Release(lease->slot_index);
    (void)released;

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

void AiProdHttpServer::HandleAdminTransitionRequest(
    const httplib::Request& request,
    httplib::Response& response,
    bool rollback) {
    const auto content_type = request.get_header_value("Content-Type");
    auto headers = BuildForwardHeaders(request);

    if (!licenseManager.GetStatus().valid) {
        ApplyJsonErrorResponse(403, "license 未授权或已失效，无法执行运行时切换。", response);
        return;
    }

    if (!RefreshCatalogAndPools()) {
        const auto backend_response = rollback
            ? backendClient.ForwardRollback(request.body, content_type, headers)
            : backendClient.ForwardPost(request.path, request.body, content_type, headers);
        ApplyBackendResponse(backend_response, response);
        return;
    }

    for (const auto& entry : capabilityCatalog.ListEntries()) {
        if (!licenseManager.QuickCheck(entry.capability_name, entry.model_version)) {
            ApplyJsonErrorResponse(403, "当前 license 未覆盖已装载能力，无法执行运行时切换。", response);
            return;
        }
    }

    const auto pools = ListInstancePools();
    BeginDrainOnPools(pools);
    if (!WaitForPoolsIdle(pools, std::chrono::duration_cast<std::chrono::milliseconds>(kDrainTimeout))) {
        EndDrainOnPools(pools);
        ApplyJsonErrorResponse(503, "当前仍有推理请求执行中，暂时无法切换运行时。", response);
        return;
    }

    const auto backend_response = rollback
        ? backendClient.ForwardRollback(request.body, content_type, headers)
        : backendClient.ForwardPost(request.path, request.body, content_type, headers);
    if (backend_response.status >= 200 && backend_response.status < 300) {
        if (!RefreshCatalogAndPoolsWithRetry(kRefreshRetryAttempts, kRefreshRetryInterval, true)) {
            EndDrainOnPools(pools);
            ApplyJsonErrorResponse(502, "运行时切换已提交，但 C++ 侧目录刷新失败。", response);
            return;
        }
        ApplyBackendResponse(backend_response, response);
        return;
    }

    EndDrainOnPools(pools);
    ApplyBackendResponse(backend_response, response);
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
