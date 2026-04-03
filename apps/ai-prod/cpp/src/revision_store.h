#ifndef AI_CAPABILITY_PLATFORM_APPS_AI_PROD_CPP_REVISION_STORE_H
#define AI_CAPABILITY_PLATFORM_APPS_AI_PROD_CPP_REVISION_STORE_H

#include <nlohmann/json.hpp>

#include <optional>
#include <string>

struct RuntimeRevisionRecord {
    int id = 0;
    std::string revision_token;
    std::string action;
    std::string status;
    bool license_valid = false;
    nlohmann::json capability_names = nlohmann::json::array();
    nlohmann::json source_summary = nlohmann::json::object();
    nlohmann::json detail = nlohmann::json::object();
    std::optional<int> rollback_of_revision_id;
    std::string created_at;
};

struct RuntimeOperationRecord {
    int id = 0;
    std::string action;
    std::string status;
    nlohmann::json detail = nlohmann::json::object();
    std::optional<int> revision_id;
    std::string created_at;
};

class RevisionStore {
public:
    explicit RevisionStore(std::string database_path);

    bool EnsureSchema(std::string* error_message);
    std::optional<RuntimeRevisionRecord> CreateRevision(
        const std::string& revision_token,
        const std::string& action,
        const std::string& status,
        const nlohmann::json& source_summary,
        const nlohmann::json& capability_names,
        bool license_valid,
        const nlohmann::json& detail,
        const std::optional<int>& rollback_of_revision_id,
        std::string* error_message);
    std::optional<RuntimeOperationRecord> CreateOperation(
        const std::string& action,
        const std::string& status,
        const nlohmann::json& detail,
        const std::optional<int>& revision_id,
        std::string* error_message);
    std::optional<RuntimeRevisionRecord> GetRevision(int revision_id, std::string* error_message);

private:
    std::string databasePath;
};

#endif
