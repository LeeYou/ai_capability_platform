#ifndef AI_CAPABILITY_PLATFORM_APPS_AI_PROD_CPP_HTTP_SERVER_H
#define AI_CAPABILITY_PLATFORM_APPS_AI_PROD_CPP_HTTP_SERVER_H

#include "backend_client.h"
#include "proxy_config.h"

#include <cpp-httplib/httplib.h>

#include <memory>

class AiProdHttpServer {
public:
    explicit AiProdHttpServer(const ProxyConfig& config);

    bool Start();
    void Stop();

private:
    static httplib::Headers BuildForwardHeaders(const httplib::Request& request);
    void ApplyBackendResponse(const BackendResponse& backend_response, httplib::Response& response) const;
    void RegisterRoutes();

    ProxyConfig config;
    AiProdBackendClient backendClient;
    std::unique_ptr<httplib::Server> server;
};

#endif
