#include "backend_client.h"

#include <nlohmann/json.hpp>

#include <chrono>
#include <string>

namespace {

constexpr char kJsonContentType[] = "application/json; charset=utf-8";

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

AiProdBackendClient::AiProdBackendClient(const ProxyConfig& config_value)
    : config(config_value) {
}

BackendResponse AiProdBackendClient::ForwardGet(
    const std::string& path,
    const httplib::Headers& headers) const {
    auto client = BuildClient();
    const auto result = client.Get(path, headers);
    if (!result) {
        return BuildFailureResponse("python backend unavailable");
    }
    return BuildSuccessResponse(result);
}

BackendResponse AiProdBackendClient::ForwardPost(
    const std::string& path,
    const std::string& body,
    const std::string& content_type,
    const httplib::Headers& headers) const {
    auto client = BuildClient();
    const auto result = client.Post(path, headers, body, content_type.c_str());
    if (!result) {
        return BuildFailureResponse("python backend unavailable");
    }
    return BuildSuccessResponse(result);
}

BackendResponse AiProdBackendClient::ForwardRollback(
    const std::string& body,
    const std::string& content_type,
    const httplib::Headers& headers) const {
    return ForwardPost(
        "/api/v1/admin/reload",
        NormalizeRollbackBody(body),
        content_type.empty() ? "application/json" : content_type,
        headers);
}

std::string AiProdBackendClient::NormalizeRollbackBody(const std::string& body) {
    nlohmann::json payload = nlohmann::json::object();
    if (!body.empty()) {
        try {
            payload = nlohmann::json::parse(body);
        } catch (const std::exception&) {
            payload = nlohmann::json::object();
        }
    }

    if (!payload.is_object()) {
        payload = nlohmann::json::object();
    }
    payload["action"] = "rollback";
    return payload.dump();
}

httplib::Client AiProdBackendClient::BuildClient() const {
    httplib::Client client(config.backend_host, config.backend_port);
    client.set_connection_timeout(std::chrono::milliseconds(config.connect_timeout_ms));
    client.set_read_timeout(std::chrono::milliseconds(config.read_timeout_ms));
    client.set_write_timeout(std::chrono::milliseconds(config.write_timeout_ms));
    return client;
}

BackendResponse AiProdBackendClient::BuildFailureResponse(const std::string& message) {
    BackendResponse response;
    response.status = 502;
    response.content_type = kJsonContentType;
    response.body = "{\"status\":\"error\",\"message\":\"" + EscapeJson(message) + "\"}";
    response.ok = false;
    return response;
}

BackendResponse AiProdBackendClient::BuildSuccessResponse(const httplib::Result& result) {
    BackendResponse response;
    response.status = result->status;
    response.body = result->body;
    const auto content_type_it = result->headers.find("Content-Type");
    if (content_type_it != result->headers.end()) {
        response.content_type = content_type_it->second;
    }
    response.ok = true;
    return response;
}
