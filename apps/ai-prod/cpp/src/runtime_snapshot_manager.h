#ifndef AI_CAPABILITY_PLATFORM_APPS_AI_PROD_CPP_RUNTIME_SNAPSHOT_MANAGER_H
#define AI_CAPABILITY_PLATFORM_APPS_AI_PROD_CPP_RUNTIME_SNAPSHOT_MANAGER_H

#include "proxy_config.h"

#include <nlohmann/json.hpp>

#include <filesystem>
#include <mutex>
#include <string>

struct SnapshotResponse {
    bool ok = false;
    std::string body;
};

class RuntimeSnapshotManager {
public:
    explicit RuntimeSnapshotManager(const ProxyConfig& config);

    SnapshotResponse BuildHealthResponse();
    SnapshotResponse BuildCapabilitiesResponse();
    SnapshotResponse BuildLicenseStatusResponse();
    bool WriteSnapshot(const nlohmann::json& payload);

private:
    bool EnsureSnapshotLoaded();
    SnapshotResponse BuildJsonResponse(const nlohmann::json& payload);
    bool SnapshotIsFresh(const std::filesystem::file_time_type& updated_at) const;

    std::string snapshotPath;
    int snapshotMaxAgeSeconds;
    std::mutex mutex;
    nlohmann::json snapshotJson;
    std::filesystem::file_time_type lastLoadedWriteTime;
    bool hasLoadedSnapshot = false;
};

#endif
