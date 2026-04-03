#ifndef AI_CAPABILITY_PLATFORM_APPS_AI_PROD_CPP_HTTP_SERVER_H
#define AI_CAPABILITY_PLATFORM_APPS_AI_PROD_CPP_HTTP_SERVER_H

#include "capability_catalog.h"
#include "backend_client.h"
#include "instance_pool.h"
#include "proxy_config.h"
#include "runtime_snapshot_manager.h"

#include <cpp-httplib/httplib.h>

#include <map>
#include <memory>
#include <mutex>
#include <optional>

class AiProdHttpServer {
public:
    explicit AiProdHttpServer(const ProxyConfig& config);

    bool Start();
    void Stop();

private:
    static httplib::Headers BuildForwardHeaders(const httplib::Request& request);
    void ApplyBackendResponse(const BackendResponse& backend_response, httplib::Response& response) const;
    void ApplySnapshotOrBackendResponse(
        const SnapshotResponse& snapshot_response,
        const httplib::Request& request,
        httplib::Response& response) const;
    bool RefreshCatalogAndPools();
    nlohmann::json BuildCatalogPayload(bool snapshot_ready) const;
    void HandleInferRequest(const httplib::Request& request, httplib::Response& response);
    std::shared_ptr<InstancePool> GetInstancePool(const std::string& capability_name) const;
    void RegisterRoutes();

    ProxyConfig config;
    CapabilityCatalog capabilityCatalog;
    AiProdBackendClient backendClient;
    std::map<std::string, std::shared_ptr<InstancePool>> instancePools;
    RuntimeSnapshotManager snapshotManager;
    mutable std::mutex runtimeStateMutex;
    int activeCatalogRevisionId = 0;
    std::unique_ptr<httplib::Server> server;
};

#endif
