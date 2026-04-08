#include "audit_logger.h"

#include <chrono>
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <sstream>
#include <utility>

namespace {

std::string CurrentCstIsoString() {
    const auto now = std::time(nullptr) + 8 * 60 * 60;
    std::tm cst_time{};
#ifdef _WIN32
    gmtime_s(&cst_time, &now);
#else
    gmtime_r(&now, &cst_time);
#endif
    std::ostringstream output;
    output << std::put_time(&cst_time, "%Y-%m-%dT%H:%M:%S") << "+08:00";
    return output.str();
}

}  // namespace

AuditLogger::AuditLogger(std::string log_path_value)
    : logPath(std::move(log_path_value)) {
}

void AuditLogger::Append(const AuditLogEntry& entry) {
    nlohmann::json detail = entry.detail.is_object() ? entry.detail : nlohmann::json::object();
    detail["status"] = entry.status.empty() ? nlohmann::json("ok") : nlohmann::json(entry.status);
    if (!entry.request_id.empty()) {
        detail["request_id"] = entry.request_id;
    }
    if (!entry.correlation_id.empty()) {
        detail["correlation_id"] = entry.correlation_id;
    }
    if (entry.elapsed_ms >= 0.0) {
        detail["elapsed_ms"] = entry.elapsed_ms;
    }
    if (!entry.error_message.empty()) {
        detail["error_message"] = entry.error_message;
    }

    const nlohmann::json payload = {
        {"happened_at_cst", CurrentCstIsoString()},
        {"action", entry.action},
        {"entity_type", entry.entity_type},
        {"entity_id", entry.entity_id},
        {"detail", detail},
    };

    std::lock_guard<std::mutex> guard(mutex);
    const std::filesystem::path log_path(logPath);
    if (!log_path.parent_path().empty()) {
        std::filesystem::create_directories(log_path.parent_path());
    }
    std::ofstream output(logPath, std::ios::app);
    if (!output.is_open()) {
        return;
    }
    output << payload.dump() << "\n";
}
