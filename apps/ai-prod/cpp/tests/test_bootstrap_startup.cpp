#include "http_server.h"
#include "revision_store.h"
#include "test_license_helpers.h"

#include <cpp-httplib/httplib.h>
#include <nlohmann/json.hpp>

#include <chrono>
#include <ctime>
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <map>
#include <optional>
#include <sstream>
#include <string>
#include <thread>

namespace {

bool Expect(bool condition, const char* message) {
    if (!condition) {
        std::cerr << message << std::endl;
        return false;
    }
    return true;
}

bool WaitForHttpReady(const std::string& host, int port, const std::string& path) {
    httplib::Client client(host, port);
    for (int attempt = 0; attempt < 50; ++attempt) {
        const auto result = client.Get(path);
        if (result) {
            return true;
        }
        std::this_thread::sleep_for(std::chrono::milliseconds(100));
    }
    return false;
}

std::filesystem::path CurrentBinaryDir(const char* argv0) {
    return std::filesystem::weakly_canonical(std::filesystem::path(argv0)).parent_path();
}

std::string SharedLibraryName() {
#ifdef _WIN32
    return "test_mock_ai_plugin.dll";
#elif __APPLE__
    return "libtest_mock_ai_plugin.dylib";
#else
    return "libtest_mock_ai_plugin.so";
#endif
}

std::string NowCstWithOffset(int day_offset) {
    const auto now = std::time(nullptr) + 8 * 60 * 60 + day_offset * 24 * 60 * 60;
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

void WriteTextFile(const std::filesystem::path& path, const std::string& content) {
    std::filesystem::create_directories(path.parent_path());
    std::ofstream output(path);
    output << content;
}

}

int main(int argc, char** argv) {
    const auto temp_root = std::filesystem::temp_directory_path() / "ai_prod_cpp_bootstrap_startup_test";
    std::filesystem::remove_all(temp_root);

    const auto snapshot_path = temp_root / "data" / "runtime_snapshot.json";
    const auto database_path = temp_root / "data" / "ai_prod.db";
    const auto runtime_log_path = temp_root / "logs" / "runtime.log";
    const auto audit_log_path = temp_root / "logs" / "audit.log";
    const auto license_root = temp_root / "license";
    const auto host_root = temp_root / "host";
    const auto image_root = temp_root / "image";

    const auto built_plugin_path = CurrentBinaryDir(argv[0]) / SharedLibraryName();
    if (!Expect(std::filesystem::exists(built_plugin_path), "test plugin library should exist")) {
        return 1;
    }

    WriteTextFile(
        host_root / "models" / "face_detect" / "v2_0_0" / "manifest.json",
        R"({"capability_name":"face_detect","model_version":"v2_0_0","backend_type":"onnxruntime","max_batch_size":5})");
    WriteTextFile(
        host_root / "libs" / "linux_x86_64" / "face_detect" / "manifest" / "manifest.json",
        R"({"capability_name":"face_detect","target_name":"linux_x86_64","build_mode":"release","instance_count":3})");
    std::filesystem::create_directories(host_root / "libs" / "linux_x86_64" / "face_detect" / "lib");
    std::filesystem::copy_file(
        built_plugin_path,
        host_root / "libs" / "linux_x86_64" / "face_detect" / "lib" / "libface_detect.so",
        std::filesystem::copy_options::overwrite_existing);

    const std::map<std::string, std::string> hardware_features = {
        {"cpu", "intel-i7"},
        {"mac", "00:11:22:33:44:55"},
    };
    nlohmann::json license_payload = {
        {"customer_code", "cust_prod"},
        {"capability_scope", nlohmann::json::array({"face_detect"})},
        {"hardware_fingerprint", test_license_helpers::BuildHardwareFingerprint(hardware_features)},
        {"start_at_cst", NowCstWithOffset(-1)},
        {"expire_at_cst", NowCstWithOffset(30)},
        {"version_constraints", {{"min_version", "v1_0_0"}, {"max_version", "v9_9_9"}}},
    };
    test_license_helpers::WriteLicenseBundle(license_root, license_payload);

    ProxyConfig config;
    config.bind_host = "127.0.0.1";
    config.bind_port = 29115;
    config.backend_host = "127.0.0.1";
    config.backend_port = 29114;
    config.host_root = host_root.string();
    config.image_resource_root = image_root.string();
    config.license_root = license_root.string();
    config.database_path = database_path.string();
    config.hardware_features = hardware_features;
    config.license_auto_reload_interval_seconds = 1;
    config.runtime_snapshot_path = snapshot_path.string();
    config.runtime_log_path = runtime_log_path.string();
    config.audit_log_path = audit_log_path.string();
    config.pool_size = 2;
    config.connect_timeout_ms = 200;
    config.read_timeout_ms = 200;
    config.write_timeout_ms = 200;
    config.snapshot_max_age_seconds = 60;

    AiProdHttpServer proxy_server(config);
    std::thread proxy_thread([&]() {
        proxy_server.Start();
    });

    if (!Expect(WaitForHttpReady("127.0.0.1", config.bind_port, "/api/v1/health"), "proxy server did not bootstrap on startup")) {
        proxy_server.Stop();
        proxy_thread.join();
        return 1;
    }

    httplib::Client client("127.0.0.1", config.bind_port);
    const auto health_result = client.Get("/api/v1/health");
    if (!Expect(health_result && health_result->status == 200, "health route should respond after bootstrap")) {
        proxy_server.Stop();
        proxy_thread.join();
        return 1;
    }
    const auto health_payload = nlohmann::json::parse(health_result->body);
    if (!Expect(health_payload["runtime_revision_id"] == 1, "bootstrap should publish first runtime revision")) {
        proxy_server.Stop();
        proxy_thread.join();
        return 1;
    }
    if (!Expect(std::filesystem::exists(snapshot_path), "bootstrap should write runtime snapshot")) {
        proxy_server.Stop();
        proxy_thread.join();
        return 1;
    }

    RevisionStore revision_store(database_path.string());
    std::string revision_error;
    const auto revision = revision_store.GetRevision(1, &revision_error);
    if (!Expect(revision.has_value(), revision_error.c_str())) {
        proxy_server.Stop();
        proxy_thread.join();
        return 1;
    }
    if (!Expect(revision->action == "bootstrap", "bootstrap should persist bootstrap revision")) {
        proxy_server.Stop();
        proxy_thread.join();
        return 1;
    }

    const auto infer_result = client.Post(
        "/api/v1/infer/face_detect",
        "{\"input_type\":\"json\",\"payload\":\"demo\"}",
        "application/json");
    if (!Expect(infer_result && infer_result->status == 200, "infer should succeed after startup bootstrap")) {
        proxy_server.Stop();
        proxy_thread.join();
        return 1;
    }
    const auto infer_payload = nlohmann::json::parse(infer_result->body);
    if (!Expect(infer_payload["result"]["plugin_result"]["mock"] == true, "infer should use plugin execution after bootstrap")) {
        proxy_server.Stop();
        proxy_thread.join();
        return 1;
    }
    if (!Expect(infer_payload["result"]["plugin_result"]["max_batch_size"] == 5, "bootstrap infer should pass max batch size to plugin")) {
        proxy_server.Stop();
        proxy_thread.join();
        return 1;
    }
    if (!Expect(infer_payload["model_version"] == "v2_0_0", "bootstrap infer should expose initial model version")) {
        proxy_server.Stop();
        proxy_thread.join();
        return 1;
    }

    WriteTextFile(
        host_root / "models" / "face_detect" / "v3_0_0" / "manifest.json",
        R"({"capability_name":"face_detect","model_version":"v3_0_0","backend_type":"onnxruntime","max_batch_size":6})");
    const auto reload_result = client.Post(
        "/api/v1/admin/reload",
        "{\"action\":\"reload\"}",
        "application/json");
    if (!Expect(reload_result && reload_result->status == 200, "reload should succeed after adding new model version")) {
        proxy_server.Stop();
        proxy_thread.join();
        return 1;
    }

    const auto infer_after_reload = client.Post(
        "/api/v1/infer/face_detect",
        "{\"input_type\":\"json\",\"payload\":\"demo-reload\"}",
        "application/json");
    if (!Expect(infer_after_reload && infer_after_reload->status == 200, "infer should succeed after reload")) {
        proxy_server.Stop();
        proxy_thread.join();
        return 1;
    }
    const auto infer_after_reload_payload = nlohmann::json::parse(infer_after_reload->body);
    if (!Expect(infer_after_reload_payload["model_version"] == "v3_0_0", "reload should switch to latest model version")) {
        proxy_server.Stop();
        proxy_thread.join();
        return 1;
    }
    if (!Expect(infer_after_reload_payload["result"]["plugin_result"]["max_batch_size"] == 6, "reload should refresh max batch size")) {
        proxy_server.Stop();
        proxy_thread.join();
        return 1;
    }

    const auto rollback_result = client.Post(
        "/api/v1/admin/rollback",
        "{\"target_revision_id\":1}",
        "application/json");
    if (!Expect(rollback_result && rollback_result->status == 200, "rollback should restore bootstrap revision")) {
        proxy_server.Stop();
        proxy_thread.join();
        return 1;
    }

    const auto infer_after_rollback = client.Post(
        "/api/v1/infer/face_detect",
        "{\"input_type\":\"json\",\"payload\":\"demo-rollback\"}",
        "application/json");
    if (!Expect(infer_after_rollback && infer_after_rollback->status == 200, "infer should succeed after rollback")) {
        proxy_server.Stop();
        proxy_thread.join();
        return 1;
    }
    const auto infer_after_rollback_payload = nlohmann::json::parse(infer_after_rollback->body);
    if (!Expect(infer_after_rollback_payload["model_version"] == "v2_0_0", "rollback should restore bootstrap model version")) {
        proxy_server.Stop();
        proxy_thread.join();
        return 1;
    }

    proxy_server.Stop();
    proxy_thread.join();
    std::filesystem::remove_all(temp_root);
    return 0;
}
