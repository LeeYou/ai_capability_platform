#include "revision_store.h"

#include <sqlite3.h>

#include <filesystem>
#include <memory>

namespace {

using SqlitePtr = std::unique_ptr<sqlite3, decltype(&sqlite3_close)>;
using StatementPtr = std::unique_ptr<sqlite3_stmt, decltype(&sqlite3_finalize)>;

SqlitePtr OpenDatabase(const std::string& database_path, std::string* error_message) {
    const auto path = std::filesystem::path(database_path);
    if (!path.parent_path().empty()) {
        std::filesystem::create_directories(path.parent_path());
    }
    sqlite3* raw_db = nullptr;
    if (sqlite3_open(database_path.c_str(), &raw_db) != SQLITE_OK) {
        if (error_message != nullptr) {
            *error_message = raw_db != nullptr ? sqlite3_errmsg(raw_db) : "打开数据库失败。";
        }
        if (raw_db != nullptr) {
            sqlite3_close(raw_db);
        }
        return {nullptr, sqlite3_close};
    }
    return SqlitePtr(raw_db, sqlite3_close);
}

bool Execute(sqlite3* db, const std::string& sql, std::string* error_message) {
    char* raw_error = nullptr;
    const int rc = sqlite3_exec(db, sql.c_str(), nullptr, nullptr, &raw_error);
    if (rc == SQLITE_OK) {
        return true;
    }
    if (error_message != nullptr) {
        *error_message = raw_error != nullptr ? raw_error : sqlite3_errmsg(db);
    }
    sqlite3_free(raw_error);
    return false;
}

StatementPtr Prepare(sqlite3* db, const std::string& sql, std::string* error_message) {
    sqlite3_stmt* raw_stmt = nullptr;
    const int rc = sqlite3_prepare_v2(db, sql.c_str(), -1, &raw_stmt, nullptr);
    if (rc != SQLITE_OK) {
        if (error_message != nullptr) {
            *error_message = sqlite3_errmsg(db);
        }
        return {nullptr, sqlite3_finalize};
    }
    return StatementPtr(raw_stmt, sqlite3_finalize);
}

bool BindText(sqlite3_stmt* stmt, int index, const std::string& value) {
    return sqlite3_bind_text(stmt, index, value.c_str(), -1, SQLITE_TRANSIENT) == SQLITE_OK;
}

std::optional<nlohmann::json> ParseJsonColumn(const unsigned char* text_value) {
    if (text_value == nullptr) {
        return nlohmann::json::object();
    }
    try {
        return nlohmann::json::parse(reinterpret_cast<const char*>(text_value));
    } catch (const std::exception&) {
        return std::nullopt;
    }
}

std::optional<RuntimeRevisionRecord> ReadRevisionRow(sqlite3_stmt* stmt) {
    const auto capability_names = ParseJsonColumn(sqlite3_column_text(stmt, 5));
    const auto source_summary = ParseJsonColumn(sqlite3_column_text(stmt, 6));
    const auto detail = ParseJsonColumn(sqlite3_column_text(stmt, 7));
    if (!capability_names.has_value() || !source_summary.has_value() || !detail.has_value()) {
        return std::nullopt;
    }
    RuntimeRevisionRecord record;
    record.id = sqlite3_column_int(stmt, 0);
    record.revision_token = reinterpret_cast<const char*>(sqlite3_column_text(stmt, 1));
    record.action = reinterpret_cast<const char*>(sqlite3_column_text(stmt, 2));
    record.status = reinterpret_cast<const char*>(sqlite3_column_text(stmt, 3));
    record.license_valid = sqlite3_column_int(stmt, 4) != 0;
    record.capability_names = *capability_names;
    record.source_summary = *source_summary;
    record.detail = *detail;
    if (sqlite3_column_type(stmt, 8) != SQLITE_NULL) {
        record.rollback_of_revision_id = sqlite3_column_int(stmt, 8);
    }
    if (sqlite3_column_type(stmt, 9) != SQLITE_NULL) {
        record.created_at = reinterpret_cast<const char*>(sqlite3_column_text(stmt, 9));
    }
    return record;
}

std::optional<RuntimeOperationRecord> ReadOperationRow(sqlite3_stmt* stmt) {
    const auto detail = ParseJsonColumn(sqlite3_column_text(stmt, 3));
    if (!detail.has_value()) {
        return std::nullopt;
    }
    RuntimeOperationRecord record;
    record.id = sqlite3_column_int(stmt, 0);
    record.action = reinterpret_cast<const char*>(sqlite3_column_text(stmt, 1));
    record.status = reinterpret_cast<const char*>(sqlite3_column_text(stmt, 2));
    record.detail = *detail;
    if (sqlite3_column_type(stmt, 4) != SQLITE_NULL) {
        record.revision_id = sqlite3_column_int(stmt, 4);
    }
    if (sqlite3_column_type(stmt, 5) != SQLITE_NULL) {
        record.created_at = reinterpret_cast<const char*>(sqlite3_column_text(stmt, 5));
    }
    return record;
}

}

