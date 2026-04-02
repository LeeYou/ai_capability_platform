#include "runtime_snapshot_manager.h"

#include <chrono>
#include <fstream>
#include <sstream>

namespace {

constexpr char kHealthStatus[] = "ok";

}

RuntimeSnapshotManager::RuntimeSnapshotManager(const ProxyConfig& config)
    : snapshotPath(config.runtime_snapshot_path),
      snapshotMaxAgeSeconds(config.snapshot_max_age_seconds) {
}

SnapshotResponse RuntimeSnapshotManager::BuildHealthResponse() {
    std::lock_guard<std::mutex> guard(mutex);
    if (!EnsureSnapshotLoaded()) {
        return {};
    }

    nlohmann::json payload = {
        {"status", kHealthStatus},
        {"service", snapshotJson.value("service_name", "ai-prod")},
        {"company_name", snapshotJson.value("company_name", "")},
        {"company_domain", snapshotJson.value("company_domain", "")},
        {"runtime_revision_id", snapshotJson.value("revision_id", 0)},
        {"capability_count", snapshotJson.value("capability_count", 0)},
        {"license_valid", snapshotJson["license_status"].value("valid", false)},
    };
    return BuildJsonResponse(payload);
}

SnapshotResponse RuntimeSnapshotManager::BuildCapabilitiesResponse() {
    std::lock_guard<std::mutex> guard(mutex);
    if (!EnsureSnapshotLoaded()) {
        return {};
    }

    nlohmann::json payload = {
        {"items", snapshotJson.value("capabilities", nlohmann::json::array())},
    };
    return BuildJsonResponse(payload);
}

SnapshotResponse RuntimeSnapshotManager::BuildLicenseStatusResponse() {
    std::lock_guard<std::mutex> guard(mutex);
    if (!EnsureSnapshotLoaded()) {
        return {};
    }

    return BuildJsonResponse(snapshotJson.value("license_status", nlohmann::json::object()));
}

bool RuntimeSnapshotManager::EnsureSnapshotLoaded() {
    try {
        const std::filesystem::path path(snapshotPath);
        if (!std::filesystem::exists(path)) {
            return false;
        }

        const auto write_time = std::filesystem::last_write_time(path);
        if (!SnapshotIsFresh(write_time)) {
            return false;
        }
        if (hasLoadedSnapshot && write_time == lastLoadedWriteTime) {
            return true;
        }

        std::ifstream input(path);
        if (!input.is_open()) {
            return false;
        }

        std::ostringstream buffer;
        buffer << input.rdbuf();
        nlohmann::json parsed = nlohmann::json::parse(buffer.str());
        if (!parsed.is_object() || !parsed.contains("license_status") || !parsed.contains("capabilities")) {
            return false;
        }
        snapshotJson = std::move(parsed);
        lastLoadedWriteTime = write_time;
        hasLoadedSnapshot = true;
        return true;
    } catch (const std::exception&) {
        return false;
    }
}

SnapshotResponse RuntimeSnapshotManager::BuildJsonResponse(const nlohmann::json& payload) {
    SnapshotResponse response;
    response.ok = true;
    response.body = payload.dump();
    return response;
}

bool RuntimeSnapshotManager::SnapshotIsFresh(const std::filesystem::file_time_type& updated_at) const {
    const auto now = std::filesystem::file_time_type::clock::now();
    const auto age = now - updated_at;
    return age <= std::chrono::seconds(snapshotMaxAgeSeconds);
}
