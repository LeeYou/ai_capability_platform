#ifndef AI_CAPABILITY_PLATFORM_APPS_AI_PROD_CPP_HTTP_SERVER_H
#define AI_CAPABILITY_PLATFORM_APPS_AI_PROD_CPP_HTTP_SERVER_H

#include "capability_catalog.h"
#include "backend_client.h"
#include "instance_pool.h"
#include "license_manager.h"
#include "proxy_config.h"
#include "revision_store.h"
#include "runtime_resource_scanner.h"
#include "runtime_snapshot_manager.h"

#include <cpp-httplib/httplib.h>

#include <chrono>
#include <map>
#include <memory>
#include <mutex>
#include <optional>
#include <vector>

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
    bool RefreshCatalogAndPools(bool force_rebuild = false);
    bool RefreshCatalogAndPoolsWithRetry(int attempts, std::chrono::milliseconds wait_interval, bool force_rebuild);
    nlohmann::json BuildCatalogPayload(bool snapshot_ready) const;
    void HandleInferRequest(const httplib::Request& request, httplib::Response& response);
    void HandleAdminTransitionRequest(
        const httplib::Request& request,
        httplib::Response& response,
        bool rollback);
    void HandleLicenseStatusRequest(const httplib::Request& request, httplib::Response& response) const;
    void HandleLicenseReloadRequest(const httplib::Request& request, httplib::Response& response);
    std::optional<nlohmann::json> ExecuteRuntimeTransition(const std::string& action, std::optional<int> target_revision_id, std::string* error_message);
    std::shared_ptr<InstancePool> GetInstancePool(const std::string& capability_name) const;
    std::vector<std::shared_ptr<InstancePool>> ListInstancePools() const;
    static void BeginDrainOnPools(const std::vector<std::shared_ptr<InstancePool>>& pools);
    static void EndDrainOnPools(const std::vector<std::shared_ptr<InstancePool>>& pools);
    static bool WaitForPoolsIdle(
        const std::vector<std::shared_ptr<InstancePool>>& pools,
        std::chrono::milliseconds timeout);
    void RegisterRoutes();

    ProxyConfig config;
    CapabilityCatalog capabilityCatalog;
    AiProdBackendClient backendClient;
    std::map<std::string, std::shared_ptr<InstancePool>> instancePools;
    LicenseManager licenseManager;
    RuntimeSnapshotManager snapshotManager;
    mutable std::mutex runtimeStateMutex;
    int activeCatalogRevisionId = 0;
    std::unique_ptr<httplib::Server> server;
};

#endif
