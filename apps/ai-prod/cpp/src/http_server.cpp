#include "http_server.h"
#include "payload_codec.h"
#include "request_lease.h"

#include <algorithm>
#include <cctype>
#include <chrono>
#include <cmath>
#include <condition_variable>
#include <deque>
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <map>
#include <limits>
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
constexpr std::size_t kRecentLatencySampleLimit = 64;

struct AdminTransitionRequestPayload {
    std::string action = "reload";
    std::optional<int> target_revision_id;
};

struct InferRequestPayload {
    std::string input_type = "json";
    std::string payload;
    DecodedPayload decoded_payload;
    std::string prefer_device = "auto";
    int prefer_deadline_ms = -1;
    nlohmann::json options = nlohmann::json::object();
    int simulate_delay_ms = 0;
};

struct InferExecutionOutcome {
    int status_code = 200;
    nlohmann::json payload = nlohmann::json::object();
};

class ScopedEndpointMetricRecorder {
public:
    ScopedEndpointMetricRecorder(
        AiProdHttpServer* owner_value,
        std::string endpoint_value,
        httplib::Response* response_value)
        : owner(owner_value),
          endpoint(std::move(endpoint_value)),
          response(response_value),
          started_at(std::chrono::steady_clock::now()) {
    }

    ~ScopedEndpointMetricRecorder() {
        if (owner != nullptr && response != nullptr) {
            owner->RecordEndpointMetric(endpoint, response->status, started_at);
        }
    }

private:
    AiProdHttpServer* owner = nullptr;
    std::string endpoint;
    httplib::Response* response = nullptr;
    std::chrono::steady_clock::time_point started_at;
};

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

