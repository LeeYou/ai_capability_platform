#ifndef AI_CAPABILITY_PLATFORM_APPS_AI_PROD_CPP_AUDIT_LOGGER_H
#define AI_CAPABILITY_PLATFORM_APPS_AI_PROD_CPP_AUDIT_LOGGER_H

#include <nlohmann/json.hpp>

#include <mutex>
#include <string>

struct AuditLogEntry {
    std::string action;
    std::string entity_type;
    std::string entity_id;
    std::string status;
    std::string request_id;
    std::string correlation_id;
    double elapsed_ms = -1.0;
    std::string error_message;
    nlohmann::json detail = nlohmann::json::object();
};

class AuditLogger {
public:
    explicit AuditLogger(std::string log_path_value);

    void Append(const AuditLogEntry& entry);

private:
    std::string logPath;
    std::mutex mutex;
};

#endif
