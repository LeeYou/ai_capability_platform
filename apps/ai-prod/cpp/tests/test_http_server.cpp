#include "backend_client.h"
#include "http_server.h"
#include "proxy_config.h"
#include "test_license_helpers.h"

#include <cpp-httplib/httplib.h>
#include <nlohmann/json.hpp>

#include <chrono>
#include <atomic>
#include <cstdlib>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <map>
#include <optional>
#include <sstream>
#include <string>
#include <thread>
#include <vector>

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

std::string SamplePngBase64() {
    return "iVBORw0KGgo=";
}

std::string SamplePdfBase64() {
    return "JVBERi0xLjQK";
}

void WriteSnapshot(
    const std::filesystem::path& snapshot_path,
    int revision_id,
    int pool_size,
    int max_batch_size,
    int batch_wait_timeout_ms,
    int queue_wait_timeout_ms,
    int max_pending_request_count,
    const std::filesystem::path& model_root,
    const std::filesystem::path& binary_path) {
    std::ofstream snapshot_output(snapshot_path);
    snapshot_output
        << "{"
        << "\"revision_id\":" << revision_id << ","
        << "\"capability_count\":1,"
        << "\"service_name\":\"ai-prod\","
        << "\"company_name\":\"北京爱知之星科技股份有限公司（Agile Star）\","
        << "\"company_domain\":\"agilestar.cn\","
        << "\"capabilities\":[{"
        << "\"capability_name\":\"face_detect\","
        << "\"plugin_target\":\"linux_x86_64\","
        << "\"model_version\":\"v2_0_0\","
        << "\"backend_type\":\"onnxruntime\","
        << "\"active_source\":\"host\","
        << "\"device_mode\":\"gpu/cpu\","
        << "\"capability_priority\":150,"
        << "\"model_root\":\"" << model_root.string() << "\","
        << "\"binary_path\":\"" << binary_path.string() << "\","
        << "\"pool_size\":" << pool_size << ","
        << "\"max_batch_size\":" << max_batch_size << ","
        << "\"min_batch_size\":2,"
        << "\"batch_wait_timeout_ms\":" << batch_wait_timeout_ms << ","
        << "\"queue_wait_timeout_ms\":" << queue_wait_timeout_ms << ","
        << "\"max_pending_request_count\":" << max_pending_request_count << ","
        << "\"infer_timeout_ms\":900,"
        << "\"estimated_avg_infer_time_ms\":45,"
        << "\"p95_infer_time_ms\":80,"
        << "\"max_concurrent_requests\":3,"
        << "\"supports_concurrent_infer\":true,"
        << "\"allow_resource_sharing\":true,"
        << "\"revision_id\":" << revision_id
        << "}],"
        << "\"license_status\":{"
        << "\"valid\":true,"
        << "\"reason\":\"ok\","
        << "\"result\":\"passed\","
        << "\"code\":\"license_valid\","
        << "\"stage\":\"success\","
        << "\"details\":{\"check\":\"success\"},"
        << "\"diagnostics_version\":\"1.0\","
        << "\"checked_at_cst\":\"2026-04-02T17:00:00+08:00\","
        << "\"customer_code\":\"cust_prod\","
        << "\"capability_scope\":[\"face_detect\"],"
        << "\"version_constraints\":{},"
        << "\"hardware_fingerprint\":\"abc\","
        << "\"runtime_revision_id\":" << revision_id
        << "}"
        << "}";
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

std::string BuildModelManifest(
    const std::filesystem::path& model_root,
    const std::string& capability_name,
    const std::string& model_version,
    int max_batch_size,
    int min_batch_size = 1,
    int queue_wait_timeout_ms = -1,
    int infer_timeout_ms = -1,
    int estimated_avg_infer_time_ms = -1,
    int p95_infer_time_ms = -1,
    int max_concurrent_requests = -1,
    int capability_priority = 100,
    const std::string& device_mode = "auto",
    bool supports_concurrent_infer = true,
    bool allow_resource_sharing = false) {
    const auto preprocess_path = model_root / "preprocess.json";
    const auto labels_path = model_root / "labels.json";
    const auto validation_path = model_root / "validation" / "acceptance_checklist.json";
    const auto delivery_metadata_path = model_root / "delivery_metadata.json";
    const auto runtime_contract_path = model_root / "runtime_contract.json";
    WriteTextFile(preprocess_path, R"({"input_type":"image","resize":{"width":640,"height":640},"normalize":{"mean":[0.5],"std":[0.5]}})");
    WriteTextFile(labels_path, R"({"labels":["ok","ng"]})");
    WriteTextFile(validation_path, R"({"required_cases":["acceptance_check"]})");
    WriteTextFile(delivery_metadata_path, R"({"ai_builder":{"manifest_schema_path":"apps/shared/schemas/manifest_model.json"}})");
    const nlohmann::json runtime_contract = {
        {"task_type", "detection"},
        {"annotation_schema", {{"type", "object"}}},
        {"template_bundle", {{"name", capability_name}}},
        {"model_files", nlohmann::json::array({"model.onnx"})},
        {"runtime_inputs", {{"preprocess_path", preprocess_path.string()}, {"labels_path", labels_path.string()}}},
    };
    WriteTextFile(runtime_contract_path, runtime_contract.dump());
    return nlohmann::json{
        {"capability_name", capability_name},
        {"task_type", "detection"},
        {"model_version", model_version},
        {"source_train_task_id", 1},
        {"task_name", capability_name + "_task"},
        {"backend_type", "onnxruntime"},
        {"artifact_path", model_root.string()},
        {"status", "ready"},
        {"checksum", capability_name + "-" + model_version + "-checksum"},
        {"preprocessing", {{"input_type", "image"}, {"resize", {{"width", 640}, {"height", 640}}}, {"normalize", {{"mean", nlohmann::json::array({0.5})}, {"std", nlohmann::json::array({0.5})}}}}},
        {"thresholds", {{"score_threshold", 0.5}, {"nms_threshold", 0.45}}},
        {"labels", nlohmann::json::array({"ok", "ng"})},
        {"validation", {{"artifacts", nlohmann::json::array({"preprocess.json", "labels.json", "validation/acceptance_checklist.json", "delivery_metadata.json", "runtime_contract.json"})}}},
        {"runtime_contract", runtime_contract},
        {"delivery_metadata", {{"ai_test", {{"task_type", "acceptance"}}}, {"ai_builder", {{"manifest_schema_path", "apps/shared/schemas/manifest_model.json"}}}, {"training_summary", {{"backend_type", "onnxruntime"}}}}},
        {"device_mode", device_mode},
        {"capability_priority", capability_priority},
        {"max_batch_size", max_batch_size},
        {"min_batch_size", min_batch_size},
        {"queue_wait_timeout_ms", queue_wait_timeout_ms},
        {"infer_timeout_ms", infer_timeout_ms},
        {"estimated_avg_infer_time_ms", estimated_avg_infer_time_ms},
        {"p95_infer_time_ms", p95_infer_time_ms},
        {"max_concurrent_requests", max_concurrent_requests},
        {"supports_concurrent_infer", supports_concurrent_infer},
        {"allow_resource_sharing", allow_resource_sharing},
    }.dump();
}

std::string BuildPluginManifest(
    const std::string& capability_name,
    const std::string& model_version,
    const std::string& target_name,
    int instance_count,
    int max_pending_request_count,
    int capability_priority = 100) {
    return nlohmann::json{
        {"capability_name", capability_name},
        {"model_version", model_version},
        {"target_name", target_name},
        {"artifact_format", "so"},
        {"build_mode", "native"},
        {"toolchain_name", "cmake-native"},
        {"jni_enabled", false},
        {"customer_code", "cust_prod"},
        {"issue_record_id", 1},
        {"dependency_summary", {{"runtime", "onnxruntime"}, {"abi", "cxx17"}, {"license_required", true}, {"build_params_controlled", true}}},
        {"instance_count", instance_count},
        {"max_pending_request_count", max_pending_request_count},
        {"capability_priority", capability_priority},
    }.dump();
}

std::vector<nlohmann::json> ReadJsonLines(const std::filesystem::path& path) {
    std::vector<nlohmann::json> items;
    std::ifstream input(path);
    std::string line;
    while (std::getline(input, line)) {
        if (line.empty()) {
            continue;
        }
        items.push_back(nlohmann::json::parse(line));
    }
    return items;
}

std::optional<nlohmann::json> FindLastAuditAction(const std::vector<nlohmann::json>& items, const std::string& action) {
    for (auto it = items.rbegin(); it != items.rend(); ++it) {
        if (it->value("action", "") == action) {
            return *it;
        }
    }
    return std::nullopt;
}

}