InferExecutionOutcome BuildErrorOutcome(int status, const std::string& message) {
    return {
        status,
        {
            {"status", "error"},
            {"message", message},
        },
    };
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

double PercentileFromSamples(const std::multiset<int>& samples, double ratio) {
    if (samples.empty()) {
        return 0.0;
    }
    const double scaled_index = std::ceil(static_cast<double>(samples.size()) * ratio) - 1.0;
    const double clamped_index = std::clamp(
        scaled_index,
        0.0,
        static_cast<double>(samples.size() - 1));
    const auto index = static_cast<std::size_t>(clamped_index);
    auto it = samples.begin();
    std::advance(it, static_cast<std::ptrdiff_t>(index));
    return static_cast<double>(*it);
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
        request->prefer_deadline_ms = payload.value("prefer_deadline_ms", -1);
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
        if (request->prefer_deadline_ms < -1) {
            *error_message = "prefer_deadline_ms 不能小于 -1。";
            return false;
        }
        if (request->options.contains("simulate_delay_ms") && request->options["simulate_delay_ms"].is_number_integer()) {
            request->simulate_delay_ms = std::clamp(request->options["simulate_delay_ms"].get<int>(), 0, kMaxSimulateDelayMs);
        }
        return PayloadCodec::Decode(request->input_type, request->payload, &request->decoded_payload, error_message);
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

std::string ResolveRequestId(const httplib::Request& request) {
    const auto request_id = request.get_header_value("X-Request-ID");
    if (!request_id.empty()) {
        return request_id;
    }
    return GenerateRequestId();
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

bool CanFallbackToCpu(const CapabilityCatalogEntry& entry, const std::string& requested_device, PluginFailureKind failure_kind) {
    if (requested_device != "gpu") {
        return false;
    }
    if (entry.device_mode == "cpu") {
        return false;
    }
    return failure_kind == PluginFailureKind::kBindingLoadFailure || failure_kind == PluginFailureKind::kLifecycleFailure;
}

nlohmann::json BuildSnapshotCapabilityPayload(
    const RuntimeCapabilityRecord& capability_record,
    int revision_id,
    const ProxyConfig& config) {
    const int pool_size = capability_record.instance_count > 0 ? capability_record.instance_count : config.pool_size;
    const int batch_wait_timeout_ms =
        capability_record.batch_wait_timeout_ms >= 0 ? capability_record.batch_wait_timeout_ms : config.infer_batch_wait_timeout_ms;
    const int queue_wait_timeout_ms =
        capability_record.queue_wait_timeout_ms >= 0 ? capability_record.queue_wait_timeout_ms : config.infer_queue_wait_timeout_ms;
    const int max_pending_request_count =
        capability_record.max_pending_request_count >= 0
            ? capability_record.max_pending_request_count
            : config.infer_queue_max_pending_requests;
    return {
        {"capability_name", capability_record.capability_name},
        {"plugin_target", capability_record.plugin_target},
        {"model_version", capability_record.model_version},
        {"backend_type", capability_record.backend_type},
        {"active_source", capability_record.active_source},
        {"model_root", capability_record.model_root},
        {"binary_path", capability_record.binary_path},
        {"device_mode", config.gpu_available ? "gpu/cpu" : "cpu"},
        {"pool_size", pool_size},
        {"max_batch_size", capability_record.max_batch_size},
        {"batch_wait_timeout_ms", batch_wait_timeout_ms},
        {"queue_wait_timeout_ms", queue_wait_timeout_ms},
        {"max_pending_request_count", max_pending_request_count},
        {"revision_id", revision_id},
    };
}

nlohmann::json BuildCapabilityRecordArray(const std::map<std::string, RuntimeCapabilityRecord>& capabilities) {
    nlohmann::json payload = nlohmann::json::array();
    for (const auto& capability_entry : capabilities) {
        payload.push_back(SerializeRuntimeCapabilityRecord(capability_entry.second));
    }
    return payload;
}

bool ValidateCapabilityRecords(
    const std::map<std::string, RuntimeCapabilityRecord>& capabilities,
    std::string* error_message) {
    for (const auto& capability_entry : capabilities) {
        const auto& record = capability_entry.second;
        if (record.model_root.empty() || !std::filesystem::exists(record.model_root)) {
            if (error_message != nullptr) {
                *error_message = "回滚目标模型目录不存在：" + record.model_root;
            }
            return false;
        }
        if (record.plugin_root.empty() || !std::filesystem::exists(record.plugin_root)) {
            if (error_message != nullptr) {
                *error_message = "回滚目标插件目录不存在：" + record.plugin_root;
            }
            return false;
        }
        if (record.binary_path.empty() || !std::filesystem::exists(record.binary_path)) {
            if (error_message != nullptr) {
                *error_message = "回滚目标插件文件不存在：" + record.binary_path;
            }
            return false;
        }
    }
    return true;
}

std::optional<std::map<std::string, RuntimeCapabilityRecord>> LoadCapabilityRecordsFromRevision(
    const RuntimeRevisionRecord& revision,
    std::string* error_message) {
    if (!revision.detail.is_object() || !revision.detail.contains("capability_records")) {
        return std::nullopt;
    }
    const auto& capability_records = revision.detail["capability_records"];
    if (!capability_records.is_array()) {
        if (error_message != nullptr) {
            *error_message = "revision capability_records 必须是数组。";
        }
        return std::nullopt;
    }

    std::map<std::string, RuntimeCapabilityRecord> restored;
    for (const auto& item : capability_records) {
        const auto record = DeserializeRuntimeCapabilityRecord(item, error_message);
        if (!record.has_value()) {
            return std::nullopt;
        }
        restored.emplace(record->capability_name, *record);
    }
    return restored;
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

struct AiProdHttpServer::PendingBatchExecution {
    std::string request_id;
    std::string capability_name;
    InferRequestPayload infer_request;
    std::chrono::steady_clock::time_point request_started_at = std::chrono::steady_clock::now();
    BatchDispatchAssignment batch_assignment;
    bool completed = false;
    InferExecutionOutcome outcome;
    std::condition_variable condition;
    std::mutex mutex;
};

AiProdHttpServer::AiProdHttpServer(const ProxyConfig& config_value)
    : config(config_value),
      capabilityCatalog(config_value.runtime_snapshot_path),
      licenseManager(
          config_value.license_root,
          config_value.hardware_features,
          config_value.license_auto_reload_interval_seconds),
      requestTracker(std::make_shared<InFlightRequestTracker>()),
      snapshotManager(config_value),
      auditLogger(std::make_unique<AuditLogger>(config_value.audit_log_path)),
      startedAt(std::chrono::steady_clock::now()),
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

void AiProdHttpServer::RecordEndpointMetric(
    const std::string& endpoint,
    int status_code,
    std::chrono::steady_clock::time_point started_at) {
    const auto latency_ms = static_cast<int>(
        std::chrono::duration_cast<std::chrono::milliseconds>(std::chrono::steady_clock::now() - started_at).count());
    std::lock_guard<std::mutex> guard(metricsMutex);
    auto& metrics = endpointMetrics[endpoint];
    metrics.total_requests += 1;
    if (status_code >= 200 && status_code < 400) {
        metrics.successful_requests += 1;
    } else {
        metrics.failed_requests += 1;
        metrics.last_error_at_utc = CurrentUtcIsoString();
    }
    metrics.last_status_code = status_code;
    metrics.total_latency_ms += static_cast<double>(latency_ms);
    if (metrics.total_requests == 1) {
        metrics.min_latency_ms = static_cast<double>(latency_ms);
        metrics.max_latency_ms = static_cast<double>(latency_ms);
    } else {
        metrics.min_latency_ms = std::min(metrics.min_latency_ms, static_cast<double>(latency_ms));
        metrics.max_latency_ms = std::max(metrics.max_latency_ms, static_cast<double>(latency_ms));
    }
    metrics.status_code_counts[status_code] += 1;
    metrics.recent_latency_ms.push_back(latency_ms);
    metrics.recent_latency_sorted.insert(latency_ms);
    while (metrics.recent_latency_ms.size() > kRecentLatencySampleLimit) {
        const int evicted_latency = metrics.recent_latency_ms.front();
        metrics.recent_latency_ms.pop_front();
        const auto sorted_it = metrics.recent_latency_sorted.find(evicted_latency);
        metrics.recent_latency_sorted.erase(sorted_it);
    }
}

void AiProdHttpServer::RecordSlaMetric(const std::string& endpoint, bool tracked, bool deadline_exceeded) {
    if (!tracked) {
        return;
    }
    std::lock_guard<std::mutex> guard(metricsMutex);
    auto& metrics = endpointMetrics[endpoint];
    metrics.sla_tracked_requests += 1;
    if (deadline_exceeded) {
        metrics.deadline_exceeded_requests += 1;
    }
}

int AiProdHttpServer::ResolveBatchWaitTimeoutMs(const CapabilityCatalogEntry& entry) const {
    return entry.batch_wait_timeout_ms >= 0 ? entry.batch_wait_timeout_ms : config.infer_batch_wait_timeout_ms;
}

void AiProdHttpServer::CompletePendingBatchExecution(
    const std::shared_ptr<PendingBatchExecution>& pending_execution,
    const nlohmann::json& payload,
    int status_code) {
    if (!pending_execution) {
        return;
    }
    {
        std::lock_guard<std::mutex> guard(pending_execution->mutex);
        pending_execution->outcome.status_code = status_code;
        pending_execution->outcome.payload = payload;
        pending_execution->completed = true;
    }
    pending_execution->condition.notify_all();
}

nlohmann::json AiProdHttpServer::BuildBatchCapabilityMetrics(
    const CapabilityCatalogEntry& entry,
    int batch_wait_timeout_ms) const {
    const auto batch_metrics = requestBatcher.GetCapabilityMetrics(entry.capability_name);
    if (!batch_metrics.has_value()) {
        return {
            {"enabled", entry.max_batch_size > 1 && batch_wait_timeout_ms > 0},
            {"max_batch_size", entry.max_batch_size},
            {"batch_wait_timeout_ms", batch_wait_timeout_ms},
            {"pending_batch_request_count", 0},
            {"formed_batch_count", 0},
            {"timeout_flush_count", 0},
            {"full_flush_count", 0},
            {"total_batched_request_count", 0},
            {"avg_batch_size", 0.0},
            {"max_batch_size_observed", 0},
            {"last_batch_size", 0},
            {"last_batch_wait_ms", 0},
            {"max_batch_wait_ms", 0},
            {"last_batch_id", nullptr},
        };
    }

    nlohmann::json payload = *batch_metrics;
    payload["enabled"] = entry.max_batch_size > 1 && batch_wait_timeout_ms > 0;
    payload["max_batch_size"] = entry.max_batch_size;
    payload["batch_wait_timeout_ms"] = batch_wait_timeout_ms;
    return payload;
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
    const std::string bootstrap_request_id = GenerateRequestId();
    if (!BootstrapRuntime(bootstrap_request_id, &bootstrap_error)) {
        MarkRuntimeError(bootstrap_error);
        AppendJsonLine(
            config.runtime_log_path,
            {
                {"event", "bootstrap_failed"},
                {"request_id", bootstrap_request_id},
                {"message", bootstrap_error},
            });
        auditLogger->Append(
            {
                "bootstrap_failed",
                "runtime_revision",
                "bootstrap",
                "failure",
                bootstrap_request_id,
                bootstrap_request_id,
                -1.0,
                bootstrap_error,
                {
                    {"reason", bootstrap_error},
                },
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
        int pending_count = 0;
        int max_pending_count = 0;
        int queue_timeout_count = 0;
        int deadline_exceeded_count = 0;
        double avg_queue_wait_ms = 0.0;
        int max_queue_wait_ms = 0;
        const int batch_wait_timeout_ms = ResolveBatchWaitTimeoutMs(entry);
        const int queue_wait_timeout_ms =
            entry.queue_wait_timeout_ms >= 0 ? entry.queue_wait_timeout_ms : config.infer_queue_wait_timeout_ms;
        const int configured_max_pending_request_count =
            entry.max_pending_request_count >= 0
                ? entry.max_pending_request_count
                : config.infer_queue_max_pending_requests;
        const auto execution_metrics = pluginExecutor.GetCapabilityMetrics(entry.capability_name);
        const auto pool_it = instancePools.find(entry.capability_name);
        if (pool_it != instancePools.end() && pool_it->second) {
            busy_count = pool_it->second->GetBusyCount();
            total_size = pool_it->second->GetTotalSize();
            pending_count = pool_it->second->GetPendingCount();
            max_pending_count = pool_it->second->GetMaxPendingCount();
            queue_timeout_count = pool_it->second->GetQueueTimeoutCount();
            deadline_exceeded_count = pool_it->second->GetDeadlineExceededCount();
            avg_queue_wait_ms = pool_it->second->GetAverageQueueWaitMs();
            max_queue_wait_ms = pool_it->second->GetMaxQueueWaitMs();
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
                {"max_batch_size", entry.max_batch_size},
                {"batch_wait_timeout_ms", batch_wait_timeout_ms},
                {"queue_wait_timeout_ms", queue_wait_timeout_ms},
                {"configured_max_pending_request_count", configured_max_pending_request_count},
                {"busy_count", busy_count},
                {"pending_request_count", pending_count},
                {"max_pending_request_count", max_pending_count},
                {"busy_reject_count", pool_it != instancePools.end() && pool_it->second ? pool_it->second->GetBusyRejectCount() : 0},
                {"queue_timeout_count", queue_timeout_count},
                {"deadline_exceeded_count", deadline_exceeded_count},
                {"avg_queue_wait_ms", avg_queue_wait_ms},
                {"max_queue_wait_ms", max_queue_wait_ms},
                {"draining", pool_it != instancePools.end() && pool_it->second ? pool_it->second->IsDraining() : false},
                {"batch_metrics", BuildBatchCapabilityMetrics(entry, batch_wait_timeout_ms)},
                {"execution_metrics", execution_metrics.has_value() ? *execution_metrics : nlohmann::json(nullptr)},
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

    nlohmann::json active_requests = nlohmann::json::array();
    for (const auto& active_request : requestTracker->Snapshot()) {
        const auto now = std::chrono::steady_clock::now();
        active_requests.push_back(
            {
                {"request_id", active_request.request_id},
                {"capability_name", active_request.capability_name},
                {"instance_id", active_request.instance_id},
                {"slot_index", active_request.slot_index},
                {"device", active_request.device},
                {"status", active_request.status},
                {"sla_status", active_request.sla_status},
                {"requested_deadline_ms", active_request.requested_deadline_ms},
                {"elapsed_ms", active_request.ElapsedMs(now)},
            });
    }

    return {
        {"service", "ai-prod-cpp-http"},
        {"snapshot_ready", snapshot_ready},
        {"runtime_state", runtimeStateMachine.GetStateName()},
        {"runtime_state_error", runtimeStateMachine.GetLastError().empty()
                                    ? nlohmann::json(nullptr)
                                    : nlohmann::json(runtimeStateMachine.GetLastError())},
        {"draining", draining},
        {"active_request_count", requestTracker->GetActiveCount()},
        {"active_requests", active_requests},
        {"runtime_revision_id", capabilityCatalog.GetRevisionId()},
        {"items", items},
    };
}

nlohmann::json AiProdHttpServer::BuildMetricsPayload(bool snapshot_ready) const {
    std::lock_guard<std::mutex> runtime_guard(runtimeStateMutex);
    std::lock_guard<std::mutex> metrics_guard(metricsMutex);

    nlohmann::json endpoint_metrics = nlohmann::json::object();
    for (const auto& entry : endpointMetrics) {
        const auto& metrics = entry.second;
        nlohmann::json status_counts = nlohmann::json::object();
        for (const auto& status_entry : metrics.status_code_counts) {
            status_counts[std::to_string(status_entry.first)] = status_entry.second;
        }
        endpoint_metrics[entry.first] = {
            {"total_requests", metrics.total_requests},
            {"successful_requests", metrics.successful_requests},
            {"failed_requests", metrics.failed_requests},
            {"avg_latency_ms", metrics.total_requests > 0
                                   ? metrics.total_latency_ms / static_cast<double>(metrics.total_requests)
                                   : 0.0},
            {"min_latency_ms", metrics.total_requests > 0 ? metrics.min_latency_ms : 0.0},
            {"p50_latency_ms", PercentileFromSamples(metrics.recent_latency_sorted, 0.50)},
            {"p95_latency_ms", PercentileFromSamples(metrics.recent_latency_sorted, 0.95)},
            {"p99_latency_ms", PercentileFromSamples(metrics.recent_latency_sorted, 0.99)},
            {"max_latency_ms", metrics.total_requests > 0 ? metrics.max_latency_ms : 0.0},
            {"recent_sample_count", metrics.recent_latency_ms.size()},
            {"sla_tracked_requests", metrics.sla_tracked_requests},
            {"deadline_exceeded_requests", metrics.deadline_exceeded_requests},
            {"deadline_exceeded_ratio", metrics.sla_tracked_requests > 0
                                           ? static_cast<double>(metrics.deadline_exceeded_requests) / static_cast<double>(metrics.sla_tracked_requests)
                                           : 0.0},
            {"last_status_code", metrics.last_status_code == 0 ? nlohmann::json(nullptr) : nlohmann::json(metrics.last_status_code)},
            {"last_error_at_utc", metrics.last_error_at_utc.empty()
                                      ? nlohmann::json(nullptr)
                                      : nlohmann::json(metrics.last_error_at_utc)},
            {"status_code_counts", status_counts},
        };
    }

    nlohmann::json pool_metrics = nlohmann::json::array();
    nlohmann::json capability_metrics = nlohmann::json::array();
    int total_pool_slots = 0;
    int total_busy_slots = 0;
    int total_pending_requests = 0;
    int total_busy_reject_count = 0;
    int total_queue_timeout_count = 0;
    int total_queued_requests = 0;
    int total_capability_requests = 0;
    int total_capability_failures = 0;
    int total_formed_batches = 0;
    int total_timeout_batches = 0;
    int total_full_batches = 0;
    int total_batched_requests = 0;
    int total_pending_batch_requests = 0;
    double total_queue_wait_ms = 0.0;
    int global_max_queue_wait_ms = 0;
    const auto infer_metrics_it = endpointMetrics.find("infer");
    const int total_deadline_exceeded_requests = infer_metrics_it != endpointMetrics.end()
        ? infer_metrics_it->second.deadline_exceeded_requests
        : 0;
    for (const auto& entry : capabilityCatalog.ListEntries()) {
        int busy_count = 0;
        int total_size = entry.pool_size;
        bool draining = false;
        int pending_count = 0;
        int queue_timeout_count = 0;
        int deadline_exceeded_count = 0;
        int queued_request_count = 0;
        double avg_queue_wait_ms = 0.0;
        int max_queue_wait_ms = 0;
        const int batch_wait_timeout_ms = ResolveBatchWaitTimeoutMs(entry);
        const int queue_wait_timeout_ms =
            entry.queue_wait_timeout_ms >= 0 ? entry.queue_wait_timeout_ms : config.infer_queue_wait_timeout_ms;
        const int configured_max_pending_request_count =
            entry.max_pending_request_count >= 0
                ? entry.max_pending_request_count
                : config.infer_queue_max_pending_requests;
        const auto pool_it = instancePools.find(entry.capability_name);
        if (pool_it != instancePools.end() && pool_it->second) {
            busy_count = pool_it->second->GetBusyCount();
            total_size = pool_it->second->GetTotalSize();
            draining = pool_it->second->IsDraining();
            pending_count = pool_it->second->GetPendingCount();
            total_busy_reject_count += pool_it->second->GetBusyRejectCount();
            queue_timeout_count = pool_it->second->GetQueueTimeoutCount();
            deadline_exceeded_count = pool_it->second->GetDeadlineExceededCount();
            queued_request_count = pool_it->second->GetQueuedRequestCount();
            avg_queue_wait_ms = pool_it->second->GetAverageQueueWaitMs();
            max_queue_wait_ms = pool_it->second->GetMaxQueueWaitMs();
            total_queue_wait_ms += static_cast<double>(pool_it->second->GetTotalQueueWaitMs());
        }
        total_pool_slots += total_size;
        total_busy_slots += busy_count;
        total_pending_requests += pending_count;
        total_queue_timeout_count += queue_timeout_count;
        total_queued_requests += queued_request_count;
        global_max_queue_wait_ms = std::max(global_max_queue_wait_ms, max_queue_wait_ms);
        const auto batch_metrics = BuildBatchCapabilityMetrics(entry, batch_wait_timeout_ms);
        total_formed_batches += batch_metrics.value("formed_batch_count", 0);
        total_timeout_batches += batch_metrics.value("timeout_flush_count", 0);
        total_full_batches += batch_metrics.value("full_flush_count", 0);
        total_batched_requests += batch_metrics.value("total_batched_request_count", 0);
        total_pending_batch_requests += batch_metrics.value("pending_batch_request_count", 0);
        pool_metrics.push_back(
            {
                {"capability_name", entry.capability_name},
                {"pool_size", total_size},
                {"busy_count", busy_count},
                {"pending_request_count", pending_count},
                {"idle_count", std::max(0, total_size - busy_count)},
                {"utilization_ratio", total_size > 0 ? static_cast<double>(busy_count) / static_cast<double>(total_size) : 0.0},
                {"busy_reject_count", pool_it != instancePools.end() && pool_it->second ? pool_it->second->GetBusyRejectCount() : 0},
                {"queue_timeout_count", queue_timeout_count},
                {"deadline_exceeded_count", deadline_exceeded_count},
                {"queued_request_count", queued_request_count},
                {"avg_queue_wait_ms", avg_queue_wait_ms},
                {"max_queue_wait_ms", max_queue_wait_ms},
                {"draining", draining},
                {"device_mode", entry.device_mode},
                {"max_batch_size", entry.max_batch_size},
                {"batch_wait_timeout_ms", batch_wait_timeout_ms},
                {"queue_wait_timeout_ms", queue_wait_timeout_ms},
                {"configured_max_pending_request_count", configured_max_pending_request_count},
                {"batch_metrics", batch_metrics},
            });

        const auto execution_metrics = pluginExecutor.GetCapabilityMetrics(entry.capability_name);
        if (execution_metrics.has_value()) {
            total_capability_requests += execution_metrics->value("total_requests", 0);
            total_capability_failures += execution_metrics->value("failed_requests", 0);
        }
        capability_metrics.push_back(
            {
                {"capability_name", entry.capability_name},
                {"execution_metrics", execution_metrics.has_value() ? *execution_metrics : nlohmann::json(nullptr)},
            });
    }

    const auto uptime_seconds = std::chrono::duration_cast<std::chrono::seconds>(
        std::chrono::steady_clock::now() - startedAt);
    return {
        {"service", "ai-prod-cpp-http"},
        {"snapshot_ready", snapshot_ready},
        {"runtime_state", runtimeStateMachine.GetStateName()},
        {"runtime_state_error", runtimeStateMachine.GetLastError().empty()
                                    ? nlohmann::json(nullptr)
                                    : nlohmann::json(runtimeStateMachine.GetLastError())},
        {"uptime_seconds", uptime_seconds.count()},
        {"runtime_revision_id", capabilityCatalog.GetRevisionId()},
        {"active_request_count", requestTracker->GetActiveCount()},
        {"pool_summary", {
             {"capability_count", capabilityCatalog.ListEntries().size()},
             {"total_pool_slots", total_pool_slots},
             {"busy_pool_slots", total_busy_slots},
             {"pending_request_count", total_pending_requests},
             {"idle_pool_slots", std::max(0, total_pool_slots - total_busy_slots)},
             {"utilization_ratio", total_pool_slots > 0 ? static_cast<double>(total_busy_slots) / static_cast<double>(total_pool_slots) : 0.0},
         }},
        {"request_summary", {
             {"capability_total_requests", total_capability_requests},
             {"capability_failed_requests", total_capability_failures},
             {"formed_batch_count", total_formed_batches},
             {"timeout_flush_count", total_timeout_batches},
             {"full_flush_count", total_full_batches},
             {"batched_request_count", total_batched_requests},
             {"pending_batch_request_count", total_pending_batch_requests},
             {"queued_request_count", total_queued_requests},
             {"avg_queue_wait_ms", total_queued_requests > 0 ? total_queue_wait_ms / static_cast<double>(total_queued_requests) : 0.0},
             {"max_queue_wait_ms", global_max_queue_wait_ms},
             {"busy_reject_count", total_busy_reject_count},
             {"queue_timeout_count", total_queue_timeout_count},
             {"deadline_exceeded_request_count", total_deadline_exceeded_requests},
          }},
        {"endpoint_metrics", endpoint_metrics},
        {"pool_metrics", pool_metrics},
        {"capability_metrics", capability_metrics},
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
    ScopedEndpointMetricRecorder recorder(this, "infer", &response);
    const auto request_started_at = std::chrono::steady_clock::now();
    const std::string request_id = ResolveRequestId(request);
    const std::string capability_name =
        request.matches.size() > 1 ? request.matches[1].str() : std::string();
    if (!RefreshCatalogAndPools()) {
        ApplyJsonErrorResponse(503, "运行时目录不可用，请先完成启动自举或 reload。", response);
        return;
    }

    const auto catalog_entry = capabilityCatalog.GetEntry(capability_name);
    if (!catalog_entry.has_value()) {
        ApplyJsonErrorResponse(404, "能力不存在或未装载。", response);
        return;
    }

    if (!licenseManager.QuickCheck(capability_name, catalog_entry->model_version)) {
        auditLogger->Append(
            {
                "infer_license_rejected",
                "capability",
                capability_name,
                "failure",
                request_id,
                request_id,
                -1.0,
                "当前 license 未授权该能力或版本。",
                {
                    {"reason", "当前 license 未授权该能力或版本。"},
                    {"model_version", catalog_entry->model_version},
                },
            });
        ApplyJsonErrorResponse(403, "当前 license 未授权该能力或版本。", response);
        return;
    }

    InferRequestPayload infer_request;
    std::string parse_error;
    if (!ParseInferRequest(request.body, &infer_request, &parse_error)) {
        auditLogger->Append(
            {
                "infer_parse_rejected",
                "capability",
                capability_name,
                "failure",
                request_id,
                request_id,
                -1.0,
                parse_error,
                {{"reason", parse_error}},
            });
        ApplyJsonErrorResponse(400, parse_error, response);
        return;
    }
    if (infer_request.prefer_deadline_ms > config.infer_request_max_deadline_ms) {
        auditLogger->Append(
            {
                "infer_deadline_rejected",
                "capability",
                capability_name,
                "failure",
                request_id,
                request_id,
                -1.0,
                "prefer_deadline_ms 超出运行时允许上限。",
                {{"deadline_ms", infer_request.prefer_deadline_ms}},
            });
        ApplyJsonErrorResponse(400, "prefer_deadline_ms 超出运行时允许上限。", response);
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

    const int queue_wait_timeout_ms =
        catalog_entry->queue_wait_timeout_ms >= 0 ? catalog_entry->queue_wait_timeout_ms : config.infer_queue_wait_timeout_ms;
    const int max_pending_request_count =
        catalog_entry->max_pending_request_count >= 0
            ? catalog_entry->max_pending_request_count
            : config.infer_queue_max_pending_requests;
    const int batch_wait_timeout_ms = ResolveBatchWaitTimeoutMs(*catalog_entry);

    auto apply_outcome = [&](const InferExecutionOutcome& outcome) {
        response.status = outcome.status_code;
        response.set_content(outcome.payload.dump(), kDefaultJsonContentType);
    };

    auto build_batch_detail = [](const BatchDispatchAssignment& assignment) {
        return nlohmann::json{
            {"batch_id", assignment.batch_id.empty() ? nlohmann::json(nullptr) : nlohmann::json(assignment.batch_id)},
            {"batch_size", static_cast<int>(assignment.batch_size)},
            {"batch_index", static_cast<int>(assignment.batch_index)},
            {"batch_wait_ms", assignment.batch_wait_ms},
            {"batch_flush_reason", assignment.timeout_triggered ? "timeout" : "full"},
        };
    };

    auto execute_prepared_request =
        [&](const std::shared_ptr<PendingBatchExecution>& pending_execution,
            const InstancePoolItem& leased_item,
            bool release_pool_slot,
            int pool_queue_wait_ms) -> InferExecutionOutcome {
        const auto& assignment = pending_execution->batch_assignment;
        const auto& pending_request = pending_execution->infer_request;
        const bool has_request_deadline = pending_request.prefer_deadline_ms >= 0;
        RequestLease request_lease(
            pool,
            leased_item,
            requestTracker,
            capability_name,
            pending_execution->request_id,
            pending_request.prefer_deadline_ms,
            release_pool_slot);
        request_lease.MarkSlaStatus(has_request_deadline ? "pending" : "not_requested");

        const std::string requested_device = ResolveDevice(pending_request, *catalog_entry);
        std::string executed_device = requested_device;
        request_lease.MarkExecuting(executed_device);
        if (pending_request.simulate_delay_ms > 0) {
            std::this_thread::sleep_for(std::chrono::milliseconds(pending_request.simulate_delay_ms));
        }

        if (has_request_deadline) {
            const auto pre_execute_elapsed_ms = static_cast<int>(
                std::chrono::duration_cast<std::chrono::milliseconds>(
                    std::chrono::steady_clock::now() - pending_execution->request_started_at)
                    .count());
            if (pre_execute_elapsed_ms > pending_request.prefer_deadline_ms) {
                request_lease.MarkSlaStatus("deadline_exceeded");
                request_lease.MarkFailed("请求 SLA 截止时间已超出，未进入执行。");
                pool->RecordDeadlineExceeded();
                RecordSlaMetric("infer", true, true);
                auto detail = build_batch_detail(assignment);
                detail["deadline_ms"] = pending_request.prefer_deadline_ms;
                detail["queue_wait_ms"] = pool_queue_wait_ms;
                auditLogger->Append(
                    {
                        "infer_deadline_exceeded",
                        "capability",
                        capability_name,
                        "failure",
                        pending_execution->request_id,
                        pending_execution->request_id,
                        static_cast<double>(pre_execute_elapsed_ms),
                        "请求 SLA 截止时间已超出，未进入执行。",
                        detail,
                    });
                return BuildErrorOutcome(503, "请求 SLA 截止时间已超出，未进入执行。");
            }
        }

        PluginExecutionResult plugin_result;
        std::string plugin_error;
        PluginFailureKind plugin_failure_kind = PluginFailureKind::kNone;
        bool plugin_ok = pluginExecutor.Execute(
            *catalog_entry,
            leased_item.slot_index,
            pending_request.input_type,
            pending_request.decoded_payload.normalized_payload,
            pending_request.options,
            executed_device,
            pending_execution->request_id,
            &plugin_result,
            &plugin_error,
            &plugin_failure_kind);
        std::string fallback_reason;
        if (!plugin_ok && CanFallbackToCpu(*catalog_entry, requested_device, plugin_failure_kind)) {
            fallback_reason = plugin_error.empty() ? "GPU 插件装载失败，已自动回退 CPU。" : plugin_error;
            executed_device = "cpu";
            request_lease.MarkExecuting(executed_device);
            plugin_error.clear();
            plugin_failure_kind = PluginFailureKind::kNone;
            plugin_ok = pluginExecutor.Execute(
                *catalog_entry,
                leased_item.slot_index,
                pending_request.input_type,
                pending_request.decoded_payload.normalized_payload,
                pending_request.options,
                executed_device,
                pending_execution->request_id,
                &plugin_result,
                &plugin_error,
                &plugin_failure_kind);
            if (plugin_ok) {
                pluginExecutor.RecordFallback(capability_name, executed_device, fallback_reason);
            }
        }
        if (!plugin_ok) {
            request_lease.MarkFailed(plugin_error.empty() ? "能力插件执行失败。" : plugin_error);
            auto detail = build_batch_detail(assignment);
            detail["requested_device"] = requested_device;
            detail["executed_device"] = executed_device;
            detail["fallback_applied"] = requested_device != executed_device;
            auditLogger->Append(
                {
                    "infer_failed",
                    "capability",
                    capability_name,
                    "failure",
                    pending_execution->request_id,
                    pending_execution->request_id,
                    -1.0,
                    plugin_error.empty() ? "能力插件执行失败。" : plugin_error,
                    detail,
                });
            return BuildErrorOutcome(503, plugin_error.empty() ? "能力插件执行失败。" : plugin_error);
        }

        request_lease.MarkCompleted();
        const double lifecycle_elapsed_ms = std::max(
            static_cast<double>(
                std::chrono::duration_cast<std::chrono::milliseconds>(
                    std::chrono::steady_clock::now() - pending_execution->request_started_at)
                    .count()),
            plugin_result.infer_time_ms);
        const std::string sla_status =
            has_request_deadline && lifecycle_elapsed_ms > static_cast<double>(pending_request.prefer_deadline_ms)
                ? "deadline_exceeded"
                : (has_request_deadline ? "ok" : "not_requested");
        request_lease.MarkSlaStatus(sla_status);
        RecordSlaMetric("infer", has_request_deadline, sla_status == "deadline_exceeded");
        pluginExecutor.RecordLifecycleSample(capability_name, executed_device, lifecycle_elapsed_ms);

        const std::string digest = Sha256Hex(
            capability_name + "|" + catalog_entry->model_version + "|" + pending_request.input_type + "|" +
            pending_request.decoded_payload.normalized_payload + "|" + plugin_result.plugin_result.dump());
        const nlohmann::json batch_result = {
            {"batch_id", assignment.batch_id.empty() ? nlohmann::json(nullptr) : nlohmann::json(assignment.batch_id)},
            {"batch_size", static_cast<int>(assignment.batch_size)},
            {"batch_index", static_cast<int>(assignment.batch_index)},
            {"batch_wait_ms", assignment.batch_wait_ms},
            {"batch_flush_reason", assignment.timeout_triggered ? "timeout" : "full"},
        };

        const nlohmann::json payload = {
            {"request_id", pending_execution->request_id},
            {"capability_name", capability_name},
            {"model_version", catalog_entry->model_version},
            {"backend_type", catalog_entry->backend_type},
            {"plugin_target", catalog_entry->plugin_target},
            {"device", executed_device},
            {"requested_device", requested_device},
            {"runtime_revision_id", catalog_entry->revision_id},
            {"license_valid", true},
            {"result", {
                {"summary", capability_name + " 推理完成"},
                {"digest", digest},
                {"score", std::round((static_cast<double>(std::stoi(digest.substr(0, 4), nullptr, 16)) / 65535.0) * 10000.0) / 10000.0},
                {"input_type", pending_request.input_type},
                {"payload_size", pending_request.decoded_payload.normalized_payload.size()},
                {"input_metadata", pending_request.decoded_payload.metadata},
                {"instance_id", request_lease.Item().instance_id},
                {"fallback_applied", requested_device != executed_device},
                {"fallback_reason", fallback_reason.empty() ? nlohmann::json(nullptr) : nlohmann::json(fallback_reason)},
                {"queue_wait_ms", pool_queue_wait_ms},
                {"queue_wait_timeout_ms", queue_wait_timeout_ms},
                {"max_pending_request_count", max_pending_request_count},
                {"deadline_ms", pending_request.prefer_deadline_ms},
                {"sla_status", sla_status},
                {"infer_time_ms", plugin_result.infer_time_ms},
                {"lifecycle_elapsed_ms", lifecycle_elapsed_ms},
                {"batch", batch_result},
                {"plugin_result", plugin_result.plugin_result},
            }},
        };

        AppendJsonLine(
            config.runtime_log_path,
            {
                {"event", "infer"},
                {"request_id", pending_execution->request_id},
                {"capability_name", capability_name},
                {"requested_device", requested_device},
                {"executed_device", executed_device},
                {"fallback_applied", requested_device != executed_device},
                {"fallback_reason", fallback_reason.empty() ? nlohmann::json(nullptr) : nlohmann::json(fallback_reason)},
                {"queue_wait_ms", pool_queue_wait_ms},
                {"queue_wait_timeout_ms", queue_wait_timeout_ms},
                {"max_pending_request_count", max_pending_request_count},
                {"deadline_ms", pending_request.prefer_deadline_ms},
                {"sla_status", sla_status},
                {"lifecycle_elapsed_ms", lifecycle_elapsed_ms},
                {"runtime_revision_id", catalog_entry->revision_id},
                {"batch", batch_result},
            });

        auto detail = build_batch_detail(assignment);
        detail["requested_device"] = requested_device;
        detail["executed_device"] = executed_device;
        detail["fallback_applied"] = requested_device != executed_device;
        detail["fallback_reason"] = fallback_reason.empty() ? nlohmann::json(nullptr) : nlohmann::json(fallback_reason);
        detail["instance_id"] = request_lease.Item().instance_id;
        detail["input_type"] = pending_request.input_type;
        detail["input_metadata"] = pending_request.decoded_payload.metadata;
        detail["queue_wait_ms"] = pool_queue_wait_ms;
        detail["queue_wait_timeout_ms"] = queue_wait_timeout_ms;
        detail["max_pending_request_count"] = max_pending_request_count;
        detail["deadline_ms"] = pending_request.prefer_deadline_ms;
        detail["sla_status"] = sla_status;
        detail["lifecycle_elapsed_ms"] = lifecycle_elapsed_ms;
        auditLogger->Append(
            {
                "infer",
                "capability",
                capability_name,
                "success",
                pending_execution->request_id,
                pending_execution->request_id,
                lifecycle_elapsed_ms,
                "",
                detail,
            });
        return {200, payload};
    };

    auto build_pending_execution = [&](const std::string& current_request_id, const InferRequestPayload& current_request) {
        auto pending_execution = std::make_shared<PendingBatchExecution>();
        pending_execution->request_id = current_request_id;
        pending_execution->capability_name = capability_name;
        pending_execution->infer_request = current_request;
        pending_execution->request_started_at = request_started_at;
        pending_execution->batch_assignment.request_ids = {current_request_id};
        pending_execution->batch_assignment.batch_size = 1;
        return pending_execution;
    };

    const bool batching_enabled = catalog_entry->max_batch_size > 1 && batch_wait_timeout_ms > 0;
    if (batching_enabled) {
        auto pending_execution = build_pending_execution(request_id, infer_request);
        {
            std::lock_guard<std::mutex> guard(pendingBatchMutex);
            pendingBatchExecutions[request_id] = pending_execution;
        }
        pending_execution->batch_assignment = requestBatcher.Submit(
            capability_name,
            request_id,
            catalog_entry->max_batch_size,
            batch_wait_timeout_ms);

        if (!pending_execution->batch_assignment.leader) {
            std::unique_lock<std::mutex> guard(pending_execution->mutex);
            pending_execution->condition.wait(guard, [&]() { return pending_execution->completed; });
            apply_outcome(pending_execution->outcome);
            return;
        }

        std::vector<std::shared_ptr<PendingBatchExecution>> batch_executions;
        {
            std::lock_guard<std::mutex> guard(pendingBatchMutex);
            for (const auto& grouped_request_id : pending_execution->batch_assignment.request_ids) {
                const auto it = pendingBatchExecutions.find(grouped_request_id);
                if (it != pendingBatchExecutions.end()) {
                    batch_executions.push_back(it->second);
                }
            }
        }

        std::vector<std::shared_ptr<PendingBatchExecution>> executable_requests;
        executable_requests.reserve(batch_executions.size());
        for (const auto& batch_execution : batch_executions) {
            const bool tracked_deadline = batch_execution->infer_request.prefer_deadline_ms >= 0;
            const auto elapsed_ms = static_cast<int>(
                std::chrono::duration_cast<std::chrono::milliseconds>(
                    std::chrono::steady_clock::now() - batch_execution->request_started_at)
                    .count());
            if (tracked_deadline && elapsed_ms > batch_execution->infer_request.prefer_deadline_ms) {
                RecordSlaMetric("infer", true, true);
                auto detail = build_batch_detail(batch_execution->batch_assignment);
                detail["deadline_ms"] = batch_execution->infer_request.prefer_deadline_ms;
                detail["queue_wait_ms"] = 0;
                auditLogger->Append(
                    {
                        "infer_deadline_exceeded",
                        "capability",
                        capability_name,
                        "failure",
                        batch_execution->request_id,
                        batch_execution->request_id,
                        static_cast<double>(elapsed_ms),
                        "请求 SLA 截止时间已超出，未进入执行。",
                        detail,
                    });
                CompletePendingBatchExecution(
                    batch_execution,
                    BuildErrorOutcome(503, "请求 SLA 截止时间已超出，未进入执行。").payload,
                    503);
                continue;
            }
            executable_requests.push_back(batch_execution);
        }

        if (!executable_requests.empty()) {
            std::optional<std::chrono::milliseconds> earliest_deadline = std::nullopt;
            for (const auto& batch_execution : executable_requests) {
                if (batch_execution->infer_request.prefer_deadline_ms < 0) {
                    continue;
                }
                const auto elapsed_ms = static_cast<int>(
                    std::chrono::duration_cast<std::chrono::milliseconds>(
                        std::chrono::steady_clock::now() - batch_execution->request_started_at)
                        .count());
                const int remaining_deadline_ms = std::max(0, batch_execution->infer_request.prefer_deadline_ms - elapsed_ms);
                if (!earliest_deadline.has_value() || remaining_deadline_ms < earliest_deadline->count()) {
                    earliest_deadline = std::chrono::milliseconds(remaining_deadline_ms);
                }
            }

            const auto acquire_result = pool->AcquireWithWait(
                std::chrono::milliseconds(queue_wait_timeout_ms),
                max_pending_request_count,
                earliest_deadline);
            if (acquire_result.status == InstanceAcquireStatus::kAcquired && acquire_result.item.has_value()) {
                for (std::size_t index = 0; index < executable_requests.size(); ++index) {
                    const bool release_pool_slot = index + 1 == executable_requests.size();
                    const auto outcome = execute_prepared_request(
                        executable_requests[index],
                        *acquire_result.item,
                        release_pool_slot,
                        acquire_result.queue_wait_ms);
                    CompletePendingBatchExecution(executable_requests[index], outcome.payload, outcome.status_code);
                }
            } else {
                for (const auto& batch_execution : executable_requests) {
                    const bool tracked_deadline = batch_execution->infer_request.prefer_deadline_ms >= 0;
                    std::string error_message = "能力实例池繁忙或排队超时，请稍后重试。";
                    std::string action = "infer_queue_timeout";
                    if (acquire_result.status == InstanceAcquireStatus::kDraining || pool->IsDraining()) {
                        error_message = "能力正在切换，请稍后重试。";
                        action = "infer_pool_draining";
                    } else if (acquire_result.status == InstanceAcquireStatus::kQueueRejected) {
                        error_message = "能力排队已满，请稍后重试。";
                        action = "infer_queue_rejected";
                    } else if (acquire_result.status == InstanceAcquireStatus::kDeadlineExceeded) {
                        error_message = "请求 SLA 截止时间已超出，未进入执行。";
                        action = "infer_deadline_exceeded";
                        RecordSlaMetric("infer", tracked_deadline, true);
                    }
                    auto detail = build_batch_detail(batch_execution->batch_assignment);
                    detail["queue_wait_ms"] = acquire_result.queue_wait_ms;
                    detail["queue_wait_timeout_ms"] = queue_wait_timeout_ms;
                    detail["max_pending_request_count"] = max_pending_request_count;
                    detail["deadline_ms"] = batch_execution->infer_request.prefer_deadline_ms;
                    auditLogger->Append(
                        {
                            action,
                            "capability",
                            capability_name,
                            "failure",
                            batch_execution->request_id,
                            batch_execution->request_id,
                            static_cast<double>(acquire_result.queue_wait_ms),
                            error_message,
                            detail,
                        });
                    CompletePendingBatchExecution(batch_execution, BuildErrorOutcome(503, error_message).payload, 503);
                }
            }
        }

        {
            std::lock_guard<std::mutex> guard(pendingBatchMutex);
            for (const auto& grouped_request_id : pending_execution->batch_assignment.request_ids) {
                pendingBatchExecutions.erase(grouped_request_id);
            }
        }

        std::unique_lock<std::mutex> guard(pending_execution->mutex);
        pending_execution->condition.wait(guard, [&]() { return pending_execution->completed; });
        apply_outcome(pending_execution->outcome);
        return;
    }

    const bool has_request_deadline = infer_request.prefer_deadline_ms >= 0;
    const auto request_deadline = has_request_deadline
        ? std::optional<std::chrono::milliseconds>(std::chrono::milliseconds(infer_request.prefer_deadline_ms))
        : std::nullopt;
    const auto acquire_result = pool->AcquireWithWait(
        std::chrono::milliseconds(queue_wait_timeout_ms),
        max_pending_request_count,
        request_deadline);
    if (acquire_result.status != InstanceAcquireStatus::kAcquired || !acquire_result.item.has_value()) {
        if (acquire_result.status == InstanceAcquireStatus::kDraining || pool->IsDraining()) {
            auditLogger->Append(
                {
                    "infer_pool_draining",
                    "capability",
                    capability_name,
                    "failure",
                    request_id,
                    request_id,
                    -1.0,
                    "能力正在切换，请稍后重试。",
                    nlohmann::json::object(),
                });
            ApplyJsonErrorResponse(503, "能力正在切换，请稍后重试。", response);
            return;
        }
        if (acquire_result.status == InstanceAcquireStatus::kQueueRejected) {
            auditLogger->Append(
                {
                    "infer_queue_rejected",
                    "capability",
                    capability_name,
                    "failure",
                    request_id,
                    request_id,
                    -1.0,
                    "能力排队已满，请稍后重试。",
                    {{"max_pending_request_count", max_pending_request_count}},
                });
            ApplyJsonErrorResponse(503, "能力排队已满，请稍后重试。", response);
            return;
        }
        if (acquire_result.status == InstanceAcquireStatus::kDeadlineExceeded) {
            RecordSlaMetric("infer", true, true);
            auditLogger->Append(
                {
                    "infer_deadline_exceeded",
                    "capability",
                    capability_name,
                    "failure",
                    request_id,
                    request_id,
                    static_cast<double>(acquire_result.queue_wait_ms),
                    "请求 SLA 截止时间已超出，未进入执行。",
                    {
                        {"deadline_ms", infer_request.prefer_deadline_ms},
                        {"queue_wait_ms", acquire_result.queue_wait_ms},
                    },
                });
            ApplyJsonErrorResponse(503, "请求 SLA 截止时间已超出，未进入执行。", response);
            return;
        }
        auditLogger->Append(
            {
                "infer_queue_timeout",
                "capability",
                capability_name,
                "failure",
                request_id,
                request_id,
                static_cast<double>(acquire_result.queue_wait_ms),
                "能力实例池繁忙或排队超时，请稍后重试。",
                {
                    {"queue_wait_ms", acquire_result.queue_wait_ms},
                    {"queue_wait_timeout_ms", queue_wait_timeout_ms},
                },
            });
        ApplyJsonErrorResponse(503, "能力实例池繁忙或排队超时，请稍后重试。", response);
        return;
    }

    auto pending_execution = build_pending_execution(request_id, infer_request);
    const auto outcome = execute_prepared_request(pending_execution, *acquire_result.item, true, acquire_result.queue_wait_ms);
    apply_outcome(outcome);
}

std::optional<nlohmann::json> AiProdHttpServer::ExecuteRuntimeTransition(
    const std::string& action,
    std::optional<int> target_revision_id,
    const std::string& request_id,
    std::string* error_message) {
    const auto scan_result = RuntimeResourceScanner::ResolveSources(
        config.host_root,
        config.image_resource_root,
        RuntimeResourceScanner::DetectPlatformTarget());
    std::map<std::string, RuntimeCapabilityRecord> selected_capabilities = scan_result.capabilities;
    nlohmann::json source_summary = scan_result.source_summary;

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
        source_summary = source_revision->source_summary;
        const auto restored_capabilities = LoadCapabilityRecordsFromRevision(*source_revision, error_message);
        if (restored_capabilities.has_value()) {
            selected_capabilities = *restored_capabilities;
            if (!ValidateCapabilityRecords(selected_capabilities, error_message)) {
                return std::nullopt;
            }
        } else {
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
    }

    const auto current_license_status = licenseManager.GetStatus();
    if (!current_license_status.valid) {
        *error_message = "license 未授权或已失效，无法执行运行时切换。";
        return std::nullopt;
    }

    for (const auto& capability_entry : selected_capabilities) {
        if (!licenseManager.QuickCheck(capability_entry.first, capability_entry.second.model_version)) {
            auditLogger->Append(
                {
                    action + "_license_rejected",
                    "capability",
                    capability_entry.first,
                    "failure",
                    request_id,
                    request_id,
                    -1.0,
                    "当前 license 未授权该能力或版本。",
                    {
                        {"reason", "当前 license 未授权该能力或版本。"},
                        {"model_version", capability_entry.second.model_version},
                    },
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
        {"capability_records", BuildCapabilityRecordArray(selected_capabilities)},
    };
    if (rollback_of_revision_id.has_value()) {
        detail["rollback_to"] = *rollback_of_revision_id;
    }

    const auto revision = revision_store.CreateRevision(
        GenerateRequestId(),
        action,
        "active",
        source_summary,
        capability_names,
        true,
        detail,
        rollback_of_revision_id,
        error_message);
    if (!revision.has_value()) {
        return std::nullopt;
    }

    for (const auto& capability_entry : selected_capabilities) {
        snapshot_capabilities.push_back(BuildSnapshotCapabilityPayload(capability_entry.second, revision->id, config));
    }

    nlohmann::json snapshot_payload = {
        {"snapshot_version", 1},
        {"updated_at_utc", CurrentUtcIsoString()},
        {"revision_id", revision->id},
        {"revision_token", revision->revision_token},
        {"capability_names", capability_names},
        {"capability_count", static_cast<int>(selected_capabilities.size())},
        {"capabilities", snapshot_capabilities},
        {"source_summary", source_summary},
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
            {"request_id", request_id},
            {"revision_id", revision->id},
            {"active_capability_count", static_cast<int>(selected_capabilities.size())},
        });
    auditLogger->Append(
        {
            action,
            "runtime_revision",
            std::to_string(revision->id),
            "success",
            request_id,
            request_id,
            -1.0,
            "",
            {
                {"active_capability_count", static_cast<int>(selected_capabilities.size())},
            },
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
    ScopedEndpointMetricRecorder recorder(this, rollback ? "admin_rollback" : "admin_reload", &response);
    const std::string request_id = ResolveRequestId(request);
    std::unique_lock<std::mutex> transition_guard(runtimeTransitionMutex, std::try_to_lock);
    if (!transition_guard.owns_lock()) {
        auditLogger->Append(
            {
                rollback ? "rollback_rejected" : "reload_rejected",
                "runtime_revision",
                rollback ? "rollback" : "reload",
                "failure",
                request_id,
                request_id,
                -1.0,
                "已有运行时切换任务正在执行。",
                {{"reason", "已有运行时切换任务正在执行。"}},
            });
        ApplyJsonErrorResponse(409, "已有运行时切换任务正在执行。", response);
        return;
    }
    AdminTransitionRequestPayload transition_request;
    std::string parse_error;
    if (!ParseAdminTransitionRequest(request.body, rollback, &transition_request, &parse_error)) {
        auditLogger->Append(
            {
                rollback ? "rollback_parse_rejected" : "reload_parse_rejected",
                "runtime_revision",
                rollback ? "rollback" : "reload",
                "failure",
                request_id,
                request_id,
                -1.0,
                parse_error,
                {{"reason", parse_error}},
            });
        ApplyJsonErrorResponse(400, parse_error, response);
        return;
    }

    if (!licenseManager.GetStatus().valid) {
        auditLogger->Append(
            {
                transition_request.action + "_license_rejected",
                "runtime_revision",
                transition_request.action,
                "failure",
                request_id,
                request_id,
                -1.0,
                "license 未授权或已失效，无法执行运行时切换。",
                {{"reason", "license 未授权或已失效，无法执行运行时切换。"}},
            });
        ApplyJsonErrorResponse(403, "license 未授权或已失效，无法执行运行时切换。", response);
        return;
    }

    for (const auto& entry : capabilityCatalog.ListEntries()) {
        if (!licenseManager.QuickCheck(entry.capability_name, entry.model_version)) {
            auditLogger->Append(
                {
                    transition_request.action + "_license_rejected",
                    "capability",
                    entry.capability_name,
                    "failure",
                    request_id,
                    request_id,
                    -1.0,
                    "当前 license 未覆盖已装载能力，无法执行运行时切换。",
                    {{"model_version", entry.model_version}},
                });
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
    if (!requestTracker->WaitForEmpty(std::chrono::duration_cast<std::chrono::milliseconds>(kDrainTimeout))) {
        EndDrainOnPools(pools);
        runtimeStateMachine.TransitionTo(RuntimeLifecycleState::kReady, &state_error);
        ApplyJsonErrorResponse(503, "当前仍有推理请求执行中，暂时无法切换运行时。", response);
        return;
    }
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
        request_id,
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
    httplib::Response& response) {
    ScopedEndpointMetricRecorder recorder(this, "license_status", &response);
    response.status = 200;
    response.set_content(
        BuildLicenseStatusPayload(licenseManager.GetStatus()).dump(),
        kDefaultJsonContentType);
}

void AiProdHttpServer::HandleLicenseReloadRequest(
    const httplib::Request& request,
    httplib::Response& response) {
    ScopedEndpointMetricRecorder recorder(this, "admin_license_reload", &response);
    const std::string request_id = ResolveRequestId(request);
    if (licenseManager.Reload()) {
        AppendJsonLine(
            config.runtime_log_path,
            {
                {"event", "license_reload"},
                {"request_id", request_id},
                {"license_valid", licenseManager.GetStatus().valid},
            });
        auditLogger->Append(
            {
                "license_reload",
                "license",
                "active_license",
                "success",
                request_id,
                request_id,
                -1.0,
                "",
                {
                    {"license_valid", licenseManager.GetStatus().valid},
                },
            });
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
    AppendJsonLine(
        config.runtime_log_path,
        {
            {"event", "license_reload_failed"},
            {"request_id", request_id},
            {"reason", failure_status.reason},
        });
    auditLogger->Append(
        {
            "license_reload_failed",
            "license",
            "active_license",
            "failure",
            request_id,
            request_id,
            -1.0,
            failure_status.reason,
            {
                {"reason", failure_status.reason},
                {"license_valid", failure_status.valid},
            },
        });
    response.status = 400;
    response.set_content(
        nlohmann::json{
            {"status", "error"},
            {"message", failure_status.reason},
            {"license_status", BuildLicenseStatusPayload(failure_status)},
        }.dump(),
        kDefaultJsonContentType);
}

bool AiProdHttpServer::BootstrapRuntime(const std::string& request_id, std::string* error_message) {
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
            auditLogger->Append(
                {
                    "bootstrap_license_rejected",
                    "capability",
                    capability_entry.first,
                    "failure",
                    request_id,
                    request_id,
                    -1.0,
                    "当前 license 未授权该能力或版本。",
                    {
                        {"reason", "当前 license 未授权该能力或版本。"},
                        {"model_version", capability_entry.second.model_version},
                    },
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
            {"capability_records", BuildCapabilityRecordArray(selected_capabilities)},
        },
        std::nullopt,
        error_message);
    if (!revision.has_value()) {
        return false;
    }

    for (const auto& capability_entry : selected_capabilities) {
        snapshot_capabilities.push_back(BuildSnapshotCapabilityPayload(capability_entry.second, revision->id, config));
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
            {"request_id", request_id},
            {"revision_id", revision->id},
            {"capability_count", static_cast<int>(selected_capabilities.size())},
            {"license_valid", current_license_status.valid},
        });
    auditLogger->Append(
        {
            "bootstrap",
            "runtime_revision",
            std::to_string(revision->id),
            "success",
            request_id,
            request_id,
            -1.0,
            "",
            {
                {"capability_count", static_cast<int>(selected_capabilities.size())},
                {"license_valid", current_license_status.valid},
            },
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
                << "\"mode\":\"runtime\","
                << "\"internal_shell\":\"" << EscapeJson(build_backend_base_url(config)) << "\","
                << "\"bind\":\"" << EscapeJson(config.bind_host + ":" + std::to_string(config.bind_port)) << "\""
                << "}";
        response.set_content(payload.str(), kDefaultJsonContentType);
    });

    server->Get("/api/v1/health", [&](const httplib::Request&, httplib::Response& response) {
        ScopedEndpointMetricRecorder recorder(this, "health", &response);
        const auto snapshot_response = snapshotManager.BuildHealthResponse();
        if (!snapshot_response.ok) {
            ApplyJsonErrorResponse(503, "运行时快照不可用，请先完成启动自举或 reload。", response);
            return;
        }
        response.status = 200;
        response.set_content(snapshot_response.body, kDefaultJsonContentType);
    });
    server->Get("/api/v1/capabilities", [&](const httplib::Request&, httplib::Response& response) {
        ScopedEndpointMetricRecorder recorder(this, "capabilities", &response);
        const auto snapshot_response = snapshotManager.BuildCapabilitiesResponse();
        if (!snapshot_response.ok) {
            ApplyJsonErrorResponse(503, "运行时快照不可用，请先完成启动自举或 reload。", response);
            return;
        }
        response.status = 200;
        response.set_content(snapshot_response.body, kDefaultJsonContentType);
    });
    server->Get("/api/v1/license/status", [&](const httplib::Request& request, httplib::Response& response) {
        HandleLicenseStatusRequest(request, response);
    });
    server->Get("/api/v1/admin/catalog", [&](const httplib::Request&, httplib::Response& response) {
        ScopedEndpointMetricRecorder recorder(this, "admin_catalog", &response);
        const bool snapshot_ready = RefreshCatalogAndPools();
        response.status = 200;
        response.set_content(BuildCatalogPayload(snapshot_ready).dump(), kDefaultJsonContentType);
    });
    server->Get("/api/v1/admin/metrics", [&](const httplib::Request&, httplib::Response& response) {
        ScopedEndpointMetricRecorder recorder(this, "admin_metrics", &response);
        const bool snapshot_ready = RefreshCatalogAndPools();
        response.status = 200;
        response.set_content(BuildMetricsPayload(snapshot_ready).dump(), kDefaultJsonContentType);
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