RevisionStore::RevisionStore(std::string database_path)
    : databasePath(std::move(database_path)) {
}

bool RevisionStore::EnsureSchema(std::string* error_message) {
    auto db = OpenDatabase(databasePath, error_message);
    if (!db) {
        return false;
    }
    return Execute(
        db.get(),
        "CREATE TABLE IF NOT EXISTS runtime_revision ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT,"
        "revision_token VARCHAR(128),"
        "action VARCHAR(32) NOT NULL,"
        "status VARCHAR(32) NOT NULL DEFAULT 'active',"
        "source_summary_json TEXT NOT NULL,"
        "capabilities_json TEXT NOT NULL,"
        "license_valid BOOLEAN NOT NULL DEFAULT 0,"
        "detail_json TEXT NOT NULL,"
        "rollback_of_revision_id INTEGER NULL REFERENCES runtime_revision(id),"
        "created_at DATETIME DEFAULT CURRENT_TIMESTAMP"
        ");"
        "CREATE INDEX IF NOT EXISTS ix_runtime_revision_revision_token ON runtime_revision(revision_token);"
        "CREATE TABLE IF NOT EXISTS runtime_operation ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT,"
        "action VARCHAR(32) NOT NULL,"
        "status VARCHAR(32) NOT NULL,"
        "detail_json TEXT NOT NULL,"
        "revision_id INTEGER NULL REFERENCES runtime_revision(id),"
        "created_at DATETIME DEFAULT CURRENT_TIMESTAMP"
        ");",
        error_message);
}

std::optional<RuntimeRevisionRecord> RevisionStore::CreateRevision(
    const std::string& revision_token,
    const std::string& action,
    const std::string& status,
    const nlohmann::json& source_summary,
    const nlohmann::json& capability_names,
    bool license_valid,
    const nlohmann::json& detail,
    const std::optional<int>& rollback_of_revision_id,
    std::string* error_message) {
    auto db = OpenDatabase(databasePath, error_message);
    if (!db) {
        return std::nullopt;
    }
    if (!EnsureSchema(error_message)) {
        return std::nullopt;
    }

    auto stmt = Prepare(
        db.get(),
        "INSERT INTO runtime_revision("
        "revision_token, action, status, source_summary_json, capabilities_json, license_valid, detail_json, rollback_of_revision_id"
        ") VALUES (?, ?, ?, ?, ?, ?, ?, ?);",
        error_message);
    if (!stmt) {
        return std::nullopt;
    }
    if (!BindText(stmt.get(), 1, revision_token) ||
        !BindText(stmt.get(), 2, action) ||
        !BindText(stmt.get(), 3, status) ||
        !BindText(stmt.get(), 4, source_summary.dump()) ||
        !BindText(stmt.get(), 5, capability_names.dump()) ||
        sqlite3_bind_int(stmt.get(), 6, license_valid ? 1 : 0) != SQLITE_OK ||
        !BindText(stmt.get(), 7, detail.dump()) ||
        (rollback_of_revision_id.has_value()
             ? sqlite3_bind_int(stmt.get(), 8, *rollback_of_revision_id) != SQLITE_OK
             : sqlite3_bind_null(stmt.get(), 8) != SQLITE_OK)) {
        if (error_message != nullptr) {
            *error_message = sqlite3_errmsg(db.get());
        }
        return std::nullopt;
    }
    if (sqlite3_step(stmt.get()) != SQLITE_DONE) {
        if (error_message != nullptr) {
            *error_message = sqlite3_errmsg(db.get());
        }
        return std::nullopt;
    }
    return GetRevision(static_cast<int>(sqlite3_last_insert_rowid(db.get())), error_message);
}

