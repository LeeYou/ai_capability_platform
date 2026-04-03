#ifndef AI_CAPABILITY_PLATFORM_APPS_AI_PROD_CPP_BACKEND_CLIENT_H
#define AI_CAPABILITY_PLATFORM_APPS_AI_PROD_CPP_BACKEND_CLIENT_H

#include "proxy_config.h"

#include <cpp-httplib/httplib.h>

#include <string>

struct BackendResponse {
    int status = 502;
    std::string body;
    std::string content_type = "application/json; charset=utf-8";
    bool ok = false;
};

class AiProdBackendClient {
public:
    explicit AiProdBackendClient(const ProxyConfig& config);

    BackendResponse ForwardGet(const std::string& path, const httplib::Headers& headers) const;
    BackendResponse ForwardPost(
        const std::string& path,
        const std::string& body,
        const std::string& content_type,
        const httplib::Headers& headers) const;
    BackendResponse ForwardRollback(
        const std::string& body,
        const std::string& content_type,
        const httplib::Headers& headers) const;

    static std::string NormalizeRollbackBody(const std::string& body);

private:
    httplib::Client BuildClient() const;
    static BackendResponse BuildFailureResponse(const std::string& message);
    static BackendResponse BuildSuccessResponse(const httplib::Result& result);

    ProxyConfig config;
};

#endif
