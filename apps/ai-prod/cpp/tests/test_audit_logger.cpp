#include "audit_logger.h"

#include <filesystem>
#include <fstream>
#include <iostream>
#include <string>

namespace {

bool Expect(bool condition, const char* message) {
    if (!condition) {
        std::cerr << message << std::endl;
        return false;
    }
    return true;
}

std::string ReadFirstLine(const std::filesystem::path& path) {
    std::ifstream input(path);
    std::string line;
    std::getline(input, line);
    return line;
}

}  // namespace

int main() {
    const auto log_path = std::filesystem::temp_directory_path() / "ai_prod_cpp_audit_logger_test.log";
    std::filesystem::remove(log_path);

    AuditLogger logger(log_path.string());
    logger.Append(
        {
            "infer",
            "capability",
            "face_detect",
            "success",
            "req-1",
            "corr-1",
            12.5,
            "",
            {
                {"queue_wait_ms", 3},
                {"device", "gpu"},
            },
        });

    if (!Expect(std::filesystem::exists(log_path), "audit logger should create log file")) {
        return 1;
    }

    const auto line = ReadFirstLine(log_path);
    if (!Expect(!line.empty(), "audit logger should write a line")) {
        return 1;
    }
    const auto payload = nlohmann::json::parse(line);
    if (!Expect(payload["action"] == "infer", "audit action mismatch")) {
        return 1;
    }
    if (!Expect(payload["entity_type"] == "capability", "audit entity type mismatch")) {
        return 1;
    }
    if (!Expect(payload["entity_id"] == "face_detect", "audit entity id mismatch")) {
        return 1;
    }
    if (!Expect(payload["detail"]["status"] == "success", "audit detail should include status")) {
        return 1;
    }
    if (!Expect(payload["detail"]["request_id"] == "req-1", "audit detail should include request id")) {
        return 1;
    }
    if (!Expect(payload["detail"]["correlation_id"] == "corr-1", "audit detail should include correlation id")) {
        return 1;
    }
    if (!Expect(payload["detail"]["elapsed_ms"] == 12.5, "audit detail should include elapsed ms")) {
        return 1;
    }
    if (!Expect(payload["detail"]["queue_wait_ms"] == 3, "audit detail should preserve custom detail")) {
        return 1;
    }
    if (!Expect(payload.contains("happened_at_cst"), "audit payload should include timestamp")) {
        return 1;
    }

    std::filesystem::remove(log_path);
    return 0;
}
