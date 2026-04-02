#include "proxy_config.h"

#include <cpp-httplib/httplib.h>

#include <algorithm>
#include <cctype>
#include <iostream>
#include <sstream>
#include <string>

namespace {

constexpr char kJsonContentType[] = "application/json; charset=utf-8";

std::string to_lower_copy(const std::string& value) {
    std::string lowered = value;
    std::transform(
        lowered.begin(),
        lowered.end(),
        lowered.begin(),
        [](unsigned char ch) { return static_cast<char>(std::tolower(ch)); });
    return lowered;
}

bool should_forward_header(const std::string& key) {
    const std::string lowered = to_lower_copy(key);
    return lowered != "host" &&
           lowered != "content-length" &&
           lowered != "transfer-encoding" &&
           lowered != "connection";
}

httplib::Headers build_forward_headers(const httplib::Request& request) {
    httplib::Headers headers;
    for (const auto& header : request.headers) {
        if (should_forward_header(header.first)) {
            headers.emplace(header.first, header.second);
        }
    }
    return headers;
}

std::string escape_json(const std::string& value) {
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

void set_json_error(httplib::Response& response, int status, const std::string& message) {
    response.status = status;
    response.set_content(
        "{\"status\":\"error\",\"message\":\"" + escape_json(message) + "\"}",
        kJsonContentType);
}

httplib::Client build_backend_client(const ProxyConfig& config) {
    httplib::Client client(config.backend_host, config.backend_port);
    client.set_connection_timeout(
        std::chrono::milliseconds(config.connect_timeout_ms));
    client.set_read_timeout(
        std::chrono::milliseconds(config.read_timeout_ms));
    client.set_write_timeout(
        std::chrono::milliseconds(config.write_timeout_ms));
    return client;
}

void copy_result_to_response(const httplib::Result& result, httplib::Response& response) {
    if (!result) {
        set_json_error(response, 502, "python backend unavailable");
        return;
    }

    response.status = result->status;
    std::string content_type = kJsonContentType;
    const auto content_type_it = result->headers.find("Content-Type");
    if (content_type_it != result->headers.end()) {
        content_type = content_type_it->second;
    }
    response.set_content(result->body, content_type.c_str());
}

void proxy_get(const ProxyConfig& config, const httplib::Request& request, httplib::Response& response) {
    auto client = build_backend_client(config);
    copy_result_to_response(client.Get(request.path, build_forward_headers(request)), response);
}

void proxy_post(const ProxyConfig& config, const httplib::Request& request, httplib::Response& response) {
    auto client = build_backend_client(config);
    std::string content_type = "application/json";
    const auto content_type_it = request.headers.find("Content-Type");
    if (content_type_it != request.headers.end()) {
        content_type = content_type_it->second;
    }
    copy_result_to_response(
        client.Post(request.path, build_forward_headers(request), request.body, content_type.c_str()),
        response);
}

}

int main() {
    const ProxyConfig config = load_proxy_config_from_env();

    httplib::Server server;

    server.Get("/", [&](const httplib::Request&, httplib::Response& response) {
        std::ostringstream payload;
        payload << "{"
                << "\"service\":\"ai-prod-cpp-proxy\","
                << "\"backend\":\"" << escape_json(build_backend_base_url(config)) << "\","
                << "\"bind\":\"" << escape_json(config.bind_host + ":" + std::to_string(config.bind_port)) << "\""
                << "}";
        response.set_content(payload.str(), kJsonContentType);
    });

    server.Get("/api/v1/health", [&](const httplib::Request& request, httplib::Response& response) {
        proxy_get(config, request, response);
    });
    server.Get("/api/v1/capabilities", [&](const httplib::Request& request, httplib::Response& response) {
        proxy_get(config, request, response);
    });
    server.Get("/api/v1/license/status", [&](const httplib::Request& request, httplib::Response& response) {
        proxy_get(config, request, response);
    });
    server.Get("/api/v1/admin/revisions", [&](const httplib::Request& request, httplib::Response& response) {
        proxy_get(config, request, response);
    });
    server.Get("/api/v1/admin/operations", [&](const httplib::Request& request, httplib::Response& response) {
        proxy_get(config, request, response);
    });
    server.Post("/api/v1/admin/reload", [&](const httplib::Request& request, httplib::Response& response) {
        proxy_post(config, request, response);
    });
    server.Post(R"(/api/v1/infer/([^/]+))", [&](const httplib::Request& request, httplib::Response& response) {
        proxy_post(config, request, response);
    });

    std::cout << "[ai-prod-cpp] listening on " << config.bind_host << ':' << config.bind_port
              << ", proxying to " << build_backend_base_url(config) << std::endl;

    if (!server.listen(config.bind_host, config.bind_port)) {
        std::cerr << "[ai-prod-cpp] failed to start server" << std::endl;
        return 1;
    }
    return 0;
}
