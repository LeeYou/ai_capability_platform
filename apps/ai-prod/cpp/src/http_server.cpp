#include "http_server.h"

#include <algorithm>
#include <cctype>
#include <sstream>
#include <string>

namespace {

constexpr char kDefaultJsonContentType[] = "application/json; charset=utf-8";

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

}

AiProdHttpServer::AiProdHttpServer(const ProxyConfig& config_value)
    : config(config_value),
      backendClient(config_value),
      snapshotManager(config_value),
      server(std::make_unique<httplib::Server>()) {
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
        const auto content_type = request.get_header_value("Content-Type");
        ApplyBackendResponse(
            backendClient.ForwardPost(request.path, request.body, content_type, BuildForwardHeaders(request)),
            response);
    });
}