std::optional<RuntimeOperationRecord> RevisionStore::CreateOperation(
    const std::string& action,
    const std::string& status,
    const nlohmann::json& detail,
    const std::optional<int>& revision_id,
    std::string* error_message) {
    auto db = OpenDatabase(databasePath, error_message);
    if (!db) {
        return std::nullopt;
    }
    if (!EnsureSchema(error_message)) {
        return std::nullopt;
    }
    auto stmt = Prepare(
        db.get(),
        "INSERT INTO runtime_operation(action, status, detail_json, revision_id) VALUES (?, ?, ?, ?);",
        error_message);
    if (!stmt) {
        return std::nullopt;
    }
    if (!BindText(stmt.get(), 1, action) ||
        !BindText(stmt.get(), 2, status) ||
        !BindText(stmt.get(), 3, detail.dump()) ||
        (revision_id.has_value()
             ? sqlite3_bind_int(stmt.get(), 4, *revision_id) != SQLITE_OK
             : sqlite3_bind_null(stmt.get(), 4) != SQLITE_OK)) {
        if (error_message != nullptr) {
            *error_message = sqlite3_errmsg(db.get());
        }
        return std::nullopt;
    }
    if (sqlite3_step(stmt.get()) != SQLITE_DONE) {
        if (error_message != nullptr) {
            *error_message = sqlite3_errmsg(db.get());
        }
        return std::nullopt;
    }

    auto query = Prepare(
        db.get(),
        "SELECT id, action, status, detail_json, revision_id, created_at FROM runtime_operation WHERE id = ?;",
        error_message);
    if (!query) {
        return std::nullopt;
    }
    if (sqlite3_bind_int64(query.get(), 1, sqlite3_last_insert_rowid(db.get())) != SQLITE_OK) {
        if (error_message != nullptr) {
            *error_message = sqlite3_errmsg(db.get());
        }
        return std::nullopt;
    }
    if (sqlite3_step(query.get()) != SQLITE_ROW) {
        if (error_message != nullptr) {
            *error_message = sqlite3_errmsg(db.get());
        }
        return std::nullopt;
    }
    return ReadOperationRow(query.get());
}

std::optional<RuntimeRevisionRecord> RevisionStore::GetRevision(int revision_id, std::string* error_message) {
    auto db = OpenDatabase(databasePath, error_message);
    if (!db) {
        return std::nullopt;
    }
    if (!EnsureSchema(error_message)) {
        return std::nullopt;
    }
    auto stmt = Prepare(
        db.get(),
        "SELECT id, revision_token, action, status, license_valid, capabilities_json, source_summary_json, detail_json, rollback_of_revision_id, created_at "
        "FROM runtime_revision WHERE id = ?;",
        error_message);
    if (!stmt) {
        return std::nullopt;
    }
    if (sqlite3_bind_int(stmt.get(), 1, revision_id) != SQLITE_OK) {
        if (error_message != nullptr) {
            *error_message = sqlite3_errmsg(db.get());
        }
        return std::nullopt;
    }
    const int rc = sqlite3_step(stmt.get());
    if (rc == SQLITE_DONE) {
        return std::nullopt;
    }
    if (rc != SQLITE_ROW) {
        if (error_message != nullptr) {
            *error_message = sqlite3_errmsg(db.get());
        }
        return std::nullopt;
    }
    return ReadRevisionRow(stmt.get());
}
