#ifndef AI_CAPABILITY_PLATFORM_APPS_AI_PROD_CPP_HTTP_SERVER_H
#define AI_CAPABILITY_PLATFORM_APPS_AI_PROD_CPP_HTTP_SERVER_H

#include "capability_catalog.h"
#include "instance_pool.h"
#include "license_manager.h"
#include "plugin_executor.h"
#include "proxy_config.h"
#include "request_tracker.h"
#include "revision_store.h"
#include "runtime_resource_scanner.h"
#include "runtime_state_machine.h"
#include "runtime_snapshot_manager.h"

#include <cpp-httplib/httplib.h>

#include <chrono>
#include <deque>
#include <map>
#include <memory>
#include <mutex>
#include <optional>
#include <set>
#include <string>
#include <vector>

class AiProdHttpServer {
public:
    explicit AiProdHttpServer(const ProxyConfig& config);

    bool Start();
    void Stop();
    void RecordEndpointMetric(const std::string& endpoint, int status_code, std::chrono::steady_clock::time_point started_at);

private:
    struct EndpointMetrics {
        int total_requests = 0;
        int successful_requests = 0;
        int failed_requests = 0;
        int last_status_code = 0;
        double total_latency_ms = 0.0;
        double min_latency_ms = 0.0;
        double max_latency_ms = 0.0;
        std::string last_error_at_utc;
        std::deque<int> recent_latency_ms;
        std::multiset<int> recent_latency_sorted;
        std::map<int, int> status_code_counts;
    };

    bool RefreshCatalogAndPools(bool force_rebuild = false);
    bool RefreshCatalogAndPoolsWithRetry(int attempts, std::chrono::milliseconds wait_interval, bool force_rebuild);
    nlohmann::json BuildCatalogPayload(bool snapshot_ready) const;
    nlohmann::json BuildMetricsPayload(bool snapshot_ready) const;
    void HandleInferRequest(const httplib::Request& request, httplib::Response& response);
    void HandleAdminTransitionRequest(
        const httplib::Request& request,
        httplib::Response& response,
        bool rollback);
    void HandleLicenseStatusRequest(const httplib::Request& request, httplib::Response& response);
    void HandleLicenseReloadRequest(const httplib::Request& request, httplib::Response& response);
    bool EnsureRuntimeReady();
    bool BootstrapRuntime(std::string* error_message);
    std::optional<nlohmann::json> ExecuteRuntimeTransition(const std::string& action, std::optional<int> target_revision_id, std::string* error_message);
    void MarkRuntimeError(const std::string& error_message);
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
    std::map<std::string, std::shared_ptr<InstancePool>> instancePools;
    LicenseManager licenseManager;
    PluginExecutor pluginExecutor;
    std::shared_ptr<InFlightRequestTracker> requestTracker;
    RuntimeSnapshotManager snapshotManager;
    mutable std::mutex runtimeStateMutex;
    mutable std::mutex metricsMutex;
    std::mutex runtimeTransitionMutex;
    RuntimeStateMachine runtimeStateMachine;
    std::chrono::steady_clock::time_point startedAt;
    std::map<std::string, EndpointMetrics> endpointMetrics;
    int activeCatalogRevisionId = 0;
    std::unique_ptr<httplib::Server> server;
};

#endif
