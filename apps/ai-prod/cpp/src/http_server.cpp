#include "http_server.h"

#include <algorithm>
#include <cctype>
#include <map>
#include <sstream>
#include <string>

namespace {

constexpr char kDefaultJsonContentType[] = "application/json; charset=utf-8";
constexpr char kInstanceIdHeader[] = "X-AI-Prod-Instance-Id";
constexpr char kPreferredDeviceHeader[] = "X-AI-Prod-Preferred-Device";
constexpr char kRuntimeRevisionIdHeader[] = "X-AI-Prod-Runtime-Revision-Id";

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

}

AiProdHttpServer::AiProdHttpServer(const ProxyConfig& config_value)
    : config(config_value),
      capabilityCatalog(config_value.runtime_snapshot_path),
      backendClient(config_value),
      snapshotManager(config_value),
      server(std::make_unique<httplib::Server>()) {
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

bool AiProdHttpServer::RefreshCatalogAndPools() {
    std::lock_guard<std::mutex> guard(runtimeStateMutex);
    const bool snapshot_ready = capabilityCatalog.RefreshIfNeeded(config.snapshot_max_age_seconds);
    if (!snapshot_ready) {
        return false;
    }

    const int revision_id = capabilityCatalog.GetRevisionId();
    if (revision_id == activeCatalogRevisionId && !instancePools.empty()) {
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
                {"revision_id", entry.revision_id},
            });
    }

    return {
        {"service", "ai-prod-cpp-http"},
        {"snapshot_ready", snapshot_ready},
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

void AiProdHttpServer::HandleInferRequest(
    const httplib::Request& request,
    httplib::Response& response) {
    const std::string capability_name =
        request.matches.size() > 1 ? request.matches[1].str() : std::string();
    const auto content_type = request.get_header_value("Content-Type");
    auto headers = BuildForwardHeaders(request);

    if (!RefreshCatalogAndPools()) {
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

    const auto pool = GetInstancePool(capability_name);
    if (!pool) {
        ApplyJsonErrorResponse(503, "能力实例池不可用。", response);
        return;
    }

    const auto lease = pool->Acquire();
    if (!lease.has_value()) {
        ApplyJsonErrorResponse(503, "能力实例池繁忙，请稍后重试。", response);
        return;
    }

    headers.emplace(kInstanceIdHeader, lease->instance_id);
    headers.emplace(kPreferredDeviceHeader, lease->preferred_device);
    headers.emplace(kRuntimeRevisionIdHeader, std::to_string(catalog_entry->revision_id));

    const auto backend_response = backendClient.ForwardPost(request.path, request.body, content_type, headers);
    pool->Release(lease->slot_index);
    ApplyBackendResponse(backend_response, response);
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
        ApplySnapshotOrBackendResponse(snapshotManager.BuildLicenseStatusResponse(), request, response);
    });
    server->Get("/api/v1/admin/catalog", [&](const httplib::Request&, httplib::Response& response) {
        const bool snapshot_ready = RefreshCatalogAndPools();
        response.status = 200;
        response.set_content(BuildCatalogPayload(snapshot_ready).dump(), kDefaultJsonContentType);
    });
    server->Get("/api/v1/admin/revisions", [&](const httplib::Request& request, httplib::Response& response) {
        ApplyBackendResponse(backendClient.ForwardGet(request.path, BuildForwardHeaders(request)), response);
    });
    server->Get("/api/v1/admin/operations", [&](const httplib::Request& request, httplib::Response& response) {
        ApplyBackendResponse(backendClient.ForwardGet(request.path, BuildForwardHeaders(request)), response);
    });
    server->Post("/api/v1/admin/reload", [&](const httplib::Request& request, httplib::Response& response) {
        const auto content_type = request.get_header_value("Content-Type");
        ApplyBackendResponse(
            backendClient.ForwardPost(request.path, request.body, content_type, BuildForwardHeaders(request)),
            response);
    });
    server->Post("/api/v1/admin/rollback", [&](const httplib::Request& request, httplib::Response& response) {
        const auto content_type = request.get_header_value("Content-Type");
        ApplyBackendResponse(
            backendClient.ForwardRollback(request.body, content_type, BuildForwardHeaders(request)),
            response);
    });
    server->Post(R"(/api/v1/infer/([^/]+))", [&](const httplib::Request& request, httplib::Response& response) {
        HandleInferRequest(request, response);
    });
}
