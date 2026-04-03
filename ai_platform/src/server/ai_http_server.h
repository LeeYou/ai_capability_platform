#ifndef AI_PLATFORM_AI_HTTP_SERVER_H
#define AI_PLATFORM_AI_HTTP_SERVER_H

#include "ai_platform/ai_types.h"

#include <cpp-httplib/httplib.h>

#include <memory>
#include <unordered_map>
#include <string>
#include <vector>

#include <atomic>

namespace ai_platform {

class AiRuntime;
class LicenseManager;
struct LicenseStatusInfo;

struct ServerConfig {
    std::string host = "0.0.0.0";
    int port = 26000;
    int workers = 4;
    int request_timeout_ms = 30000;
    int max_body_size_mb = 50;
    int max_video_size_mb = 200;
    std::string admin_token = "demo-admin-token";
};

class AiHttpServer {
public:
    bool initialize(const ServerConfig& config, AiRuntime* runtime, LicenseManager* license_manager);
    bool start();
    void stop();

private:
    struct HttpRequestContext {
        std::string method;
        std::string path;
        std::string version;
        std::string raw_request;
        std::string body;
        std::string content_type;
        std::unordered_map<std::string, std::string> headers;
        std::string request_id;
        std::string endpoint;
        std::int64_t timestamp = 0;
    };

    struct InferRequestBuildResult {
        InferRequest request;
        int error_code = 0;
        std::string error_message;
        bool ok = false;
    };

    struct HttpResponseContext {
        std::string status = "200 OK";
        std::string body;
        std::string content_type = "application/json; charset=utf-8";
        std::vector<std::string> headers;
    };

    std::string build_health_response(const HttpRequestContext& request) const;
    std::string build_test_page_response(const HttpRequestContext& request) const;
    std::string build_capabilities_response(const HttpRequestContext& request) const;
    std::string build_license_status_response(const HttpRequestContext& request) const;
    std::string build_runtime_metrics_response(const HttpRequestContext& request) const;
    std::string build_runtime_status_response(const HttpRequestContext& request) const;
    std::string build_runtime_diagnostics_response(const HttpRequestContext& request) const;
    std::string build_error_response(int code, const std::string& message) const;
    std::string build_infer_error_response(const HttpRequestContext& request, const InferRequest& infer_request, int code, const std::string& message, const LicenseStatusInfo* license_status = nullptr) const;
    std::string build_method_not_allowed_response(const HttpRequestContext& request, const std::string& allow_method) const;
    std::string build_management_error_response(const HttpRequestContext& request, int code, const std::string& message, const LicenseStatusInfo* license_status = nullptr, const std::string& data_json = "null") const;
    std::string build_management_success_response(const HttpRequestContext& request, const std::string& message, const std::string& data_json) const;
    std::string build_management_meta_json(const HttpRequestContext& request) const;
    bool verify_admin_token(const HttpRequestContext& request) const;
    HttpRequestContext build_request_context(const std::string& method, const std::string& path, const std::string& body, const std::string& content_type, const std::unordered_map<std::string, std::string>& headers) const;
    HttpResponseContext route_request(const HttpRequestContext& request) const;
    InferRequestBuildResult build_infer_request(const HttpRequestContext& request) const;

    ServerConfig config_;
    AiRuntime* runtime_ = nullptr;
    LicenseManager* license_manager_ = nullptr;
    std::atomic<bool> running_{false};
    std::unique_ptr<::httplib::Server> server_;
};

}

#endif