int main(int argc, char** argv) {
    const std::filesystem::path snapshot_path = std::filesystem::temp_directory_path() / "ai_prod_cpp_runtime_snapshot_test.json";
    const std::filesystem::path license_root = std::filesystem::temp_directory_path() / "ai_prod_cpp_runtime_license_test";
    const std::filesystem::path runtime_log_path = std::filesystem::temp_directory_path() / "ai_prod_cpp_runtime_test.log";
    const std::filesystem::path audit_log_path = std::filesystem::temp_directory_path() / "ai_prod_cpp_audit_test.log";
    const std::filesystem::path host_root = std::filesystem::temp_directory_path() / "ai_prod_cpp_runtime_host_root";
    const std::filesystem::path image_root = std::filesystem::temp_directory_path() / "ai_prod_cpp_runtime_image_root";
    const std::filesystem::path database_path = std::filesystem::temp_directory_path() / "ai_prod_cpp_runtime_test.db";
    std::filesystem::remove_all(license_root);
    std::filesystem::remove_all(host_root);
    std::filesystem::remove_all(image_root);
    std::filesystem::remove(database_path);
    std::filesystem::remove(runtime_log_path);
    std::filesystem::remove(audit_log_path);
    const auto built_plugin_path = CurrentBinaryDir(argv[0]) / SharedLibraryName();
    if (!Expect(std::filesystem::exists(built_plugin_path), "test plugin library should exist")) {
        return 1;
    }
    WriteTextFile(
        host_root / "models" / "face_detect" / "v2_0_0" / "manifest.json",
        BuildModelManifest(host_root / "models" / "face_detect" / "v2_0_0", "face_detect", "v2_0_0", 5, 2, 220, 900, 45, 80, 3, 120, "gpu/cpu", true, true));
    WriteTextFile(
        host_root / "libs" / "linux_x86_64" / "face_detect" / "manifest" / "manifest.json",
        BuildPluginManifest("face_detect", "v2_0_0", "linux_x86_64", 2, 4, 140));
    std::filesystem::create_directories(host_root / "libs" / "linux_x86_64" / "face_detect" / "lib");
    std::filesystem::copy_file(
        built_plugin_path,
        host_root / "libs" / "linux_x86_64" / "face_detect" / "lib" / "libface_detect.so",
        std::filesystem::copy_options::overwrite_existing);
    WriteTextFile(
        image_root / "models" / "ocr" / "v1_0_0" / "manifest.json",
        BuildModelManifest(image_root / "models" / "ocr" / "v1_0_0", "ocr", "v1_0_0", 3));
    WriteTextFile(
        image_root / "libs" / "linux_x86_64" / "ocr" / "manifest" / "manifest.json",
        BuildPluginManifest("ocr", "v1_0_0", "linux_x86_64", 2, 0));
    std::filesystem::create_directories(image_root / "libs" / "linux_x86_64" / "ocr" / "lib");
    std::filesystem::copy_file(
        built_plugin_path,
        image_root / "libs" / "linux_x86_64" / "ocr" / "lib" / "libocr.so",
        std::filesystem::copy_options::overwrite_existing);
    WriteTextFile(
        image_root / "models" / "pose_estimate" / "gpucheckfail_v1_0_0" / "manifest.json",
        BuildModelManifest(image_root / "models" / "pose_estimate" / "gpucheckfail_v1_0_0", "pose_estimate", "gpucheckfail_v1_0_0", 2));
    WriteTextFile(
        image_root / "libs" / "linux_x86_64" / "pose_estimate" / "manifest" / "manifest.json",
        BuildPluginManifest("pose_estimate", "gpucheckfail_v1_0_0", "linux_x86_64", 2, 0));
    std::filesystem::create_directories(image_root / "libs" / "linux_x86_64" / "pose_estimate" / "lib");
    std::filesystem::copy_file(
        built_plugin_path,
        image_root / "libs" / "linux_x86_64" / "pose_estimate" / "lib" / "libpose_estimate.so",
        std::filesystem::copy_options::overwrite_existing);
    WriteSnapshot(
        snapshot_path,
        9,
        1,
        4,
        30,
        180,
        3,
        host_root / "models" / "face_detect" / "v2_0_0",
        host_root / "libs" / "linux_x86_64" / "face_detect" / "lib" / "libface_detect.so");
    const std::map<std::string, std::string> hardware_features = {
        {"cpu", "intel-i7"},
        {"mac", "00:11:22:33:44:55"},
    };
    nlohmann::json license_payload = {
        {"customer_code", "cust_prod"},
        {"capability_scope", nlohmann::json::array({"face_detect", "ocr", "pose_estimate"})},
        {"hardware_fingerprint", test_license_helpers::BuildHardwareFingerprint(hardware_features)},
        {"start_at_cst", NowCstWithOffset(-1)},
        {"expire_at_cst", NowCstWithOffset(30)},
        {"version_constraints", {{"min_version", "v1_0_0"}, {"max_version", "v9_9_9"}}},
    };
    test_license_helpers::WriteLicenseBundle(license_root, license_payload);

    if (!Expect(
            AiProdBackendClient::NormalizeRollbackBody("{}") == "{\"action\":\"rollback\"}",
            "rollback normalization should add action")) {
        return 1;
    }

    const int backend_port = 29104;
    const int proxy_port = 29105;

    httplib::Server backend_server;
    backend_server.Get("/api/v1/health", [](const httplib::Request&, httplib::Response& response) {
        response.set_content("{\"status\":\"ok\",\"service\":\"backend\"}", "application/json");
    });

    std::thread backend_thread([&]() {
        backend_server.listen("127.0.0.1", backend_port);
    });

    if (!Expect(WaitForHttpReady("127.0.0.1", backend_port, "/api/v1/health"), "backend server did not start")) {
        backend_server.stop();
        backend_thread.join();
        return 1;
    }

    ProxyConfig config;
    config.bind_host = "127.0.0.1";
    config.bind_port = proxy_port;
    config.backend_host = "127.0.0.1";
    config.backend_port = backend_port;
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
    config.connect_timeout_ms = 1000;
    config.read_timeout_ms = 1000;
    config.write_timeout_ms = 1000;
    config.snapshot_max_age_seconds = 60;
    config.infer_queue_wait_timeout_ms = 150;
    config.infer_queue_max_pending_requests = 2;
    config.infer_batch_wait_timeout_ms = 10;

    AiProdHttpServer proxy_server(config);
    std::thread proxy_thread([&]() {
        proxy_server.Start();
    });

    if (!Expect(WaitForHttpReady("127.0.0.1", proxy_port, "/api/v1/health"), "proxy server did not start")) {
        proxy_server.Stop();
        backend_server.stop();
        proxy_thread.join();
        backend_thread.join();
        return 1;
    }

    httplib::Client proxy_client("127.0.0.1", proxy_port);
    const auto health_result = proxy_client.Get("/api/v1/health");
    if (!Expect(health_result && health_result->status == 200, "health route should proxy successfully")) {
        proxy_server.Stop();
        backend_server.stop();
        proxy_thread.join();
        backend_thread.join();
        return 1;
    }
    const auto health_payload = nlohmann::json::parse(health_result->body);
    if (!Expect(health_payload["runtime_revision_id"] == 9, "health route should use snapshot revision")) {
        return 1;
    }

    const auto capabilities_result = proxy_client.Get("/api/v1/capabilities");
    if (!Expect(capabilities_result && capabilities_result->status == 200, "capabilities route should respond")) {
        return 1;
    }
    const auto capabilities_payload = nlohmann::json::parse(capabilities_result->body);
    if (!Expect(capabilities_payload["items"].size() == 1, "capabilities route should use snapshot items")) {
        return 1;
    }
    const auto catalog_result = proxy_client.Get("/api/v1/admin/catalog");
    if (!Expect(catalog_result && catalog_result->status == 200, "catalog route should respond")) {
        return 1;
    }
    const auto catalog_payload = nlohmann::json::parse(catalog_result->body);
    if (!Expect(catalog_payload["snapshot_ready"] == true, "catalog route should mark snapshot ready")) {
        return 1;
    }
    if (!Expect(catalog_payload["runtime_state"] == "ready", "catalog route should expose ready runtime state")) {
        return 1;
    }
    if (!Expect(catalog_payload["items"].size() == 1, "catalog route should expose one capability")) {
        return 1;
    }
    if (!Expect(catalog_payload["active_request_count"] == 0, "catalog should start with zero active requests")) {
        return 1;
    }
    if (!Expect(catalog_payload["items"][0]["execution_metrics"].is_null(), "catalog should not expose execution metrics before first infer")) {
        return 1;
    }
    if (!Expect(catalog_payload["items"][0]["busy_count"] == 0, "catalog busy count should default to zero")) {
        return 1;
    }
    if (!Expect(catalog_payload["items"][0]["max_batch_size"] == 4, "catalog should expose max batch size from snapshot")) {
        return 1;
    }
    if (!Expect(catalog_payload["items"][0]["min_batch_size"] == 2, "catalog should expose min batch size from snapshot")) {
        return 1;
    }
    if (!Expect(catalog_payload["items"][0]["batch_wait_timeout_ms"] == 30, "catalog should expose snapshot batch wait timeout")) {
        return 1;
    }
    if (!Expect(catalog_payload["items"][0]["queue_wait_timeout_ms"] == 180, "catalog should expose snapshot queue wait timeout")) {
        return 1;
    }
    if (!Expect(catalog_payload["items"][0]["configured_max_pending_request_count"] == 3, "catalog should expose snapshot max pending configuration")) {
        return 1;
    }
    if (!Expect(catalog_payload["items"][0]["pending_request_count"] == 0, "catalog should start with zero pending requests")) {
        return 1;
    }
    if (!Expect(catalog_payload["items"][0]["orchestration"]["recommended_min_batch_size"] == 2, "catalog should expose orchestration recommendation")) {
        return 1;
    }
    if (!Expect(catalog_payload["orchestration_summary"]["overall_state"] == "stable", "catalog should expose orchestration summary")) {
        return 1;
    }

    const auto initial_metrics_result = proxy_client.Get("/api/v1/admin/metrics");
    if (!Expect(initial_metrics_result && initial_metrics_result->status == 200, "metrics route should respond")) {
        return 1;
    }
    const auto initial_metrics_payload = nlohmann::json::parse(initial_metrics_result->body);
    if (!Expect(initial_metrics_payload["pool_summary"]["capability_count"] == 1, "metrics should expose capability count")) {
        return 1;
    }
    if (!Expect(initial_metrics_payload["endpoint_metrics"]["health"]["total_requests"] >= 1, "metrics should count health requests")) {
        return 1;
    }
    if (!Expect(initial_metrics_payload["endpoint_metrics"]["capabilities"]["total_requests"] >= 1, "metrics should count capabilities requests")) {
        return 1;
    }
    if (!Expect(initial_metrics_payload["endpoint_metrics"]["admin_catalog"]["total_requests"] >= 1, "metrics should count catalog requests")) {
        return 1;
    }
    if (!Expect(initial_metrics_payload["pool_metrics"][0]["batch_metrics"]["batch_wait_timeout_ms"] == 30, "metrics should expose batch wait timeout")) {
        return 1;
    }
    if (!Expect(initial_metrics_payload["pool_metrics"][0]["orchestration"]["recommended_min_batch_size"] == 2, "metrics should expose orchestration output")) {
        return 1;
    }

    std::optional<int> batch_status_a;
    std::optional<int> batch_status_b;
    std::string batch_body_a;
    std::string batch_body_b;
    std::thread batch_thread_a([&]() {
        httplib::Client infer_client("127.0.0.1", proxy_port);
        const auto infer_result = infer_client.Post(
            "/api/v1/infer/face_detect",
            "{\"input_type\":\"json\",\"payload\":\"batch-a\"}",
            "application/json");
        if (!infer_result) {
            batch_status_a = 0;
            return;
        }
        batch_status_a = infer_result->status;
        batch_body_a = infer_result->body;
    });
    std::thread batch_thread_b([&]() {
        std::this_thread::sleep_for(std::chrono::milliseconds(5));
        httplib::Client infer_client("127.0.0.1", proxy_port);
        const auto infer_result = infer_client.Post(
            "/api/v1/infer/face_detect",
            "{\"input_type\":\"json\",\"payload\":\"batch-b\"}",
            "application/json");
        if (!infer_result) {
            batch_status_b = 0;
            return;
        }
        batch_status_b = infer_result->status;
        batch_body_b = infer_result->body;
    });
    batch_thread_a.join();
    batch_thread_b.join();
    if (!Expect(batch_status_a.has_value() && batch_status_a.value() == 200, "batched request a should succeed")) {
        return 1;
    }
    if (!Expect(batch_status_b.has_value() && batch_status_b.value() == 200, "batched request b should succeed")) {
        return 1;
    }
    const auto batch_payload_a = nlohmann::json::parse(batch_body_a);
    const auto batch_payload_b = nlohmann::json::parse(batch_body_b);
    if (!Expect(batch_payload_a["result"]["batch"]["batch_size"] == 2, "batched request a should report batch size")) {
        return 1;
    }
    if (!Expect(batch_payload_b["result"]["batch"]["batch_size"] == 2, "batched request b should report batch size")) {
        return 1;
    }
    if (!Expect(batch_payload_a["result"]["batch"]["batch_id"] == batch_payload_b["result"]["batch"]["batch_id"], "batched requests should share batch id")) {
        return 1;
    }
    if (!Expect(batch_payload_b["result"]["batch"]["batch_index"] == 1, "batched request b should report batch index")) {
        return 1;
    }
    if (!Expect(batch_payload_a["result"]["batch"]["batch_wait_ms"] >= 0, "batched request should expose batch wait")) {
        return 1;
    }
    const auto batch_metrics_result = proxy_client.Get("/api/v1/admin/metrics");
    if (!Expect(batch_metrics_result && batch_metrics_result->status == 200, "metrics should respond after batched infer")) {
        return 1;
    }
    const auto batch_metrics_payload = nlohmann::json::parse(batch_metrics_result->body);
    if (!Expect(batch_metrics_payload["request_summary"]["formed_batch_count"] >= 1, "metrics should count formed batches")) {
        return 1;
    }
    if (!Expect(batch_metrics_payload["request_summary"]["batched_request_count"] >= 2, "metrics should count batched requests")) {
        return 1;
    }

    const auto license_status_result = proxy_client.Get("/api/v1/license/status");
    if (!Expect(license_status_result && license_status_result->status == 200, "license status route should respond")) {
        return 1;
    }
    const auto license_status_payload = nlohmann::json::parse(license_status_result->body);
    if (!Expect(license_status_payload["valid"] == true, "license status should be valid")) {
        return 1;
    }
    if (!Expect(license_status_payload["code"] == "license_valid", "license status should expose stable code")) {
        return 1;
    }
    if (!Expect(license_status_payload["diagnostics_version"] == "1.0", "license status should expose diagnostics version")) {
        return 1;
    }
    if (!Expect(license_status_payload["capability_scope"].size() == 3, "license status should expose capability scope")) {
        return 1;
    }

    const auto internal_revisions_result = proxy_client.Get("/api/v1/admin/revisions");
    if (!Expect(internal_revisions_result && internal_revisions_result->status == 404, "public proxy should not expose internal revision route")) {
        return 1;
    }
    const auto internal_operations_result = proxy_client.Get("/api/v1/admin/operations");
    if (!Expect(internal_operations_result && internal_operations_result->status == 404, "public proxy should not expose internal operation route")) {
        return 1;
    }

    std::optional<int> queued_success_status;
    std::thread queued_success_thread([&]() {
        httplib::Client infer_client("127.0.0.1", proxy_port);
        const auto infer_result = infer_client.Post(
            "/api/v1/infer/face_detect",
            "{\"input_type\":\"json\",\"payload\":\"queue-holder\",\"options\":{\"simulate_delay_ms\":120}}",
            "application/json");
        if (!infer_result) {
            queued_success_status = 0;
            return;
        }
        queued_success_status = infer_result->status;
    });
    bool queue_holder_busy = false;
    for (int attempt = 0; attempt < 50; ++attempt) {
        const auto inflight_catalog_result = proxy_client.Get("/api/v1/admin/catalog");
        if (inflight_catalog_result && inflight_catalog_result->status == 200) {
            const auto inflight_catalog_payload = nlohmann::json::parse(inflight_catalog_result->body);
            if (inflight_catalog_payload["items"][0]["busy_count"] == 1) {
                queue_holder_busy = true;
                break;
            }
        }
        std::this_thread::sleep_for(std::chrono::milliseconds(10));
    }
    if (!Expect(queue_holder_busy, "queue success holder should occupy pool")) {
        queued_success_thread.join();
        return 1;
    }
    const auto queued_success_result = proxy_client.Post(
        "/api/v1/infer/face_detect",
        "{\"input_type\":\"json\",\"payload\":\"queue-success\"}",
        "application/json");
    queued_success_thread.join();
    if (!Expect(queued_success_status.has_value() && queued_success_status.value() == 200, "queue success holder should finish successfully")) {
        return 1;
    }
    if (!Expect(queued_success_result && queued_success_result->status == 200, "infer should succeed after queued wait")) {
        return 1;
    }
    const auto queued_success_payload = nlohmann::json::parse(queued_success_result->body);
    if (!Expect(queued_success_payload["result"]["queue_wait_ms"] >= 20, "queued infer should report positive queue wait")) {
        return 1;
    }
    const auto queue_metrics_result = proxy_client.Get("/api/v1/admin/metrics");
    if (!Expect(queue_metrics_result && queue_metrics_result->status == 200, "metrics should respond after queued infer")) {
        return 1;
    }
    const auto queue_metrics_payload = nlohmann::json::parse(queue_metrics_result->body);
    if (!Expect(queue_metrics_payload["request_summary"]["queued_request_count"] >= 1, "metrics should count queued requests")) {
        return 1;
    }
    if (!Expect(queue_metrics_payload["request_summary"]["avg_queue_wait_ms"] > 0.0, "metrics should report average queue wait")) {
        return 1;
    }
    const auto queue_catalog_result = proxy_client.Get("/api/v1/admin/catalog");
    if (!Expect(queue_catalog_result && queue_catalog_result->status == 200, "catalog should respond after queued infer")) {
        return 1;
    }
    const auto queue_catalog_payload = nlohmann::json::parse(queue_catalog_result->body);
    if (!Expect(queue_catalog_payload["items"][0]["max_pending_request_count"] >= 1, "catalog should expose max pending request count")) {
        return 1;
    }
    if (!Expect(queue_catalog_payload["items"][0]["configured_max_pending_request_count"] == 3, "catalog should preserve configured max pending configuration")) {
        return 1;
    }
    if (!Expect(queue_catalog_payload["items"][0]["orchestration"]["recommended_pool_size"].get<int>() >= 1, "catalog should surface orchestration output under queue pressure")) {
        return 1;
    }

    std::optional<int> infer_status;
    std::string infer_body;
    std::thread infer_thread([&]() {
        httplib::Client infer_client("127.0.0.1", proxy_port);
        const auto infer_result = infer_client.Post(
            "/api/v1/infer/face_detect",
            "{\"input_type\":\"json\",\"payload\":\"demo\",\"prefer_device\":\"gpu\",\"prefer_deadline_ms\":700,\"options\":{\"simulate_delay_ms\":400}}",
            "application/json");
        if (!infer_result) {
            infer_status = 0;
            return;
        }
        infer_status = infer_result->status;
        infer_body = infer_result->body;
    });

    bool infer_busy = false;
    for (int attempt = 0; attempt < 50; ++attempt) {
        const auto inflight_catalog_result = proxy_client.Get("/api/v1/admin/catalog");
        if (inflight_catalog_result && inflight_catalog_result->status == 200) {
            const auto inflight_catalog_payload = nlohmann::json::parse(inflight_catalog_result->body);
            if (inflight_catalog_payload["items"][0]["busy_count"] == 1) {
                infer_busy = true;
                break;
            }
        }
        std::this_thread::sleep_for(std::chrono::milliseconds(20));
    }
    if (!Expect(infer_busy, "infer request should occupy instance pool")) {
        infer_thread.join();
        return 1;
    }

    const auto busy_catalog_result = proxy_client.Get("/api/v1/admin/catalog");
    if (!Expect(busy_catalog_result && busy_catalog_result->status == 200, "catalog route should respond during infer")) {
        infer_thread.join();
        return 1;
    }
    const auto busy_catalog_payload = nlohmann::json::parse(busy_catalog_result->body);
    if (!Expect(busy_catalog_payload["items"][0]["busy_count"] == 1, "catalog busy count should reflect in-flight infer")) {
        infer_thread.join();
        return 1;
    }
    if (!Expect(busy_catalog_payload["active_request_count"] == 1, "catalog should expose one active request during infer")) {
        infer_thread.join();
        return 1;
    }
    if (!Expect(busy_catalog_payload["active_requests"].size() == 1, "catalog should list active request during infer")) {
        infer_thread.join();
        return 1;
    }
    if (!Expect(busy_catalog_payload["active_requests"][0]["capability_name"] == "face_detect", "active request should expose capability name")) {
        infer_thread.join();
        return 1;
    }
    if (!Expect(busy_catalog_payload["active_requests"][0]["status"] == "executing", "active request should expose executing status")) {
        infer_thread.join();
        return 1;
    }
    if (!Expect(busy_catalog_payload["active_requests"][0]["requested_deadline_ms"] == 700, "active request should expose requested deadline")) {
        infer_thread.join();
        return 1;
    }
    if (!Expect(busy_catalog_payload["active_requests"][0]["sla_status"] == "pending", "active request should expose pending sla status")) {
        infer_thread.join();
        return 1;
    }
    if (!Expect(busy_catalog_payload["items"][0]["pending_request_count"] == 0, "catalog should still show zero pending requests before queueing")) {
        infer_thread.join();
        return 1;
    }

    const auto busy_infer_result = proxy_client.Post(
        "/api/v1/infer/face_detect",
        "{\"input_type\":\"json\",\"payload\":\"demo-2\"}",
        "application/json");
    if (!Expect(busy_infer_result && busy_infer_result->status == 503, "infer route should reject when pool is busy")) {
        infer_thread.join();
        return 1;
    }
    const auto busy_metrics_result = proxy_client.Get("/api/v1/admin/metrics");
    if (!Expect(busy_metrics_result && busy_metrics_result->status == 200, "metrics route should respond during busy reject")) {
        infer_thread.join();
        return 1;
    }
    const auto busy_metrics_payload = nlohmann::json::parse(busy_metrics_result->body);
    if (!Expect(busy_metrics_payload["pool_metrics"][0]["busy_reject_count"] >= 1, "metrics should count busy rejects per pool")) {
        infer_thread.join();
        return 1;
    }
    if (!Expect(busy_metrics_payload["pool_metrics"][0]["queue_timeout_count"] >= 1, "metrics should count queue timeouts")) {
        infer_thread.join();
        return 1;
    }
    std::optional<int> reload_status;
    std::string reload_body;
    std::thread reload_thread([&]() {
        httplib::Client reload_client("127.0.0.1", proxy_port);
        const auto reload_result = reload_client.Post(
            "/api/v1/admin/reload",
            "{\"action\":\"reload\"}",
            "application/json");
        if (!reload_result) {
            reload_status = 0;
            return;
        }
        reload_status = reload_result->status;
        reload_body = reload_result->body;
    });
    std::this_thread::sleep_for(std::chrono::milliseconds(150));
    const auto concurrent_reload_result = proxy_client.Post(
        "/api/v1/admin/reload",
        "{\"action\":\"reload\"}",
        "application/json");
    if (!Expect(concurrent_reload_result && concurrent_reload_result->status == 409, "reload route should reject concurrent transition")) {
        reload_thread.join();
        infer_thread.join();
        return 1;
    }
    if (!Expect(!std::filesystem::exists(database_path), "reload should wait for in-flight infer to finish before persisting revision")) {
        reload_thread.join();
        infer_thread.join();
        return 1;
    }

    const auto draining_infer_result = proxy_client.Post(
        "/api/v1/infer/face_detect",
        "{\"input_type\":\"json\",\"payload\":\"demo-drain\"}",
        "application/json");
    if (!Expect(draining_infer_result && draining_infer_result->status == 503, "infer should reject during drain")) {
        reload_thread.join();
        infer_thread.join();
        return 1;
    }

    const auto draining_catalog_result = proxy_client.Get("/api/v1/admin/catalog");
    if (!Expect(draining_catalog_result && draining_catalog_result->status == 200, "catalog route should respond during drain")) {
        reload_thread.join();
        infer_thread.join();
        return 1;
    }
    const auto draining_catalog_payload = nlohmann::json::parse(draining_catalog_result->body);
    if (!Expect(draining_catalog_payload["draining"] == true, "catalog route should show draining state")) {
        reload_thread.join();
        infer_thread.join();
        return 1;
    }
    if (!Expect(draining_catalog_payload["runtime_state"] == "draining", "catalog route should expose draining runtime state")) {
        reload_thread.join();
        infer_thread.join();
        return 1;
    }
    if (!Expect(draining_catalog_payload["active_request_count"] == 1, "catalog should keep active request count during drain")) {
        reload_thread.join();
        infer_thread.join();
        return 1;
    }
    if (!Expect(draining_catalog_payload["items"][0]["draining"] == true, "catalog item should show draining state")) {
        reload_thread.join();
        infer_thread.join();
        return 1;
    }

    const auto missing_infer_result = proxy_client.Post(
        "/api/v1/infer/ocr",
        "{\"input_type\":\"json\",\"payload\":\"demo-3\"}",
        "application/json");
    if (!Expect(missing_infer_result && missing_infer_result->status == 404, "infer route should reject unknown capability")) {
        infer_thread.join();
        return 1;
    }

    infer_thread.join();
    reload_thread.join();
    if (!Expect(infer_status.has_value() && infer_status.value() == 200, "infer route should respond successfully")) {
        return 1;
    }
    if (!Expect(reload_status.has_value() && reload_status.value() == 200, "reload route should complete after drain")) {
        return 1;
    }
    const auto infer_payload = nlohmann::json::parse(infer_body);
    if (!Expect(infer_payload["capability_name"] == "face_detect", "infer should return capability name")) {
        return 1;
    }
    if (!Expect(infer_payload["plugin_target"] == "linux_x86_64", "infer should return plugin target")) {
        return 1;
    }
    if (!Expect(infer_payload["device"] == "gpu", "infer should select gpu when available")) {
        return 1;
    }
    if (!Expect(infer_payload["runtime_revision_id"] == 9, "infer should return runtime revision")) {
        return 1;
    }
    if (!Expect(infer_payload["result"]["instance_id"] == "face_detect-1", "infer should return leased instance id")) {
        return 1;
    }
    if (!Expect(infer_payload["result"]["fallback_applied"] == false, "infer should report no fallback for gpu path")) {
        return 1;
    }
    if (!Expect(infer_payload["result"]["plugin_result"]["mock"] == true, "infer should include plugin execution result")) {
        return 1;
    }
    if (!Expect(infer_payload["result"]["plugin_result"]["device"] == "cuda", "infer should execute plugin on gpu binding")) {
        return 1;
    }
    if (!Expect(infer_payload["result"]["queue_wait_ms"] == 0, "direct infer should report zero queue wait")) {
        return 1;
    }
    if (!Expect(infer_payload["result"]["queue_wait_timeout_ms"] == 180, "direct infer should expose snapshot queue wait timeout")) {
        return 1;
    }
    if (!Expect(infer_payload["result"]["max_pending_request_count"] == 3, "direct infer should expose snapshot max pending configuration")) {
        return 1;
    }
    if (!Expect(infer_payload["result"]["deadline_ms"] == 700, "infer should expose request deadline")) {
        return 1;
    }
    if (!Expect(infer_payload["result"]["sla_status"] == "ok", "infer should report non-violated sla status")) {
        return 1;
    }
    if (!Expect(infer_payload["result"]["lifecycle_elapsed_ms"] >= infer_payload["result"]["infer_time_ms"], "direct infer should expose lifecycle elapsed time")) {
        return 1;
    }
    if (!Expect(std::filesystem::exists(runtime_log_path), "infer should append runtime log")) {
        return 1;
    }
    if (!Expect(std::filesystem::exists(audit_log_path), "infer should append audit log")) {
        return 1;
    }
    const auto infer_audit_entries = ReadJsonLines(audit_log_path);
    if (!Expect(!infer_audit_entries.empty(), "audit log should contain infer entry")) {
        return 1;
    }
    const auto infer_audit_entry = FindLastAuditAction(infer_audit_entries, "infer");
    if (!Expect(infer_audit_entry.has_value(), "audit log should expose infer action")) {
        return 1;
    }
    if (!Expect((*infer_audit_entry)["action"] == "infer", "audit entry should record infer action")) {
        return 1;
    }
    if (!Expect((*infer_audit_entry)["detail"]["status"] == "success", "infer audit entry should record success status")) {
        return 1;
    }
    if (!Expect((*infer_audit_entry)["detail"]["request_id"] == infer_payload["request_id"], "infer audit entry should preserve request id")) {
        return 1;
    }
    if (!Expect((*infer_audit_entry)["detail"]["correlation_id"] == infer_payload["request_id"], "infer audit entry should preserve correlation id")) {
        return 1;
    }
    if (!Expect((*infer_audit_entry)["detail"]["lifecycle_elapsed_ms"] == infer_payload["result"]["lifecycle_elapsed_ms"], "infer audit entry should preserve lifecycle timing")) {
        return 1;
    }
    const auto deadline_exceeded_result = proxy_client.Post(
        "/api/v1/infer/face_detect",
        "{\"input_type\":\"json\",\"payload\":\"deadline-demo\",\"prefer_deadline_ms\":50,\"options\":{\"simulate_delay_ms\":80}}",
        "application/json");
    if (!Expect(deadline_exceeded_result && deadline_exceeded_result->status == 503, "infer route should reject when request deadline expires before execution")) {
        return 1;
    }
    const auto deadline_metrics_result = proxy_client.Get("/api/v1/admin/metrics");
    if (!Expect(deadline_metrics_result && deadline_metrics_result->status == 200, "metrics should respond after deadline exceeded infer")) {
        return 1;
    }
    const auto deadline_metrics_payload = nlohmann::json::parse(deadline_metrics_result->body);
    if (!Expect(deadline_metrics_payload["endpoint_metrics"]["infer"]["deadline_exceeded_requests"] >= 1, "metrics should count deadline exceeded requests")) {
        return 1;
    }
    if (!Expect(deadline_metrics_payload["request_summary"]["deadline_exceeded_request_count"] >= 1, "request summary should count deadline exceeded requests")) {
        return 1;
    }
    bool found_deadline_pool_metric = false;
    for (const auto& item : deadline_metrics_payload["pool_metrics"]) {
        if (item["capability_name"] != "face_detect") {
            continue;
        }
        found_deadline_pool_metric = item["deadline_exceeded_count"] >= 1;
        break;
    }
    if (!Expect(found_deadline_pool_metric, "pool metrics should count deadline exceeded requests")) {
        return 1;
    }
    const auto deadline_audit_entries = ReadJsonLines(audit_log_path);
    const auto deadline_audit_entry = FindLastAuditAction(deadline_audit_entries, "infer_deadline_exceeded");
    if (!Expect(deadline_audit_entry.has_value(), "audit log should record deadline exceeded infer")) {
        return 1;
    }
    if (!Expect((*deadline_audit_entry)["detail"]["status"] == "failure", "deadline exceeded audit should record failure status")) {
        return 1;
    }
    if (!Expect((*deadline_audit_entry)["detail"]["error_message"] == "请求 SLA 截止时间已超出，未进入执行。", "deadline exceeded audit should preserve error message")) {
        return 1;
    }

    const auto reloaded_catalog_result = proxy_client.Get("/api/v1/admin/catalog");
    if (!Expect(reloaded_catalog_result && reloaded_catalog_result->status == 200, "catalog route should respond after reload")) {
        return 1;
    }
    const auto reloaded_catalog_payload = nlohmann::json::parse(reloaded_catalog_result->body);
    if (!Expect(reloaded_catalog_payload["runtime_revision_id"] == 1, "reload should refresh catalog revision")) {
        return 1;
    }
    if (!Expect(reloaded_catalog_payload["runtime_state"] == "ready", "catalog should return to ready runtime state after reload")) {
        return 1;
    }
    if (!Expect(reloaded_catalog_payload["active_request_count"] == 0, "catalog should clear active requests after reload")) {
        return 1;
    }
    if (!Expect(reloaded_catalog_payload["items"][0]["pool_size"] == 2, "reload should rebuild pool size from new snapshot")) {
        return 1;
    }
    if (!Expect(reloaded_catalog_payload["items"][0]["max_batch_size"] == 5, "reload should expose refreshed max batch size")) {
        return 1;
    }
    if (!Expect(reloaded_catalog_payload["items"][0]["capability_priority"] == 140, "reload should expose refreshed capability priority")) {
        return 1;
    }
    if (!Expect(reloaded_catalog_payload["items"][0]["queue_wait_timeout_ms"] == 220, "reload should expose refreshed queue wait timeout")) {
        return 1;
    }
    if (!Expect(reloaded_catalog_payload["items"][0]["configured_max_pending_request_count"] == 4, "reload should expose refreshed max pending configuration")) {
        return 1;
    }
    if (!Expect(reloaded_catalog_payload["draining"] == false, "catalog should leave draining state after reload")) {
        return 1;
    }
    if (!Expect(reloaded_catalog_payload["items"].size() == 3, "reload should publish merged capabilities")) {
        return 1;
    }
    const auto ocr_infer_result = proxy_client.Post(
        "/api/v1/infer/ocr",
        ("{\"input_type\":\"image\",\"payload\":\"" + SamplePngBase64() + "\"}").c_str(),
        "application/json");
    if (!Expect(ocr_infer_result && ocr_infer_result->status == 200, "reload should enable plugin execution for image capability")) {
        return 1;
    }
    const auto ocr_infer_payload = nlohmann::json::parse(ocr_infer_result->body);
    if (!Expect(ocr_infer_payload["result"]["plugin_result"]["mock"] == true, "ocr infer should use plugin result")) {
        return 1;
    }
    if (!Expect(ocr_infer_payload["result"]["input_metadata"]["detected_format"] == "png", "image infer should expose decoded input metadata")) {
        return 1;
    }
    if (!Expect(ocr_infer_payload["result"]["payload_size"] == 8, "image infer should report decoded payload size")) {
        return 1;
    }
    const auto invalid_image_infer_result = proxy_client.Post(
        "/api/v1/infer/ocr",
        "{\"input_type\":\"image\",\"payload\":\"demo-ocr\"}",
        "application/json");
    if (!Expect(invalid_image_infer_result && invalid_image_infer_result->status == 400, "invalid image payload should be rejected by codec")) {
        return 1;
    }
    const auto pdf_infer_result = proxy_client.Post(
        "/api/v1/infer/ocr",
        ("{\"input_type\":\"pdf\",\"payload\":\"" + SamplePdfBase64() + "\"}").c_str(),
        "application/json");
    if (!Expect(pdf_infer_result && pdf_infer_result->status == 200, "pdf infer should be accepted after codec decode")) {
        return 1;
    }
    const auto pdf_infer_payload = nlohmann::json::parse(pdf_infer_result->body);
    if (!Expect(pdf_infer_payload["result"]["input_metadata"]["detected_format"] == "pdf", "pdf infer should expose decoded format metadata")) {
        return 1;
    }
    const auto fallback_infer_result = proxy_client.Post(
        "/api/v1/infer/pose_estimate",
        "{\"input_type\":\"json\",\"payload\":\"demo-fallback\",\"prefer_device\":\"gpu\",\"prefer_deadline_ms\":500}",
        "application/json");
    if (!Expect(fallback_infer_result && fallback_infer_result->status == 200, "gpu lifecycle failure should fallback to cpu")) {
        return 1;
    }
    const auto fallback_infer_payload = nlohmann::json::parse(fallback_infer_result->body);
    if (!Expect(fallback_infer_payload["requested_device"] == "gpu", "fallback infer should preserve requested device")) {
        return 1;
    }
    if (!Expect(fallback_infer_payload["device"] == "cpu", "fallback infer should execute on cpu")) {
        return 1;
    }
    if (!Expect(fallback_infer_payload["result"]["fallback_applied"] == true, "fallback infer should mark fallback applied")) {
        return 1;
    }
    if (!Expect(fallback_infer_payload["result"]["plugin_result"]["device"] == "cpu", "fallback infer should use cpu plugin binding")) {
        return 1;
    }
    if (!Expect(fallback_infer_payload["result"]["fallback_reason"] == "能力插件健康检查失败。", "fallback infer should expose lifecycle fallback reason")) {
        return 1;
    }
    if (!Expect(fallback_infer_payload["result"]["deadline_ms"] == 500, "fallback infer should expose request deadline")) {
        return 1;
    }
    if (!Expect(fallback_infer_payload["result"]["sla_status"] == "ok", "fallback infer should preserve ok sla status")) {
        return 1;
    }
    if (!Expect(fallback_infer_payload["result"]["lifecycle_elapsed_ms"] >= fallback_infer_payload["result"]["infer_time_ms"], "fallback infer should expose lifecycle elapsed time")) {
        return 1;
    }
    const auto metrics_catalog_result = proxy_client.Get("/api/v1/admin/catalog");
    if (!Expect(metrics_catalog_result && metrics_catalog_result->status == 200, "catalog should respond after metrics-producing infer")) {
        return 1;
    }
    const auto metrics_catalog_payload = nlohmann::json::parse(metrics_catalog_result->body);
    bool found_ocr_metrics = false;
    for (const auto& item : metrics_catalog_payload["items"]) {
        if (item["capability_name"] != "ocr") {
            continue;
        }
        found_ocr_metrics = true;
        if (!Expect(!item["execution_metrics"].is_null(), "catalog should expose execution metrics after infer")) {
            return 1;
        }
        if (!Expect(item["execution_metrics"]["total_requests"] == 2, "catalog metrics should count executed requests")) {
            return 1;
        }
        if (!Expect(item["execution_metrics"]["successful_requests"] == 2, "catalog metrics should count successful requests")) {
            return 1;
        }
        if (!Expect(item["execution_metrics"]["max_batch_size"] == 3, "catalog metrics should expose capability max batch size")) {
            return 1;
        }
        if (!Expect(item["execution_metrics"]["avg_lifecycle_time_ms"] >= item["execution_metrics"]["avg_infer_time_ms"], "catalog metrics should expose lifecycle latency aggregate")) {
            return 1;
        }
        if (!Expect(item["execution_metrics"]["bindings"][0]["plugin_info"]["capability_id"] == "mock_capability", "catalog metrics should expose plugin info")) {
            return 1;
        }
        if (!Expect(item["execution_metrics"]["warmup_status"] == "passed", "catalog metrics should expose successful warmup status")) {
            return 1;
        }
        if (!Expect(item["execution_metrics"]["health_check_status"] == "passed", "catalog metrics should expose successful health status")) {
            return 1;
        }
        if (!Expect(!item["execution_metrics"]["last_warmup_at_utc"].is_null(), "catalog metrics should expose warmup timestamp")) {
            return 1;
        }
        if (!Expect(!item["execution_metrics"]["last_health_check_at_utc"].is_null(), "catalog metrics should expose health timestamp")) {
            return 1;
        }
    }
    if (!Expect(found_ocr_metrics, "catalog should include ocr metrics entry")) {
        return 1;
    }
    bool found_fallback_metrics = false;
    for (const auto& item : metrics_catalog_payload["items"]) {
        if (item["capability_name"] != "pose_estimate") {
            continue;
        }
        found_fallback_metrics = true;
        if (!Expect(item["execution_metrics"]["fallback_count"] == 1, "catalog metrics should count gpu to cpu fallback")) {
            return 1;
        }
        if (!Expect(item["execution_metrics"]["last_fallback_reason"] == "能力插件健康检查失败。", "catalog metrics should expose last fallback reason")) {
            return 1;
        }
        if (!Expect(item["execution_metrics"]["avg_lifecycle_time_ms"] >= item["execution_metrics"]["avg_infer_time_ms"], "fallback metrics should expose lifecycle latency aggregate")) {
            return 1;
        }
    }
    if (!Expect(found_fallback_metrics, "catalog should include fallback metrics entry")) {
        return 1;
    }

    const auto runtime_metrics_result = proxy_client.Get("/api/v1/admin/metrics");
    if (!Expect(runtime_metrics_result && runtime_metrics_result->status == 200, "metrics route should respond after infer")) {
        return 1;
    }
    const auto runtime_metrics_payload = nlohmann::json::parse(runtime_metrics_result->body);
    if (!Expect(runtime_metrics_payload["request_summary"]["capability_total_requests"] >= 3, "metrics should aggregate capability request totals")) {
        return 1;
    }
    if (!Expect(runtime_metrics_payload["endpoint_metrics"]["infer"]["total_requests"] >= 6, "metrics should count infer attempts")) {
        return 1;
    }
    if (!Expect(runtime_metrics_payload["endpoint_metrics"]["infer"]["failed_requests"] >= 3, "metrics should count failed infer attempts")) {
        return 1;
    }
    if (!Expect(runtime_metrics_payload["pool_summary"]["total_pool_slots"] == 6, "metrics should expose total pool slots after reload")) {
        return 1;
    }
    if (!Expect(runtime_metrics_payload["endpoint_metrics"]["admin_reload"]["successful_requests"] == 1, "metrics should count successful reload")) {
        return 1;
    }
    bool found_fallback_capability_metrics = false;
    for (const auto& item : runtime_metrics_payload["capability_metrics"]) {
        if (item["capability_name"] != "pose_estimate") {
            continue;
        }
        found_fallback_capability_metrics = true;
        if (!Expect(item["execution_metrics"]["fallback_count"] == 1, "runtime metrics should expose fallback count")) {
            return 1;
        }
        if (!Expect(item["execution_metrics"]["avg_lifecycle_time_ms"] >= item["execution_metrics"]["avg_infer_time_ms"], "runtime metrics should expose lifecycle latency aggregate")) {
            return 1;
        }
    }
    if (!Expect(found_fallback_capability_metrics, "runtime metrics should include fallback capability")) {
        return 1;
    }

    license_payload["capability_scope"] = nlohmann::json::array({"ocr"});
    test_license_helpers::WriteLicenseBundle(license_root, license_payload);
    const auto license_reload_result = proxy_client.Post(
        "/api/v1/admin/license-reload",
        "{}",
        "application/json");
    if (!Expect(license_reload_result && license_reload_result->status == 200, "license reload route should succeed")) {
        return 1;
    }
    const auto license_reload_audit_entries = ReadJsonLines(audit_log_path);
    const auto license_reload_audit_entry = FindLastAuditAction(license_reload_audit_entries, "license_reload");
    if (!Expect(license_reload_audit_entry.has_value(), "audit log should record license reload")) {
        return 1;
    }
    if (!Expect((*license_reload_audit_entry)["detail"]["status"] == "success", "license reload audit should record success status")) {
        return 1;
    }
    const auto denied_infer_result = proxy_client.Post(
        "/api/v1/infer/face_detect",
        "{\"input_type\":\"json\",\"payload\":\"demo-license\"}",
        "application/json");
    if (!Expect(denied_infer_result && denied_infer_result->status == 403, "infer route should reject capability outside license scope")) {
        return 1;
    }
    const auto denied_infer_payload = nlohmann::json::parse(denied_infer_result->body);
    if (!Expect(denied_infer_payload["license_status"]["code"] == "capability_scope_denied", "infer rejection should expose stable code")) {
        return 1;
    }
    const auto denied_reload_result = proxy_client.Post(
        "/api/v1/admin/reload",
        "{\"action\":\"reload\"}",
        "application/json");
    if (!Expect(denied_reload_result && denied_reload_result->status == 403, "reload route should reject invalid license status")) {
        return 1;
    }
    const auto denied_reload_payload = nlohmann::json::parse(denied_reload_result->body);
    if (!Expect(denied_reload_payload["license_status"]["code"] == "capability_scope_denied", "reload rejection should expose stable code")) {
        return 1;
    }
    license_payload["capability_scope"] = nlohmann::json::array({"face_detect", "ocr", "pose_estimate"});
    test_license_helpers::WriteLicenseBundle(license_root, license_payload);
    const auto restore_license_result = proxy_client.Post(
        "/api/v1/admin/license-reload",
        "{}",
        "application/json");
    if (!Expect(restore_license_result && restore_license_result->status == 200, "license reload should restore valid license")) {
        return 1;
    }

    const auto reload_payload = nlohmann::json::parse(reload_body);
    if (!Expect(reload_payload["revision"]["revision_id"] == 1, "reload response should expose new revision id")) {
        return 1;
    }

    std::filesystem::remove(snapshot_path);
    const auto missing_snapshot_health_result = proxy_client.Get("/api/v1/health");
    if (!Expect(missing_snapshot_health_result && missing_snapshot_health_result->status == 503, "health route should reject missing runtime snapshot")) {
        return 1;
    }
    const auto missing_snapshot_health_payload = nlohmann::json::parse(missing_snapshot_health_result->body);
    if (!Expect(missing_snapshot_health_payload["status"] == "error", "health route should return structured error when snapshot is missing")) {
        return 1;
    }
    const auto stale_catalog_result = proxy_client.Get("/api/v1/admin/catalog");
    if (!Expect(stale_catalog_result && stale_catalog_result->status == 200, "catalog route should still respond without snapshot")) {
        return 1;
    }
    const auto stale_catalog_payload = nlohmann::json::parse(stale_catalog_result->body);
    if (!Expect(stale_catalog_payload["snapshot_ready"] == false, "catalog route should mark snapshot unavailable")) {
        return 1;
    }
    const auto missing_snapshot_infer_result = proxy_client.Post(
        "/api/v1/infer/face_detect",
        "{\"input_type\":\"json\",\"payload\":\"demo-after-snapshot-remove\"}",
        "application/json");
    if (!Expect(missing_snapshot_infer_result && missing_snapshot_infer_result->status == 503, "infer should reject when runtime snapshot is unavailable")) {
        return 1;
    }

    const auto rollback_result = proxy_client.Post(
        "/api/v1/admin/rollback",
        "{\"target_revision_id\":1}",
        "application/json");
    if (!Expect(rollback_result && rollback_result->status == 200, "rollback route should execute successfully")) {
        proxy_server.Stop();
        backend_server.stop();
        proxy_thread.join();
        backend_thread.join();
        return 1;
    }

    const auto rollback_payload = nlohmann::json::parse(rollback_result->body);
    if (!Expect(rollback_payload["revision"]["action"] == "rollback", "rollback response should mark action")) {
        proxy_server.Stop();
        backend_server.stop();
        proxy_thread.join();
        backend_thread.join();
        return 1;
    }
    if (!Expect(rollback_payload["revision"]["rollback_of_revision_id"] == 1, "rollback should preserve target revision id")) {
        proxy_server.Stop();
        backend_server.stop();
        proxy_thread.join();
        backend_thread.join();
        return 1;
    }

    const auto rollback_catalog_result = proxy_client.Get("/api/v1/admin/catalog");
    if (!Expect(rollback_catalog_result && rollback_catalog_result->status == 200, "catalog should respond after rollback")) {
        proxy_server.Stop();
        backend_server.stop();
        proxy_thread.join();
        backend_thread.join();
        return 1;
    }
    const auto rollback_catalog_payload = nlohmann::json::parse(rollback_catalog_result->body);
    if (!Expect(rollback_catalog_payload["runtime_revision_id"] == 2, "rollback should refresh catalog revision")) {
        proxy_server.Stop();
        backend_server.stop();
        proxy_thread.join();
        backend_thread.join();
        return 1;
    }

    proxy_server.Stop();
    backend_server.stop();
    proxy_thread.join();
    backend_thread.join();
    std::filesystem::remove_all(license_root);
    std::filesystem::remove_all(host_root);
    std::filesystem::remove_all(image_root);
    std::filesystem::remove(database_path);
    std::filesystem::remove(runtime_log_path);
    std::filesystem::remove(audit_log_path);
    return 0;
}
