#ifndef AI_CAPABILITY_PLATFORM_APPS_AI_PROD_CPP_CAPABILITY_CATALOG_H
#define AI_CAPABILITY_PLATFORM_APPS_AI_PROD_CPP_CAPABILITY_CATALOG_H

#include <nlohmann/json.hpp>

#include <filesystem>
#include <mutex>
#include <optional>
#include <string>
#include <unordered_map>
#include <vector>

struct CapabilityCatalogEntry {
    std::string capability_name;
    std::string plugin_target;
    std::string model_version;
    std::string backend_type;
    std::string active_source;
    std::string device_mode;
    int pool_size = 0;
    int revision_id = 0;
};

class CapabilityCatalog {
public:
    explicit CapabilityCatalog(const std::string& snapshot_path);

    bool RefreshIfNeeded(int max_age_seconds);
    std::vector<CapabilityCatalogEntry> ListEntries() const;
    std::optional<CapabilityCatalogEntry> GetEntry(const std::string& capability_name) const;
    int GetRevisionId() const;

private:
    bool LoadSnapshotUnlocked(int max_age_seconds);
    bool ParseSnapshotUnlocked(const nlohmann::json& snapshot_json);
    bool SnapshotIsFresh(
        const std::filesystem::file_time_type& updated_at,
        int max_age_seconds) const;

    std::string snapshotPath;
    mutable std::mutex mutex;
    std::unordered_map<std::string, CapabilityCatalogEntry> entries;
    std::filesystem::file_time_type lastLoadedWriteTime;
    int revisionId = 0;
    bool hasLoadedSnapshot = false;
};

#endif
