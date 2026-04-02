#include "ai_http_server.h"

#include "input_validators.h"
#include "ai_runtime.h"
#include "license_manager.h"
#include "app_paths.h"

#include "ai_platform/ai_types.h"

#include <cpp-httplib/httplib.h>
#include <nlohmann/json.hpp>

#include <algorithm>
#include <cctype>
#include <cstdlib>
#include <cstring>
#include <iostream>
#include <sstream>
#include <unordered_map>

#include <chrono>

namespace ai_platform {

namespace {

constexpr std::size_t kMaxImageCount = 8;
constexpr std::size_t kMaxRequestIdLength = 128;

std::size_t megabytes_to_bytes(int value_mb) {
    return static_cast<std::size_t>(std::max(1, value_mb)) * 1024 * 1024;
}

std::vector<std::uint8_t> to_bytes(const std::string& value) {
    return std::vector<std::uint8_t>(value.begin(), value.end());
}

bool starts_with(const std::string& value, const std::string& prefix) {
    return value.rfind(prefix, 0) == 0;
}

std::string map_status_to_httplib_code(const std::string& status) {
    if (starts_with(status, "200")) {
        return "200";
    }
    if (starts_with(status, "401")) {
        return "401";
    }
    if (starts_with(status, "403")) {
        return "403";
    }
    if (starts_with(status, "400")) {
        return "400";
    }
    if (starts_with(status, "404")) {
        return "404";
    }
    if (starts_with(status, "405")) {
        return "405";
    }
    return "500";
}

int to_status_code(const std::string& status) {
    return std::atoi(map_status_to_httplib_code(status).c_str());
}

bool is_json_content_type(const std::string& content_type) {
    return content_type == "application/json" || starts_with(content_type, "application/json;");
}

std::string escape_json_string(const std::string& value) {
    std::string escaped;
    escaped.reserve(value.size());
    for (const char ch : value) {
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

RuntimeReloadType parse_runtime_reload_type(const std::string& body) {
    if (body.empty()) {
        return RuntimeReloadType::kAll;
    }

    try {
        const auto json_body = nlohmann::json::parse(body);
        if (!json_body.is_object() || !json_body.contains("type") || !json_body["type"].is_string()) {
            return RuntimeReloadType::kAll;
        }

        const std::string type = json_body["type"].get<std::string>();
        if (type == "plugin") {
            return RuntimeReloadType::kPlugin;
        }
        if (type == "model") {
            return RuntimeReloadType::kModel;
        }
        return RuntimeReloadType::kAll;
    } catch (const std::exception&) {
        return RuntimeReloadType::kAll;
    }
}

std::string parse_runtime_reload_target_model_dir(const std::string& body) {
    if (body.empty()) {
        return std::string();
    }

    try {
        const auto json_body = nlohmann::json::parse(body);
        if (!json_body.is_object() || !json_body.contains("target_model_dir") || !json_body["target_model_dir"].is_string()) {
            return std::string();
        }
        return json_body["target_model_dir"].get<std::string>();
    } catch (const std::exception&) {
        return std::string();
    }
}

}

bool AiHttpServer::initialize(const ServerConfig& config, AiRuntime* runtime, LicenseManager* license_manager) {
    config_ = config;
    runtime_ = runtime;
    license_manager_ = license_manager;
    return runtime_ != nullptr && license_manager_ != nullptr;
}

bool AiHttpServer::verify_admin_token(const HttpRequestContext& request) const {
    const auto token_it = request.headers.find("x-admin-token");
    if (token_it == request.headers.end()) {
        return false;
    }
    return !config_.admin_token.empty() && token_it->second == config_.admin_token;
}

AiHttpServer::HttpRequestContext AiHttpServer::build_request_context(const std::string& method, const std::string& path, const std::string& body, const std::string& content_type, const std::unordered_map<std::string, std::string>& headers) const {
    HttpRequestContext request;
    request.raw_request.clear();
    request.body = body;
    request.content_type = content_type;
    request.headers = headers;
    request.timestamp = std::chrono::duration_cast<std::chrono::milliseconds>(
        std::chrono::system_clock::now().time_since_epoch()).count();
    request.request_id = "mgmt_" + std::to_string(request.timestamp);
    request.method = method;
    request.path = path;
    request.version = "HTTP/1.1";
    request.endpoint = request.path;
    return request;
}

AiHttpServer::HttpResponseContext AiHttpServer::route_request(const HttpRequestContext& request) const {
    HttpResponseContext response;

    if (request.method == "GET" && request.path == "/test") {
        const auto license_status = license_manager_->get_status();
        if (!license_status.valid) {
            response.status = "403 Forbidden";
            response.body = build_management_error_response(request, -302, "license invalid", &license_status);
            return response;
        }
        if (!license_status.allow_test_page) {
            response.status = "403 Forbidden";
            response.body = build_management_error_response(request, -307, "test page disabled by license");
            return response;
        }
        response.content_type = "text/html; charset=utf-8";
        response.body = build_test_page_response(request);
    } else if (request.method == "GET" && request.path == "/api/v1/health") {
        response.body = build_health_response(request);
    } else if (request.method == "GET" && request.path == "/api/v1/capabilities") {
        response.body = build_capabilities_response(request);
    } else if (request.method == "GET" && request.path == "/api/v1/metrics/runtime") {
        response.body = build_runtime_metrics_response(request);
    } else if (request.method == "GET" && request.path == "/api/v1/runtime/status") {
        response.body = build_runtime_status_response(request);
    } else if (request.method == "GET" && request.path == "/api/v1/runtime/diagnostics") {
        response.body = build_runtime_diagnostics_response(request);
    } else if (request.method == "GET" && request.path == "/api/v1/license/status") {
        response.body = build_license_status_response(request);
    } else if (request.method == "POST" && request.path == "/api/v1/license/reload") {
        if (!verify_admin_token(request)) {
            response.status = "401 Unauthorized";
            response.body = build_management_error_response(request, -303, "admin token invalid");
            return response;
        }

        const auto license_status = license_manager_->get_status();
        if (license_status.valid && !license_status.allow_admin_api) {
            response.status = "403 Forbidden";
            response.body = build_management_error_response(request, -304, "admin api disabled by license");
            return response;
        }

        const bool ok = license_manager_->reload_license();
        const auto reloaded_status = license_manager_->get_status();
        if (!ok) {
            const auto reload_failure_status = license_manager_->get_last_reload_failure_status();
            response.status = "403 Forbidden";
            response.body = build_management_error_response(request, -306, "license reload failed", &reload_failure_status);
            return response;
        }

        std::ostringstream data_json;
        data_json << "{\"reloaded\":true"
                  << ",\"valid\":" << (reloaded_status.valid ? "true" : "false")
                  << ",\"allow_admin_api\":" << (reloaded_status.allow_admin_api ? "true" : "false")
                  << ",\"allow_reload\":" << (reloaded_status.allow_reload ? "true" : "false")
                  << "}";
        response.body = build_management_success_response(
            request,
            "success",
            data_json.str());
    } else if (request.method == "POST" && request.path == "/api/v1/runtime/reload-all") {
        if (!verify_admin_token(request)) {
            response.status = "401 Unauthorized";
            response.body = build_management_error_response(request, -303, "admin token invalid");
            return response;
        }

        const auto license_status = license_manager_->get_status();
        if (!license_status.valid) {
            response.status = "403 Forbidden";
            response.body = build_management_error_response(request, -302, "license invalid", &license_status);
            return response;
        }
        if (!license_status.allow_admin_api) {
            response.status = "403 Forbidden";
            response.body = build_management_error_response(request, -304, "admin api disabled by license");
            return response;
        }
        if (!license_status.allow_reload) {
            response.status = "403 Forbidden";
            response.body = build_management_error_response(request, -305, "reload disabled by license");
            return response;
        }

        const auto capabilities = runtime_->list_capabilities();
        const auto reload_type = parse_runtime_reload_type(request.body);
        const auto target_model_dir = parse_runtime_reload_target_model_dir(request.body);
        const auto reload_result = runtime_->reload_all_capabilities(reload_type, target_model_dir);
        if (!reload_result.ok) {
            response.status = "400 Bad Request";
            std::ostringstream data_json;
            data_json << "{\"reloaded_all\":true"
                      << ",\"reload_type\":\"" << escape_json_string(reload_result.reload_type) << "\""
                      << ",\"previous_model_dir\":\"" << escape_json_string(reload_result.previous_model_dir) << "\""
                      << ",\"current_model_dir\":\"" << escape_json_string(reload_result.current_model_dir) << "\""
                      << ",\"rollback_performed\":" << (reload_result.rollback_performed ? "true" : "false")
                      << ",\"rollback_source_model_dir\":\"" << escape_json_string(reload_result.rollback_source_model_dir) << "\""
                      << ",\"rollback_target_model_dir\":\"" << escape_json_string(reload_result.rollback_target_model_dir) << "\""
                      << ",\"rolled_back\":" << (reload_result.rolled_back ? "true" : "false")
                      << ",\"restored_previous_state\":" << (reload_result.restored_previous_state ? "true" : "false")
                      << ",\"target_model_dir\":\"" << escape_json_string(reload_result.target_model_dir) << "\""
                      << ",\"reloaded_capability_ids\":[";
            for (std::size_t i = 0; i < reload_result.reloaded_capability_ids.size(); ++i) {
                if (i > 0) {
                    data_json << ',';
                }
                data_json << "\"" << escape_json_string(reload_result.reloaded_capability_ids[i]) << "\"";
            }
            data_json << "],\"failed_capability_ids\":[";
            for (std::size_t i = 0; i < reload_result.failed_capability_ids.size(); ++i) {
                if (i > 0) {
                    data_json << ',';
                }
                data_json << "\"" << escape_json_string(reload_result.failed_capability_ids[i]) << "\"";
            }
            data_json << "],\"reload_failure_details\":[";
            for (std::size_t i = 0; i < reload_result.reload_failure_details.size(); ++i) {
                if (i > 0) {
                    data_json << ',';
                }
                const auto& detail = reload_result.reload_failure_details[i];
                data_json << "{\"capability_id\":\"" << escape_json_string(detail.capability_id) << "\""
                          << ",\"reload_reason\":\"" << escape_json_string(detail.reload_reason) << "\""
                          << ",\"reload_failed_stage\":\"" << escape_json_string(detail.reload_failed_stage) << "\""
                          << ",\"previous_model_dir\":\"" << escape_json_string(detail.previous_model_dir) << "\""
                          << ",\"current_model_dir\":\"" << escape_json_string(detail.current_model_dir) << "\""
                          << ",\"target_model_dir\":\"" << escape_json_string(detail.target_model_dir) << "\""
                          << ",\"message\":\"" << escape_json_string(detail.message) << "\"}";
            }
            data_json << "]}";
            response.body = build_management_error_response(request, -301, reload_result.message.empty() ? "reload all failed" : reload_result.message, nullptr, data_json.str());
            return response;
        }
        std::ostringstream data_json;
        data_json << "{\"reloaded_all\":true"
                  << ",\"reload_type\":\"" << escape_json_string(reload_result.reload_type) << "\""
                  << ",\"previous_model_dir\":\"" << escape_json_string(reload_result.previous_model_dir) << "\""
                  << ",\"current_model_dir\":\"" << escape_json_string(reload_result.current_model_dir) << "\""
                  << ",\"rollback_performed\":" << (reload_result.rollback_performed ? "true" : "false")
                  << ",\"rollback_source_model_dir\":\"" << escape_json_string(reload_result.rollback_source_model_dir) << "\""
                  << ",\"rollback_target_model_dir\":\"" << escape_json_string(reload_result.rollback_target_model_dir) << "\""
                  << ",\"rolled_back\":" << (reload_result.rolled_back ? "true" : "false")
                  << ",\"restored_previous_state\":" << (reload_result.restored_previous_state ? "true" : "false")
                  << ",\"target_model_dir\":\"" << escape_json_string(reload_result.target_model_dir) << "\""
                  << ",\"capability_count\":" << capabilities.size()
                  << ",\"capability_ids\":[";
        for (std::size_t i = 0; i < capabilities.size(); ++i) {
            if (i > 0) {
                data_json << ',';
            }
            data_json << "\"" << escape_json_string(capabilities[i].capability_id) << "\"";
        }
        data_json << "],\"reloaded_capability_ids\":[";
        for (std::size_t i = 0; i < reload_result.reloaded_capability_ids.size(); ++i) {
            if (i > 0) {
                data_json << ',';
            }
            data_json << "\"" << escape_json_string(reload_result.reloaded_capability_ids[i]) << "\"";
        }
        data_json << "],\"failed_capability_ids\":[";
        for (std::size_t i = 0; i < reload_result.failed_capability_ids.size(); ++i) {
            if (i > 0) {
                data_json << ',';
            }
            data_json << "\"" << escape_json_string(reload_result.failed_capability_ids[i]) << "\"";
        }
        data_json << "],\"reload_failure_details\":[";
        for (std::size_t i = 0; i < reload_result.reload_failure_details.size(); ++i) {
            if (i > 0) {
                data_json << ',';
            }
            const auto& detail = reload_result.reload_failure_details[i];
            data_json << "{\"capability_id\":\"" << escape_json_string(detail.capability_id) << "\""
                      << ",\"reload_reason\":\"" << escape_json_string(detail.reload_reason) << "\""
                      << ",\"reload_failed_stage\":\"" << escape_json_string(detail.reload_failed_stage) << "\""
                      << ",\"previous_model_dir\":\"" << escape_json_string(detail.previous_model_dir) << "\""
                      << ",\"current_model_dir\":\"" << escape_json_string(detail.current_model_dir) << "\""
                      << ",\"target_model_dir\":\"" << escape_json_string(detail.target_model_dir) << "\""
                      << ",\"message\":\"" << escape_json_string(detail.message) << "\"}";
        }
        data_json << "]}";
        response.body = build_management_success_response(
            request,
            "success",
            data_json.str());
    } else if (request.method == "POST" && starts_with(request.path, "/api/v1/runtime/reload/")) {
        if (!verify_admin_token(request)) {
            response.status = "401 Unauthorized";
            response.body = build_management_error_response(request, -303, "admin token invalid");
            return response;
        }

        const auto license_status = license_manager_->get_status();
        if (!license_status.valid) {
            response.status = "403 Forbidden";
            response.body = build_management_error_response(request, -302, "license invalid", &license_status);
            return response;
        }
        if (!license_status.allow_admin_api) {
            response.status = "403 Forbidden";
            response.body = build_management_error_response(request, -304, "admin api disabled by license");
            return response;
        }
        if (!license_status.allow_reload) {
            response.status = "403 Forbidden";
            response.body = build_management_error_response(request, -305, "reload disabled by license");
            return response;
        }

        const std::string capability_id = request.path.substr(std::strlen("/api/v1/runtime/reload/"));
        const auto reload_type = parse_runtime_reload_type(request.body);
        const auto target_model_dir = parse_runtime_reload_target_model_dir(request.body);
        const auto reload_result = runtime_->reload_capability(capability_id, reload_type, target_model_dir);
        if (!reload_result.ok) {
            response.status = "400 Bad Request";
            response.body = build_management_error_response(request, -300, reload_result.message.empty() ? "reload failed" : reload_result.message);
            return response;
        }
        const auto capabilities = runtime_->list_capabilities();
        std::ostringstream data_json;
        data_json << "{\"capability_id\":\"" << escape_json_string(capability_id) << "\",\"reloaded\":true"
                  << ",\"reload_type\":\"" << escape_json_string(reload_result.reload_type) << "\""
                  << ",\"previous_model_dir\":\"" << escape_json_string(reload_result.previous_model_dir) << "\""
                  << ",\"current_model_dir\":\"" << escape_json_string(reload_result.current_model_dir) << "\""
                  << ",\"rollback_performed\":" << (reload_result.rollback_performed ? "true" : "false")
                  << ",\"rollback_source_model_dir\":\"" << escape_json_string(reload_result.rollback_source_model_dir) << "\""
                  << ",\"rollback_target_model_dir\":\"" << escape_json_string(reload_result.rollback_target_model_dir) << "\""
                  << ",\"rolled_back\":" << (reload_result.rolled_back ? "true" : "false")
                  << ",\"restored_previous_state\":" << (reload_result.restored_previous_state ? "true" : "false")
                  << ",\"target_model_dir\":\"" << escape_json_string(reload_result.target_model_dir) << "\""
                  << ",\"message\":\"" << escape_json_string(reload_result.message) << "\"";
        for (const auto& capability : capabilities) {
            if (capability.capability_id == capability_id) {
                data_json << ",\"status\":\"" << escape_json_string(capability.status) << "\"";
                data_json << ",\"device\":\"" << escape_json_string(capability.device) << "\"";
                data_json << ",\"model_dir\":\"" << escape_json_string(capability.model_dir) << "\"";
                break;
            }
        }
        data_json << "}";
        response.body = build_management_success_response(
            request,
            "success",
            data_json.str());
    } else if (request.method == "POST" && request.path == "/api/v1/runtime/rollback-all") {
        if (!verify_admin_token(request)) {
            response.status = "401 Unauthorized";
            response.body = build_management_error_response(request, -303, "admin token invalid");
            return response;
        }

        const auto license_status = license_manager_->get_status();
        if (!license_status.valid) {
            response.status = "403 Forbidden";
            response.body = build_management_error_response(request, -302, "license invalid", &license_status);
            return response;
        }
        if (!license_status.allow_admin_api) {
            response.status = "403 Forbidden";
            response.body = build_management_error_response(request, -304, "admin api disabled by license");
            return response;
        }
        if (!license_status.allow_reload) {
            response.status = "403 Forbidden";
            response.body = build_management_error_response(request, -305, "reload disabled by license");
            return response;
        }

        const auto rollback_result = runtime_->rollback_all_capabilities();
        if (!rollback_result.ok) {
            response.status = "400 Bad Request";
            std::ostringstream data_json;
            data_json << "{\"rollback_all\":true"
                      << ",\"rollback_performed\":" << (rollback_result.rollback_performed ? "true" : "false")
                      << ",\"rolled_back\":" << (rollback_result.rolled_back ? "true" : "false")
                      << ",\"restored_previous_state\":" << (rollback_result.restored_previous_state ? "true" : "false")
                      << ",\"rollback_reason\":\"" << escape_json_string(rollback_result.rollback_reason) << "\""
                      << ",\"rollback_failed_stage\":\"" << escape_json_string(rollback_result.rollback_failed_stage) << "\""
                      << ",\"rolled_back_capability_ids\":[";
            for (std::size_t i = 0; i < rollback_result.rolled_back_capability_ids.size(); ++i) {
                if (i > 0) {
                    data_json << ',';
                }
                data_json << "\"" << escape_json_string(rollback_result.rolled_back_capability_ids[i]) << "\"";
            }
            data_json << "],\"failed_capability_ids\":[";
            for (std::size_t i = 0; i < rollback_result.failed_capability_ids.size(); ++i) {
                if (i > 0) {
                    data_json << ',';
                }
                data_json << "\"" << escape_json_string(rollback_result.failed_capability_ids[i]) << "\"";
            }
            data_json << "],\"rollback_failure_details\":[";
            for (std::size_t i = 0; i < rollback_result.rollback_failure_details.size(); ++i) {
                if (i > 0) {
                    data_json << ',';
                }
                const auto& detail = rollback_result.rollback_failure_details[i];
                data_json << "{\"capability_id\":\"" << escape_json_string(detail.capability_id) << "\""
                          << ",\"rollback_reason\":\"" << escape_json_string(detail.rollback_reason) << "\""
                          << ",\"rollback_failed_stage\":\"" << escape_json_string(detail.rollback_failed_stage) << "\""
                          << ",\"previous_model_dir\":\"" << escape_json_string(detail.previous_model_dir) << "\""
                          << ",\"current_model_dir\":\"" << escape_json_string(detail.current_model_dir) << "\""
                          << ",\"target_model_dir\":\"" << escape_json_string(detail.target_model_dir) << "\""
                          << ",\"message\":\"" << escape_json_string(detail.message) << "\"}";
            }
            data_json << "]}";
            response.body = build_management_error_response(request, -309, rollback_result.message.empty() ? "rollback all failed" : rollback_result.message, nullptr, data_json.str());
            return response;
        }

        std::ostringstream data_json;
        data_json << "{\"rollback_all\":true"
                  << ",\"rollback_performed\":" << (rollback_result.rollback_performed ? "true" : "false")
                  << ",\"rolled_back\":" << (rollback_result.rolled_back ? "true" : "false")
                  << ",\"restored_previous_state\":" << (rollback_result.restored_previous_state ? "true" : "false")
                  << ",\"rollback_reason\":\"" << escape_json_string(rollback_result.rollback_reason) << "\""
                  << ",\"rollback_failed_stage\":\"" << escape_json_string(rollback_result.rollback_failed_stage) << "\""
                  << ",\"message\":\"" << escape_json_string(rollback_result.message) << "\""
                  << ",\"rolled_back_capability_ids\":[";
        for (std::size_t i = 0; i < rollback_result.rolled_back_capability_ids.size(); ++i) {
            if (i > 0) {
                data_json << ',';
            }
            data_json << "\"" << escape_json_string(rollback_result.rolled_back_capability_ids[i]) << "\"";
        }
        data_json << "],\"failed_capability_ids\":[";
        for (std::size_t i = 0; i < rollback_result.failed_capability_ids.size(); ++i) {
            if (i > 0) {
                data_json << ',';
            }
            data_json << "\"" << escape_json_string(rollback_result.failed_capability_ids[i]) << "\"";
        }
        data_json << "],\"rollback_failure_details\":[";
        for (std::size_t i = 0; i < rollback_result.rollback_failure_details.size(); ++i) {
            if (i > 0) {
                data_json << ',';
            }
            const auto& detail = rollback_result.rollback_failure_details[i];
            data_json << "{\"capability_id\":\"" << escape_json_string(detail.capability_id) << "\""
                      << ",\"rollback_reason\":\"" << escape_json_string(detail.rollback_reason) << "\""
                      << ",\"rollback_failed_stage\":\"" << escape_json_string(detail.rollback_failed_stage) << "\""
                      << ",\"previous_model_dir\":\"" << escape_json_string(detail.previous_model_dir) << "\""
                      << ",\"current_model_dir\":\"" << escape_json_string(detail.current_model_dir) << "\""
                      << ",\"target_model_dir\":\"" << escape_json_string(detail.target_model_dir) << "\""
                      << ",\"message\":\"" << escape_json_string(detail.message) << "\"}";
        }
        data_json << "]}";
        response.body = build_management_success_response(
            request,
            "success",
            data_json.str());
    } else if (request.method == "POST" && starts_with(request.path, "/api/v1/runtime/rollback/")) {
        if (!verify_admin_token(request)) {
            response.status = "401 Unauthorized";
            response.body = build_management_error_response(request, -303, "admin token invalid");
            return response;
        }

        const auto license_status = license_manager_->get_status();
        if (!license_status.valid) {
            response.status = "403 Forbidden";
            response.body = build_management_error_response(request, -302, "license invalid", &license_status);
            return response;
        }
        if (!license_status.allow_admin_api) {
            response.status = "403 Forbidden";
            response.body = build_management_error_response(request, -304, "admin api disabled by license");
            return response;
        }
        if (!license_status.allow_reload) {
            response.status = "403 Forbidden";
            response.body = build_management_error_response(request, -305, "reload disabled by license");
            return response;
        }

        const std::string capability_id = request.path.substr(std::strlen("/api/v1/runtime/rollback/"));
        const auto rollback_result = runtime_->rollback_capability(capability_id);
        if (!rollback_result.ok) {
            response.status = "400 Bad Request";
            std::ostringstream data_json;
            data_json << "{\"capability_id\":\"" << escape_json_string(capability_id) << "\""
                      << ",\"rollback_performed\":" << (rollback_result.rollback_performed ? "true" : "false")
                      << ",\"rollback_source_model_dir\":\"" << escape_json_string(rollback_result.rollback_source_model_dir) << "\""
                      << ",\"rollback_target_model_dir\":\"" << escape_json_string(rollback_result.rollback_target_model_dir) << "\""
                      << ",\"rollback_reason\":\"" << escape_json_string(rollback_result.rollback_reason) << "\""
                      << ",\"rollback_failed_stage\":\"" << escape_json_string(rollback_result.rollback_failed_stage) << "\""
                      << ",\"previous_model_dir\":\"" << escape_json_string(rollback_result.previous_model_dir) << "\""
                      << ",\"current_model_dir\":\"" << escape_json_string(rollback_result.current_model_dir) << "\""
                      << ",\"target_model_dir\":\"" << escape_json_string(rollback_result.target_model_dir) << "\""
                      << "}";
            response.body = build_management_error_response(request, -308, rollback_result.message.empty() ? "rollback failed" : rollback_result.message, nullptr, data_json.str());
            return response;
        }

        std::ostringstream data_json;
        data_json << "{\"capability_id\":\"" << escape_json_string(capability_id) << "\",\"rolled_back\":true"
                  << ",\"reload_type\":\"" << escape_json_string(rollback_result.reload_type) << "\""
                  << ",\"previous_model_dir\":\"" << escape_json_string(rollback_result.previous_model_dir) << "\""
                  << ",\"current_model_dir\":\"" << escape_json_string(rollback_result.current_model_dir) << "\""
                  << ",\"target_model_dir\":\"" << escape_json_string(rollback_result.target_model_dir) << "\""
                  << ",\"rollback_performed\":" << (rollback_result.rollback_performed ? "true" : "false")
                  << ",\"rollback_source_model_dir\":\"" << escape_json_string(rollback_result.rollback_source_model_dir) << "\""
                  << ",\"rollback_target_model_dir\":\"" << escape_json_string(rollback_result.rollback_target_model_dir) << "\""
                  << ",\"rollback_reason\":\"" << escape_json_string(rollback_result.rollback_reason) << "\""
                  << ",\"rollback_failed_stage\":\"" << escape_json_string(rollback_result.rollback_failed_stage) << "\""
                  << ",\"restored_previous_state\":" << (rollback_result.restored_previous_state ? "true" : "false")
                  << ",\"message\":\"" << escape_json_string(rollback_result.message) << "\"";
        const auto capabilities = runtime_->list_capabilities();
        for (const auto& capability : capabilities) {
            if (capability.capability_id == capability_id) {
                data_json << ",\"status\":\"" << escape_json_string(capability.status) << "\"";
                data_json << ",\"device\":\"" << escape_json_string(capability.device) << "\"";
                data_json << ",\"model_dir\":\"" << escape_json_string(capability.model_dir) << "\"";
                break;
            }
        }
        data_json << "}";
        response.body = build_management_success_response(
            request,
            "success",
            data_json.str());
    } else if (request.method == "POST" && starts_with(request.path, "/api/v1/infer/")) {
        const InferRequestBuildResult infer_build_result = build_infer_request(request);
        const InferRequest& infer_request = infer_build_result.request;

        if (!infer_build_result.ok) {
            response.status = "400 Bad Request";
            response.body = build_infer_error_response(request, infer_request, infer_build_result.error_code, infer_build_result.error_message);
            return response;
        }

        const auto license_status = license_manager_->get_status();
        if (!license_status.valid) {
            response.status = "403 Forbidden";
            response.body = build_infer_error_response(request, infer_request, -402, "license invalid", &license_status);
            return response;
        }

        if (!license_manager_->quick_check(infer_request.capability_id)) {
            response.status = "403 Forbidden";
            response.body = build_infer_error_response(request, infer_request, -401, "capability not licensed");
            return response;
        }

        const InferResult infer_result = runtime_->infer(infer_request);
        std::ostringstream infer_response;
        infer_response << "{\"code\":" << infer_result.code
                       << ",\"message\":\"" << escape_json_string(infer_result.message)
                       << "\",\"data\":" << infer_result.data_json
                       << ",\"request_id\":\"" << escape_json_string(infer_result.request_id)
                       << "\",\"endpoint\":\"" << escape_json_string(request.path)
                       << "\",\"timestamp\":" << infer_request.timestamp
                       << ",\"cost_ms\":" << infer_result.cost_ms
                       << ",\"api_version\":\"v1\"}";
        response.body = infer_response.str();
    } else if ((request.path == "/api/v1/runtime/status" || request.path == "/api/v1/license/status" ||
                request.path == "/api/v1/capabilities" || request.path == "/api/v1/health" ||
                request.path == "/api/v1/metrics/runtime") && request.method != "GET") {
        response.status = "405 Method Not Allowed";
        response.body = build_method_not_allowed_response(request, "GET");
        response.headers.push_back("Allow: GET");
    } else if (request.path == "/test" && request.method != "GET") {
        response.status = "405 Method Not Allowed";
        response.body = build_method_not_allowed_response(request, "GET");
        response.headers.push_back("Allow: GET");
    } else if (starts_with(request.path, "/api/v1/infer/") && request.method != "POST") {
        response.status = "405 Method Not Allowed";
        std::ostringstream infer_error_response;
        infer_error_response << "{\"code\":-405,\"message\":\"method not allowed\",\"data\":null"
                             << ",\"allow\":\"POST\",\"request_id\":\"req_" << request.timestamp
                             << "\",\"endpoint\":\"" << escape_json_string(request.path)
                             << "\",\"timestamp\":" << request.timestamp
                             << ",\"cost_ms\":0,\"api_version\":\"v1\"}";
        response.body = infer_error_response.str();
        response.headers.push_back("Allow: POST");
    } else if ((request.path == "/api/v1/license/reload" || request.path == "/api/v1/runtime/reload-all" || request.path == "/api/v1/runtime/rollback-all" || starts_with(request.path, "/api/v1/runtime/reload/") || starts_with(request.path, "/api/v1/runtime/rollback/")) && request.method != "POST") {
        response.status = "405 Method Not Allowed";
        response.body = build_method_not_allowed_response(request, "POST");
        response.headers.push_back("Allow: POST");
    } else if (starts_with(request.path, "/api/v1/")) {
        response.status = "404 Not Found";
        response.body = build_management_error_response(request, -1, "not found");
    } else {
        response.status = "404 Not Found";
        response.body = build_error_response(-1, "not found");
    }

    return response;

}

AiHttpServer::InferRequestBuildResult AiHttpServer::build_infer_request(const HttpRequestContext& request) const {
    InferRequestBuildResult result;
    result.request.capability_id = request.path.substr(std::strlen("/api/v1/infer/"));
    result.request.timestamp = std::chrono::duration_cast<std::chrono::milliseconds>(
        std::chrono::system_clock::now().time_since_epoch()).count();
    result.request.request_id = "req_" + std::to_string(result.request.timestamp);
    result.request.params_json = "{}";

    const auto fail = [&result](int code, const std::string& message) {
        result.error_code = code;
        result.error_message = message;
        return result;
    };

    if (!is_json_content_type(request.content_type)) {
        return fail(-400, "content-type must be application/json");
    }

    if (request.body.empty()) {
        return fail(-400, "empty request body");
    }

    if (request.body.size() > megabytes_to_bytes(config_.max_body_size_mb)) {
        return fail(-400, "request body too large");
    }

    nlohmann::json body_json;
    try {
        body_json = nlohmann::json::parse(request.body);
    } catch (const nlohmann::json::parse_error&) {
        return fail(-400, "invalid json body");
    }

    if (!body_json.is_object()) {
        return fail(-400, "invalid json body");
    }

    const auto parse_request_metadata = [&]() -> bool {
        if (body_json.contains("request_id")) {
            if (!body_json["request_id"].is_string() || body_json["request_id"].get<std::string>().empty()) {
                result = fail(-400, "invalid request_id");
                return false;
            }
            result.request.request_id = body_json["request_id"].get<std::string>();
            if (result.request.request_id.size() > kMaxRequestIdLength) {
                result = fail(-400, "request_id too long");
                return false;
            }
        }

        if (body_json.contains("params")) {
            if (!body_json["params"].is_object()) {
                result = fail(-400, "invalid params");
                return false;
            }
            result.request.params_json = body_json["params"].dump();
        }

        return true;
    };

    const auto parse_images = [&]() -> bool {
        if (!body_json.contains("images")) {
            return true;
        }
        if (!body_json["images"].is_array()) {
            result = fail(-400, "invalid images");
            return false;
        }
        if (body_json["images"].empty()) {
            result = fail(-400, "images array is empty");
            return false;
        }
        if (body_json["images"].size() > kMaxImageCount) {
            result = fail(-400, "too many images");
            return false;
        }

        for (const auto& image_item : body_json["images"]) {
            if (!image_item.is_object()) {
                result = fail(-400, "invalid image item");
                return false;
            }

            ImageData image;
            image.source = "json_body";
            image.format = "unknown";

            ImageFieldValidationSummary image_validation;

            if (image_item.contains("format")) {
                if (!image_item["format"].is_string() || image_item["format"].get<std::string>().empty()) {
                    result = fail(-400, "invalid image format");
                    return false;
                }
                image.format = image_item["format"].get<std::string>();
                image_validation.has_format = true;
                image_validation.format = image.format;
            }

            if (image_item.contains("data")) {
                if (!image_item["data"].is_string()) {
                    result = fail(-400, "invalid image data");
                    return false;
                }
                const std::string image_data = image_item["data"].get<std::string>();
                image_validation.has_data = true;
                image_validation.data_text = image_data;
                image.data = to_bytes(image_data);
            }

            if (image.data.empty() && image_item.contains("uri")) {
                if (!image_item["uri"].is_string() || image_item["uri"].get<std::string>().empty()) {
                    result = fail(-400, "invalid image uri");
                    return false;
                }
                const std::string image_uri = image_item["uri"].get<std::string>();
                image_validation.has_uri = true;
                image_validation.uri = image_uri;
                image.source = image_uri;
            }

            const auto image_validation_result = validate_image_fields(image_validation);
            if (!image_validation_result.ok) {
                result = fail(image_validation_result.error_code, image_validation_result.error_message);
                return false;
            }

            result.request.images.push_back(image);
        }

        return true;
    };

    const auto parse_media = [&]() -> bool {
        if (!body_json.contains("media")) {
            return true;
        }
        if (!body_json["media"].is_object()) {
            result = fail(-400, "invalid media");
            return false;
        }

        const auto& media_item = body_json["media"];
        MediaData media;
        media.source = "json_body";
        media.format = "unknown";

        MediaFieldValidationSummary media_validation;
        media_validation.max_data_bytes = megabytes_to_bytes(config_.max_video_size_mb);

        if (!media_item.contains("type") || !media_item["type"].is_string() || media_item["type"].get<std::string>().empty()) {
            result = fail(-400, "invalid media type");
            return false;
        }
        media.media_type = media_item["type"].get<std::string>();
        media_validation.has_type = true;
        media_validation.media_type = media.media_type;

        if (media_item.contains("format")) {
            if (!media_item["format"].is_string() || media_item["format"].get<std::string>().empty()) {
                result = fail(-400, "invalid media format");
                return false;
            }
            media.format = media_item["format"].get<std::string>();
            media_validation.has_format = true;
            media_validation.format = media.format;
        }

        if (media_item.contains("data")) {
            if (!media_item["data"].is_string()) {
                result = fail(-400, "invalid media data");
                return false;
            }
            const std::string media_data = media_item["data"].get<std::string>();
            media_validation.has_data = true;
            media_validation.data_text = media_data;
            media.data = to_bytes(media_data);
        }

        if (media.data.empty() && media_item.contains("uri")) {
            if (!media_item["uri"].is_string() || media_item["uri"].get<std::string>().empty()) {
                result = fail(-400, "invalid media uri");
                return false;
            }
            const std::string media_uri = media_item["uri"].get<std::string>();
            media_validation.has_uri = true;
            media_validation.uri = media_uri;
            media.source = media_uri;
        }

        const auto media_validation_result = validate_media_fields(media_validation);
        if (!media_validation_result.ok) {
            result = fail(media_validation_result.error_code, media_validation_result.error_message);
            return false;
        }

        result.request.media.push_back(media);
        return true;
    };

    const auto validate_request = [&]() -> bool {
        InferRequestValidationSummary validation_summary;
        validation_summary.capability_id = result.request.capability_id;
        validation_summary.image_count = result.request.images.size();
        validation_summary.media_count = result.request.media.size();
        validation_summary.has_params = body_json.contains("params") && body_json["params"].is_object();
        if (validation_summary.has_params && body_json["params"].contains("action") && body_json["params"]["action"].is_string()) {
            validation_summary.liveness_action = body_json["params"]["action"].get<std::string>();
        }
        const auto validation_result = validate_infer_request_summary(validation_summary);
        if (!validation_result.ok) {
            result = fail(validation_result.error_code, validation_result.error_message);
            return false;
        }
        return true;
    };

    if (!parse_request_metadata() || !parse_images() || !parse_media() || !validate_request()) {
        return result;
    }

    result.ok = true;
    return result;
}

bool AiHttpServer::start() {
    try {
        server_ = std::make_unique<httplib::Server>();
        running_ = true;
        server_->set_read_timeout(std::chrono::milliseconds(std::max(1, config_.request_timeout_ms)));
        server_->set_write_timeout(std::chrono::milliseconds(std::max(1, config_.request_timeout_ms)));
        server_->set_payload_max_length(megabytes_to_bytes(config_.max_body_size_mb));
        server_->new_task_queue = [workers = static_cast<std::size_t>(std::max(1, config_.workers))]() {
            return new httplib::ThreadPool(workers);
        };

        auto handler = [this](const httplib::Request& req, httplib::Response& res) {
            const auto content_type = req.get_header_value("Content-Type");
            std::unordered_map<std::string, std::string> headers;
            for (const auto& header : req.headers) {
                std::string key = header.first;
                std::transform(key.begin(), key.end(), key.begin(), [](unsigned char ch) {
                    return static_cast<char>(std::tolower(ch));
                });
                headers.emplace(std::move(key), header.second);
            }
            const auto request = build_request_context(req.method, req.path, req.body, content_type, headers);
            const auto response = route_request(request);
            res.status = to_status_code(response.status);
            res.set_content(response.body, response.content_type.c_str());
            for (const auto& header : response.headers) {
                const auto pos = header.find(':');
                if (pos == std::string::npos) {
                    continue;
                }
                std::string name = header.substr(0, pos);
                std::string value = header.substr(pos + 1);
                while (!value.empty() && value.front() == ' ') {
                    value.erase(value.begin());
                }
                res.set_header(name.c_str(), value.c_str());
            }
        };

        server_->Get(R"(/.*)", handler);
        server_->Post(R"(/.*)", handler);
        server_->Put(R"(/.*)", handler);
        server_->Delete(R"(/.*)", handler);
        server_->Patch(R"(/.*)", handler);
        server_->Options(R"(/.*)", handler);

        std::cout << "AiHttpServer listening on " << config_.host << ':' << config_.port << std::endl;
        const bool ok = server_->listen(config_.host.c_str(), config_.port);
        running_ = false;
        return ok;
    } catch (const std::exception& ex) {
        std::cerr << "AiHttpServer start failed: " << ex.what() << std::endl;
        return false;
    }
}

void AiHttpServer::stop() {
    running_ = false;
    if (server_ != nullptr) {
        server_->stop();
    }
}

std::string AiHttpServer::build_health_response(const HttpRequestContext& request) const {
    return build_management_success_response(
        request,
        "healthy",
        "{\"status\":\"healthy\",\"port\":" + std::to_string(config_.port) + "}");
}

std::string AiHttpServer::build_test_page_response(const HttpRequestContext& request) const {
    const auto status = license_manager_->get_status();
    std::ostringstream oss;
    oss << "<!DOCTYPE html><html><head><meta charset=\"utf-8\"><title>AI Platform Test Page</title></head><body>";
    oss << "<h1>AI Platform Test Page</h1>";
    oss << "<p>license_valid=" << (status.valid ? "true" : "false") << "</p>";
    oss << "<p>allow_test_page=" << (status.allow_test_page ? "true" : "false") << "</p>";
    oss << "<p>request_id=" << escape_json_string(request.request_id) << "</p>";
    oss << "</body></html>";
    return oss.str();
}

std::string AiHttpServer::build_capabilities_response(const HttpRequestContext& request) const {
    const auto capabilities = runtime_->list_capabilities();
    const auto metrics = runtime_->list_metrics();
    std::unordered_map<std::string, CapabilityMetricsInfo> metrics_by_capability;
    metrics_by_capability.reserve(metrics.size());
    for (const auto& metric : metrics) {
        metrics_by_capability[metric.capability_id] = metric;
    }
    std::size_t ready_count = 0;
    std::size_t not_ready_count = 0;
    std::size_t unknown_count = 0;
    std::size_t draining_count = 0;
    std::size_t total_pool_size = 0;
    std::size_t total_busy_count = 0;
    std::size_t total_request_count = 0;
    std::size_t total_success_count = 0;
    std::size_t total_failure_count = 0;
    std::size_t total_busy_reject_count = 0;
    double total_cost_ms = 0.0;
    double avg_cost_ms = 0.0;
    std::int64_t last_request_timestamp = 0;
    std::int64_t last_success_timestamp = 0;
    std::int64_t last_failure_timestamp = 0;
    std::string last_failure_capability_id;
    int last_failure_error_code = 0;
    for (const auto& capability : capabilities) {
        total_pool_size += capability.pool_size;
        total_busy_count += capability.busy_count;
        if (capability.draining) {
            ++draining_count;
            ++not_ready_count;
        } else if (capability.status == "ready") {
            ++ready_count;
        } else if (capability.status.empty()) {
            ++unknown_count;
        } else {
            ++not_ready_count;
        }
    }
    for (const auto& metric : metrics) {
        total_request_count += metric.request_count;
        total_success_count += metric.success_count;
        total_failure_count += metric.failure_count;
        total_busy_reject_count += metric.busy_reject_count;
        total_cost_ms += metric.total_cost_ms;
        if (metric.last_request_timestamp > last_request_timestamp) {
            last_request_timestamp = metric.last_request_timestamp;
        }
        if (metric.last_success_timestamp > last_success_timestamp) {
            last_success_timestamp = metric.last_success_timestamp;
        }
        if (metric.last_failure_timestamp > last_failure_timestamp) {
            last_failure_timestamp = metric.last_failure_timestamp;
            last_failure_capability_id = metric.capability_id;
            last_failure_error_code = metric.last_error_code;
        }
    }
    if (total_success_count > 0) {
        avg_cost_ms = total_cost_ms / static_cast<double>(total_success_count);
    }
    std::ostringstream oss;
    oss << "{\"summary\":{\"capability_count\":" << capabilities.size()
        << ",\"ready_count\":" << ready_count
        << ",\"not_ready_count\":" << not_ready_count
        << ",\"draining_count\":" << draining_count
        << ",\"pool_size\":" << total_pool_size
        << ",\"busy_count\":" << total_busy_count
        << ",\"status_breakdown\":{\"ready\":" << ready_count
        << ",\"draining\":" << draining_count
        << ",\"not_ready\":" << not_ready_count
        << ",\"unknown\":" << unknown_count << "},\"metrics\":{\"request_count\":" << total_request_count
        << ",\"success_count\":" << total_success_count
        << ",\"failure_count\":" << total_failure_count
        << ",\"busy_reject_count\":" << total_busy_reject_count
        << ",\"total_cost_ms\":" << total_cost_ms
        << ",\"avg_cost_ms\":" << avg_cost_ms
        << ",\"last_request_timestamp\":" << last_request_timestamp
        << ",\"last_success_timestamp\":" << last_success_timestamp
        << ",\"last_failure_timestamp\":" << last_failure_timestamp
        << ",\"last_failure_capability_id\":\"" << escape_json_string(last_failure_capability_id)
        << "\",\"last_failure_error_code\":" << last_failure_error_code << "}},\"capabilities\":[";
    for (std::size_t i = 0; i < capabilities.size(); ++i) {
        const auto& capability = capabilities[i];
        const auto metrics_it = metrics_by_capability.find(capability.capability_id);
        const CapabilityMetricsInfo capability_metrics = metrics_it == metrics_by_capability.end()
            ? CapabilityMetricsInfo{capability.capability_id}
            : metrics_it->second;
        if (i > 0) {
            oss << ',';
        }
        oss << "{\"capability_id\":\"" << escape_json_string(capability.capability_id)
            << "\",\"name\":\"" << escape_json_string(capability.name)
            << "\",\"version\":\"" << escape_json_string(capability.version)
            << "\",\"model_version\":\"" << escape_json_string(capability.model_version)
            << "\",\"model_dir\":\"" << escape_json_string(capability.model_dir)
            << "\",\"description\":\"" << escape_json_string(capability.description)
            << "\",\"library_path\":\"" << escape_json_string(capability.library_path)
            << "\",\"configured_device\":\"" << escape_json_string(capability.configured_device)
            << "\",\"max_batch_size\":" << capability.max_batch_size
            << ",\"device\":\"" << escape_json_string(capability.device)
            << "\",\"status\":\"" << escape_json_string(capability.status)
            << "\",\"pool_size\":" << capability.pool_size
            << ",\"busy_count\":" << capability.busy_count
            << ",\"ready\":" << (capability.ready ? "true" : "false")
            << ",\"draining\":" << (capability.draining ? "true" : "false")
            << ",\"metrics\":{\"request_count\":" << capability_metrics.request_count
            << ",\"success_count\":" << capability_metrics.success_count
            << ",\"failure_count\":" << capability_metrics.failure_count
            << ",\"busy_reject_count\":" << capability_metrics.busy_reject_count
            << ",\"avg_cost_ms\":" << capability_metrics.avg_cost_ms
            << ",\"last_request_timestamp\":" << capability_metrics.last_request_timestamp
            << ",\"last_success_timestamp\":" << capability_metrics.last_success_timestamp
            << ",\"last_failure_timestamp\":" << capability_metrics.last_failure_timestamp
            << ",\"last_error_code\":" << capability_metrics.last_error_code << "}}";
    }
    oss << "]}";
    return build_management_success_response(request, "success", oss.str());
}

std::string AiHttpServer::build_runtime_status_response(const HttpRequestContext& request) const {
    const auto license_status = license_manager_->get_status();
    const auto capabilities = runtime_->list_capabilities();
    const auto metrics = runtime_->list_metrics();
    std::size_t total_pool_size = 0;
    std::size_t total_busy_count = 0;
    std::size_t ready_pool_count = 0;
    std::size_t draining_pool_count = 0;
    std::size_t total_request_count = 0;
    std::size_t total_success_count = 0;
    std::size_t total_failure_count = 0;
    std::size_t total_busy_reject_count = 0;
    double total_cost_ms = 0.0;
    for (const auto& capability : capabilities) {
        total_pool_size += capability.pool_size;
        total_busy_count += capability.busy_count;
        if (capability.ready) {
            ++ready_pool_count;
        }
        if (capability.draining) {
            ++draining_pool_count;
        }
    }
    for (const auto& metric : metrics) {
        total_request_count += metric.request_count;
        total_success_count += metric.success_count;
        total_failure_count += metric.failure_count;
        total_busy_reject_count += metric.busy_reject_count;
        total_cost_ms += metric.total_cost_ms;
    }
    std::ostringstream oss;
    oss << "\"running\":" << (running_ ? "true" : "false") << ",";
    oss << "\"host\":\"" << escape_json_string(config_.host) << "\",";
    oss << "\"port\":" << config_.port << ",";
    oss << "\"capability_count\":" << runtime_->capability_count() << ",";
    oss << "\"pool_size\":" << total_pool_size << ",";
    oss << "\"busy_count\":" << total_busy_count << ",";
    oss << "\"ready_pool_count\":" << ready_pool_count << ",";
    oss << "\"draining_pool_count\":" << draining_pool_count << ",";
    oss << "\"metrics\":{\"request_count\":" << total_request_count
        << ",\"success_count\":" << total_success_count
        << ",\"failure_count\":" << total_failure_count
        << ",\"busy_reject_count\":" << total_busy_reject_count
        << ",\"total_cost_ms\":" << total_cost_ms << ",\"capabilities\":[";
    for (std::size_t i = 0; i < metrics.size(); ++i) {
        if (i > 0) {
            oss << ',';
        }
        const auto& metric = metrics[i];
        oss << "{\"capability_id\":\"" << escape_json_string(metric.capability_id)
            << "\",\"request_count\":" << metric.request_count
            << ",\"success_count\":" << metric.success_count
            << ",\"failure_count\":" << metric.failure_count
            << ",\"busy_reject_count\":" << metric.busy_reject_count
            << ",\"total_cost_ms\":" << metric.total_cost_ms
            << ",\"avg_cost_ms\":" << metric.avg_cost_ms
            << ",\"last_request_timestamp\":" << metric.last_request_timestamp
            << ",\"last_success_timestamp\":" << metric.last_success_timestamp
            << ",\"last_failure_timestamp\":" << metric.last_failure_timestamp
            << ",\"last_error_code\":" << metric.last_error_code << "}";
    }
    oss << "]},";
    oss << "\"license_valid\":" << (license_status.valid ? "true" : "false") << ",";
    oss << "\"capability_ids\":[";
    for (std::size_t i = 0; i < capabilities.size(); ++i) {
        if (i > 0) {
            oss << ',';
        }
        oss << "\"" << escape_json_string(capabilities[i].capability_id) << "\"";
    }
    oss << "],";
    oss << "\"license_type\":\"" << escape_json_string(license_status.license_type) << "\",";
    oss << "\"expires_at\":\"" << escape_json_string(license_status.expires_at) << "\",";
    oss << "\"licensed_capabilities\":[";
    for (std::size_t i = 0; i < license_status.licensed_capabilities.size(); ++i) {
        if (i > 0) {
            oss << ',';
        }
        oss << "\"" << escape_json_string(license_status.licensed_capabilities[i]) << "\"";
    }
    oss << "],";
    oss << "\"capability_details\":[";
    for (std::size_t i = 0; i < capabilities.size(); ++i) {
        if (i > 0) {
            oss << ',';
        }
        const auto& capability = capabilities[i];
        oss << "{\"capability_id\":\"" << escape_json_string(capability.capability_id)
            << "\",\"status\":\"" << escape_json_string(capability.status)
            << "\",\"device\":\"" << escape_json_string(capability.device)
            << "\",\"model_dir\":\"" << escape_json_string(capability.model_dir)
            << "\",\"pool_size\":" << capability.pool_size
            << ",\"busy_count\":" << capability.busy_count
            << ",\"ready\":" << (capability.ready ? "true" : "false")
            << ",\"draining\":" << (capability.draining ? "true" : "false") << "}";
    }
    oss << "]";
    return build_management_success_response(request, "success", "{" + oss.str() + "}");
}

std::string AiHttpServer::build_runtime_diagnostics_response(const HttpRequestContext& request) const {
    const auto diagnostics = runtime_->get_diagnostics();
    const auto license_status = license_manager_->get_status();
    const auto& paths = app_paths();

    std::size_t total_request_count = 0;
    std::size_t total_success_count = 0;
    std::size_t total_failure_count = 0;
    std::size_t total_busy_reject_count = 0;
    for (const auto& metric : diagnostics.metrics) {
        total_request_count += metric.request_count;
        total_success_count += metric.success_count;
        total_failure_count += metric.failure_count;
        total_busy_reject_count += metric.busy_reject_count;
    }

    std::ostringstream oss;
    oss << '{';
    oss << "\"server\":{"
        << "\"running\":" << (running_ ? "true" : "false")
        << ",\"host\":\"" << escape_json_string(config_.host) << "\""
        << ",\"port\":" << config_.port
        << ",\"workers\":" << config_.workers
        << ",\"request_timeout_ms\":" << config_.request_timeout_ms
        << ",\"max_body_size_mb\":" << config_.max_body_size_mb
        << ",\"max_video_size_mb\":" << config_.max_video_size_mb
        << "},";
    oss << "\"paths\":{"
        << "\"platform_config\":\"" << escape_json_string(paths.platform_config) << "\""
        << ",\"plugins_registry\":\"" << escape_json_string(paths.plugins_registry) << "\""
        << ",\"license_audit_log\":\"" << escape_json_string(paths.license_audit_log) << "\""
        << ",\"runtime_audit_log\":\"" << escape_json_string(paths.runtime_audit_log) << "\""
        << "},";
    oss << "\"runtime\":{"
        << "\"initialized\":" << (diagnostics.initialized ? "true" : "false")
        << ",\"capability_count\":" << diagnostics.capability_count
        << ",\"ready_capability_count\":" << diagnostics.ready_capability_count
        << ",\"draining_capability_count\":" << diagnostics.draining_capability_count
        << ",\"total_pool_size\":" << diagnostics.total_pool_size
        << ",\"total_busy_count\":" << diagnostics.total_busy_count
        << ",\"metrics_summary\":{"
        << "\"request_count\":" << total_request_count
        << ",\"success_count\":" << total_success_count
        << ",\"failure_count\":" << total_failure_count
        << ",\"busy_reject_count\":" << total_busy_reject_count
        << "},"
        << "\"plugin_load\":{"
        << "\"registry_opened\":" << (diagnostics.plugin_load.registry_opened ? "true" : "false")
        << ",\"registry_path\":\"" << escape_json_string(diagnostics.plugin_load.registry_path) << "\""
        << ",\"last_error\":\"" << escape_json_string(diagnostics.plugin_load.last_error) << "\""
        << ",\"configured_count\":" << diagnostics.plugin_load.configured_count
        << ",\"loaded_count\":" << diagnostics.plugin_load.loaded_count
        << ",\"loaded_capability_ids\":[";
    for (std::size_t i = 0; i < diagnostics.plugin_load.loaded_capability_ids.size(); ++i) {
        if (i > 0) {
            oss << ',';
        }
        oss << "\"" << escape_json_string(diagnostics.plugin_load.loaded_capability_ids[i]) << "\"";
    }
    oss << "],\"failures\":[";
    for (std::size_t i = 0; i < diagnostics.plugin_load.failures.size(); ++i) {
        if (i > 0) {
            oss << ',';
        }
        const auto& failure = diagnostics.plugin_load.failures[i];
        oss << "{\"capability_id\":\"" << escape_json_string(failure.capability_id)
            << "\",\"library_path\":\"" << escape_json_string(failure.library_path)
            << "\",\"model_dir\":\"" << escape_json_string(failure.model_dir)
            << "\",\"stage\":\"" << escape_json_string(failure.stage)
            << "\",\"message\":\"" << escape_json_string(failure.message) << "\"}";
    }
    oss << "]},\"capabilities\":[";
    for (std::size_t i = 0; i < diagnostics.capabilities.size(); ++i) {
        if (i > 0) {
            oss << ',';
        }
        const auto& capability = diagnostics.capabilities[i];
        oss << "{\"capability_id\":\"" << escape_json_string(capability.capability_id)
            << "\",\"status\":\"" << escape_json_string(capability.status)
            << "\",\"library_path\":\"" << escape_json_string(capability.library_path)
            << "\",\"model_dir\":\"" << escape_json_string(capability.model_dir)
            << "\",\"configured_device\":\"" << escape_json_string(capability.configured_device)
            << "\",\"device\":\"" << escape_json_string(capability.device)
            << "\",\"pool_size\":" << capability.pool_size
            << ",\"busy_count\":" << capability.busy_count
            << ",\"ready\":" << (capability.ready ? "true" : "false")
            << ",\"draining\":" << (capability.draining ? "true" : "false")
            << '}';
    }
    oss << "]},";
    oss << "\"license\":{"
        << "\"valid\":" << (license_status.valid ? "true" : "false")
        << ",\"failure_reason\":\"" << escape_json_string(license_status.failure_reason) << "\""
        << ",\"failure_detail\":\"" << escape_json_string(license_status.failure_detail) << "\""
        << ",\"license_type\":\"" << escape_json_string(license_status.license_type) << "\""
        << ",\"expires_at\":\"" << escape_json_string(license_status.expires_at) << "\""
        << ",\"allow_reload\":" << (license_status.allow_reload ? "true" : "false")
        << ",\"allow_admin_api\":" << (license_status.allow_admin_api ? "true" : "false")
        << '}';
    oss << '}';

    return build_management_success_response(request, "success", oss.str());
}

std::string AiHttpServer::build_runtime_metrics_response(const HttpRequestContext& request) const {
    const auto metrics = runtime_->list_metrics();
    std::size_t total_request_count = 0;
    std::size_t total_success_count = 0;
    std::size_t total_failure_count = 0;
    std::size_t total_busy_reject_count = 0;
    double total_cost_ms = 0.0;

    for (const auto& metric : metrics) {
        total_request_count += metric.request_count;
        total_success_count += metric.success_count;
        total_failure_count += metric.failure_count;
        total_busy_reject_count += metric.busy_reject_count;
        total_cost_ms += metric.total_cost_ms;
    }

    std::ostringstream oss;
    oss << "{\"request_count\":" << total_request_count
        << ",\"success_count\":" << total_success_count
        << ",\"failure_count\":" << total_failure_count
        << ",\"busy_reject_count\":" << total_busy_reject_count
        << ",\"total_cost_ms\":" << total_cost_ms
        << ",\"capabilities\":[";

    for (std::size_t i = 0; i < metrics.size(); ++i) {
        if (i > 0) {
            oss << ',';
        }
        const auto& metric = metrics[i];
        oss << "{\"capability_id\":\"" << escape_json_string(metric.capability_id)
            << "\",\"request_count\":" << metric.request_count
            << ",\"success_count\":" << metric.success_count
            << ",\"failure_count\":" << metric.failure_count
            << ",\"busy_reject_count\":" << metric.busy_reject_count
            << ",\"total_cost_ms\":" << metric.total_cost_ms
            << ",\"avg_cost_ms\":" << metric.avg_cost_ms
            << ",\"last_request_timestamp\":" << metric.last_request_timestamp
            << ",\"last_success_timestamp\":" << metric.last_success_timestamp
            << ",\"last_failure_timestamp\":" << metric.last_failure_timestamp
            << ",\"last_error_code\":" << metric.last_error_code << "}";
    }

    oss << "]}";
    return build_management_success_response(request, "success", oss.str());
}

std::string AiHttpServer::build_error_response(int code, const std::string& message) const {
    std::ostringstream oss;
    oss << "{\"code\":" << code << ",\"message\":\"" << escape_json_string(message) << "\",\"data\":null,\"api_version\":\"v1\"}";
    return oss.str();
}

std::string AiHttpServer::build_infer_error_response(const HttpRequestContext& request, const InferRequest& infer_request, int code, const std::string& message, const LicenseStatusInfo* license_status) const {
    std::ostringstream data_json;
    data_json << "{\"request_id\":\"" << escape_json_string(infer_request.request_id) << "\""
              << ",\"capability_id\":\"" << escape_json_string(infer_request.capability_id) << "\"";
    if (license_status != nullptr) {
        data_json << ",\"license\":{";
        data_json << "\"valid\":" << (license_status->valid ? "true" : "false")
                  << ",\"allow_admin_api\":" << (license_status->allow_admin_api ? "true" : "false")
                  << ",\"allow_reload\":" << (license_status->allow_reload ? "true" : "false")
                  << ",\"allow_test_page\":" << (license_status->allow_test_page ? "true" : "false")
                  << ",\"failure_reason\":\"" << escape_json_string(license_status->failure_reason) << "\""
                  << ",\"failure_detail\":\"" << escape_json_string(license_status->failure_detail) << "\"";
        data_json << '}';
    }
    data_json << '}';

    std::ostringstream oss;
    oss << '{'
        << "\"code\":" << code
        << ",\"message\":\"" << escape_json_string(message) << "\""
        << ",\"data\":" << data_json.str() << ','
        << build_management_meta_json(request)
        << ",\"api_version\":\"v1\""
        << '}';
    return oss.str();
}

std::string AiHttpServer::build_method_not_allowed_response(const HttpRequestContext& request, const std::string& allow_method) const {
    std::ostringstream oss;
    oss << '{'
        << "\"code\":-405"
        << ",\"message\":\"method not allowed\""
        << ",\"data\":null"
        << ",\"allow\":\"" << escape_json_string(allow_method) << "\""
        << ','
        << build_management_meta_json(request)
        << ",\"api_version\":\"v1\""
        << '}';
    return oss.str();
}

std::string AiHttpServer::build_management_error_response(const HttpRequestContext& request, int code, const std::string& message, const LicenseStatusInfo* license_status, const std::string& data_json) const {
    std::ostringstream oss;
    std::string resolved_data_json = data_json;
    if (license_status != nullptr) {
        std::ostringstream license_json;
        license_json << "{\"valid\":" << (license_status->valid ? "true" : "false")
                     << ",\"allow_admin_api\":" << (license_status->allow_admin_api ? "true" : "false")
                     << ",\"allow_reload\":" << (license_status->allow_reload ? "true" : "false")
                     << ",\"license_failure_reason\":\"" << escape_json_string(license_status->failure_reason) << "\"";
        if (!license_status->failure_detail.empty()) {
            license_json << ",\"license_failure_detail\":\"" << escape_json_string(license_status->failure_detail) << "\"";
        }
        license_json << '}';
        resolved_data_json = license_json.str();
    }

    oss << '{'
        << "\"code\":" << code
        << ",\"message\":\"" << escape_json_string(message) << "\""
        << ",\"data\":" << resolved_data_json << ','
        << build_management_meta_json(request)
        << ",\"api_version\":\"v1\""
        << '}';
    return oss.str();
}

std::string AiHttpServer::build_management_success_response(const HttpRequestContext& request, const std::string& message, const std::string& data_json) const {
    std::ostringstream oss;
    oss << "{\"code\":0,\"message\":\"" << escape_json_string(message) << "\",\"data\":" << data_json << ",";
    oss << build_management_meta_json(request) << ",\"api_version\":\"v1\"}";
    return oss.str();
}

std::string AiHttpServer::build_management_meta_json(const HttpRequestContext& request) const {
    std::ostringstream oss;
    oss << "\"request_id\":\"" << escape_json_string(request.request_id) << "\",";
    oss << "\"endpoint\":\"" << escape_json_string(request.endpoint) << "\",";
    oss << "\"timestamp\":" << request.timestamp;
    return oss.str();
}

std::string AiHttpServer::build_license_status_response(const HttpRequestContext& request) const {
    const auto status = license_manager_->get_status();
    std::ostringstream oss;
    oss << "\"valid\":" << (status.valid ? "true" : "false") << ",";
    oss << "\"effective_now\":" << (status.effective_now ? "true" : "false") << ",";
    oss << "\"in_grace_period\":" << (status.in_grace_period ? "true" : "false") << ",";
    oss << "\"expired\":" << (status.expired ? "true" : "false") << ",";
    oss << "\"failure_reason\":\"" << escape_json_string(status.failure_reason) << "\",";
    oss << "\"failure_detail\":\"" << escape_json_string(status.failure_detail) << "\",";
    oss << "\"version\":\"" << escape_json_string(status.version) << "\",";
    oss << "\"license_type\":\"" << escape_json_string(status.license_type) << "\",";
    oss << "\"customer_id\":\"" << escape_json_string(status.customer_id) << "\",";
    oss << "\"customer_name\":\"" << escape_json_string(status.customer_name) << "\",";
    oss << "\"issued_at\":\"" << escape_json_string(status.issued_at) << "\",";
    oss << "\"effective_from\":\"" << escape_json_string(status.effective_from) << "\",";
    oss << "\"expires_at\":\"" << escape_json_string(status.expires_at) << "\",";
    oss << "\"grace_period_hours\":" << status.grace_period_hours << ",";
    oss << "\"allow_reload\":" << (status.allow_reload ? "true" : "false") << ",";
    oss << "\"allow_admin_api\":" << (status.allow_admin_api ? "true" : "false") << ",";
    oss << "\"allow_test_page\":" << (status.allow_test_page ? "true" : "false") << ",";
    oss << "\"licensed_capabilities\":[";
    for (std::size_t i = 0; i < status.licensed_capabilities.size(); ++i) {
        if (i > 0) {
            oss << ',';
        }
        oss << "\"" << escape_json_string(status.licensed_capabilities[i]) << "\"";
    }
    oss << "],";
    oss << "\"denied_capabilities\":[";
    for (std::size_t i = 0; i < status.denied_capabilities.size(); ++i) {
        if (i > 0) {
            oss << ',';
        }
        oss << "\"" << escape_json_string(status.denied_capabilities[i]) << "\"";
    }
    oss << "]";
    return build_management_success_response(request, "success", "{" + oss.str() + "}");
}

}
