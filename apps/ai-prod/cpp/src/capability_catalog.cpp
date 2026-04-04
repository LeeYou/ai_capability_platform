#include "capability_catalog.h"

#include <algorithm>
#include <chrono>
#include <fstream>
#include <sstream>
#include <utility>

CapabilityCatalog::CapabilityCatalog(const std::string& snapshot_path)
    : snapshotPath(snapshot_path) {
}

bool CapabilityCatalog::RefreshIfNeeded(int max_age_seconds) {
    std::lock_guard<std::mutex> guard(mutex);
    return LoadSnapshotUnlocked(max_age_seconds);
}

std::vector<CapabilityCatalogEntry> CapabilityCatalog::ListEntries() const {
    std::lock_guard<std::mutex> guard(mutex);
    std::vector<CapabilityCatalogEntry> items;
    items.reserve(entries.size());
    for (const auto& item : entries) {
        items.push_back(item.second);
    }
    std::sort(
        items.begin(),
        items.end(),
        [](const CapabilityCatalogEntry& left, const CapabilityCatalogEntry& right) {
            return left.capability_name < right.capability_name;
        });
    return items;
}

std::optional<CapabilityCatalogEntry> CapabilityCatalog::GetEntry(const std::string& capability_name) const {
    std::lock_guard<std::mutex> guard(mutex);
    const auto found = entries.find(capability_name);
    if (found == entries.end()) {
        return std::nullopt;
    }
    return found->second;
}

int CapabilityCatalog::GetRevisionId() const {
    std::lock_guard<std::mutex> guard(mutex);
    return revisionId;
}

bool CapabilityCatalog::LoadSnapshotUnlocked(int max_age_seconds) {
    try {
        const std::filesystem::path path(snapshotPath);
        if (!std::filesystem::exists(path)) {
            return false;
        }

        const auto write_time = std::filesystem::last_write_time(path);
        if (!SnapshotIsFresh(write_time, max_age_seconds)) {
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
        const nlohmann::json snapshot_json = nlohmann::json::parse(buffer.str());
        if (!ParseSnapshotUnlocked(snapshot_json)) {
            return false;
        }
        lastLoadedWriteTime = write_time;
        hasLoadedSnapshot = true;
        return true;
    } catch (const std::exception&) {
        return false;
    }
}

bool CapabilityCatalog::ParseSnapshotUnlocked(const nlohmann::json& snapshot_json) {
    if (!snapshot_json.is_object() || !snapshot_json.contains("capabilities") ||
        !snapshot_json["capabilities"].is_array()) {
        return false;
    }

    std::unordered_map<std::string, CapabilityCatalogEntry> next_entries;
    for (const auto& item : snapshot_json["capabilities"]) {
        if (!item.is_object()) {
            return false;
        }
        const std::string capability_name = item.value("capability_name", "");
        if (capability_name.empty()) {
            return false;
        }
        next_entries.emplace(
            capability_name,
            CapabilityCatalogEntry{
                capability_name,
                item.value("plugin_target", ""),
                item.value("model_version", ""),
                item.value("backend_type", ""),
                item.value("active_source", ""),
                item.value("device_mode", "cpu"),
                item.value("model_root", ""),
                item.value("binary_path", ""),
                item.value("pool_size", 0),
                item.value("max_batch_size", 1),
                std::max(0, item.value("queue_wait_timeout_ms", 0)),
                std::max(0, item.value("max_pending_request_count", 0)),
                item.value("revision_id", snapshot_json.value("revision_id", 0)),
            });
    }

    entries = std::move(next_entries);
    revisionId = snapshot_json.value("revision_id", 0);
    return true;
}

bool CapabilityCatalog::SnapshotIsFresh(
    const std::filesystem::file_time_type& updated_at,
    int max_age_seconds) const {
    const auto now = std::filesystem::file_time_type::clock::now();
    const auto age = now - updated_at;
    return age <= std::chrono::seconds(max_age_seconds);
}
