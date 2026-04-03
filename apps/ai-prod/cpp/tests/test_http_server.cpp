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

void WriteSnapshot(
    const std::filesystem::path& snapshot_path,
    int revision_id,
    int pool_size) {
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
        << "\"model_version\":\"v1_0_0\","
        << "\"backend_type\":\"onnxruntime\","
        << "\"active_source\":\"host\","
        << "\"device_mode\":\"gpu/cpu\","
        << "\"pool_size\":" << pool_size << ","
        << "\"revision_id\":" << revision_id
        << "}],"
        << "\"license_status\":{"
        << "\"valid\":true,"
        << "\"reason\":\"ok\","
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

}

int main() {
    const std::filesystem::path snapshot_path = std::filesystem::temp_directory_path() / "ai_prod_cpp_runtime_snapshot_test.json";
    WriteSnapshot(snapshot_path, 9, 1);
    const std::filesystem::path license_root = std::filesystem::temp_directory_path() / "ai_prod_cpp_runtime_license_test";
    const std::filesystem::path runtime_log_path = std::filesystem::temp_directory_path() / "ai_prod_cpp_runtime_test.log";
    const std::filesystem::path audit_log_path = std::filesystem::temp_directory_path() / "ai_prod_cpp_audit_test.log";
    std::filesystem::remove_all(license_root);
    std::filesystem::remove(runtime_log_path);
    std::filesystem::remove(audit_log_path);
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

    if (!Expect(
            AiProdBackendClient::NormalizeRollbackBody("{}") == "{\"action\":\"rollback\"}",
            "rollback normalization should add action")) {
        return 1;
    }

    const int backend_port = 29104;
    const int proxy_port = 29105;
    std::string forwarded_reload_body;
    std::atomic<bool> reload_called(false);
    std::atomic<int> reload_call_count(0);

    httplib::Server backend_server;
    backend_server.Get("/api/v1/health", [](const httplib::Request&, httplib::Response& response) {
        response.set_content("{\"status\":\"ok\",\"service\":\"backend\"}", "application/json");
    });
    backend_server.Post("/api/v1/admin/reload", [&](const httplib::Request& request, httplib::Response& response) {
        forwarded_reload_body = request.body;
        reload_called = true;
        ++reload_call_count;
        const auto payload = nlohmann::json::parse(request.body.empty() ? "{}" : request.body);
        if (payload.value("action", "reload") == "rollback") {
            WriteSnapshot(snapshot_path, 11, 1);
        } else {
            WriteSnapshot(snapshot_path, 10, 2);
        }
        response.set_content(request.body, "application/json");
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
    config.license_root = license_root.string();
    config.hardware_features = hardware_features;
    config.license_auto_reload_interval_seconds = 1;
    config.runtime_snapshot_path = snapshot_path.string();
    config.runtime_log_path = runtime_log_path.string();
    config.audit_log_path = audit_log_path.string();
    config.connect_timeout_ms = 1000;
    config.read_timeout_ms = 1000;
    config.write_timeout_ms = 1000;
    config.snapshot_max_age_seconds = 60;

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
    if (!Expect(catalog_payload["items"].size() == 1, "catalog route should expose one capability")) {
        return 1;
    }
    if (!Expect(catalog_payload["items"][0]["busy_count"] == 0, "catalog busy count should default to zero")) {
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
    if (!Expect(license_status_payload["capability_scope"].size() == 1, "license status should expose capability scope")) {
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

    std::optional<int> infer_status;
    std::string infer_body;
    std::thread infer_thread([&]() {
        httplib::Client infer_client("127.0.0.1", proxy_port);
        const auto infer_result = infer_client.Post(
            "/api/v1/infer/face_detect",
            "{\"input_type\":\"json\",\"payload\":\"demo\",\"prefer_device\":\"gpu\",\"options\":{\"simulate_delay_ms\":400}}",
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

    std::optional<int> reload_status;
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
    });
    std::this_thread::sleep_for(std::chrono::milliseconds(150));
    if (!Expect(!reload_called.load(), "reload should wait for in-flight infer to drain before forwarding")) {
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
    if (!Expect(draining_catalog_payload["items"][0]["draining"] == true, "catalog item should show draining state")) {
        reload_thread.join();
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
    if (!Expect(reload_call_count.load() == 1, "reload should be forwarded exactly once")) {
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
    if (!Expect(std::filesystem::exists(runtime_log_path), "infer should append runtime log")) {
        return 1;
    }
    if (!Expect(std::filesystem::exists(audit_log_path), "infer should append audit log")) {
        return 1;
    }

    const auto reloaded_catalog_result = proxy_client.Get("/api/v1/admin/catalog");
    if (!Expect(reloaded_catalog_result && reloaded_catalog_result->status == 200, "catalog route should respond after reload")) {
        return 1;
    }
    const auto reloaded_catalog_payload = nlohmann::json::parse(reloaded_catalog_result->body);
    if (!Expect(reloaded_catalog_payload["runtime_revision_id"] == 10, "reload should refresh catalog revision")) {
        return 1;
    }
    if (!Expect(reloaded_catalog_payload["items"][0]["pool_size"] == 2, "reload should rebuild pool size from new snapshot")) {
        return 1;
    }
    if (!Expect(reloaded_catalog_payload["draining"] == false, "catalog should leave draining state after reload")) {
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
    const auto denied_infer_result = proxy_client.Post(
        "/api/v1/infer/face_detect",
        "{\"input_type\":\"json\",\"payload\":\"demo-license\"}",
        "application/json");
    if (!Expect(denied_infer_result && denied_infer_result->status == 403, "infer route should reject capability outside license scope")) {
        return 1;
    }
    const auto denied_reload_result = proxy_client.Post(
        "/api/v1/admin/reload",
        "{\"action\":\"reload\"}",
        "application/json");
    if (!Expect(denied_reload_result && denied_reload_result->status == 403, "reload route should reject invalid license status")) {
        return 1;
    }
    license_payload["capability_scope"] = nlohmann::json::array({"face_detect"});
    test_license_helpers::WriteLicenseBundle(license_root, license_payload);
    const auto restore_license_result = proxy_client.Post(
        "/api/v1/admin/license-reload",
        "{}",
        "application/json");
    if (!Expect(restore_license_result && restore_license_result->status == 200, "license reload should restore valid license")) {
        return 1;
    }

    std::filesystem::remove(snapshot_path);
    const auto fallback_health_result = proxy_client.Get("/api/v1/health");
    if (!Expect(fallback_health_result && fallback_health_result->status == 200, "health route should fallback to backend")) {
        return 1;
    }
    const auto fallback_health_payload = nlohmann::json::parse(fallback_health_result->body);
    if (!Expect(fallback_health_payload["service"] == "backend", "health fallback should use backend payload")) {
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

    const auto rollback_result = proxy_client.Post(
        "/api/v1/admin/rollback",
        "{\"target_revision_id\":7}",
        "application/json");
    if (!Expect(rollback_result && rollback_result->status == 200, "rollback route should proxy successfully")) {
        proxy_server.Stop();
        backend_server.stop();
        proxy_thread.join();
        backend_thread.join();
        return 1;
    }

    const auto payload = nlohmann::json::parse(forwarded_reload_body);
    if (!Expect(payload["action"] == "rollback", "rollback route should force action=rollback")) {
        proxy_server.Stop();
        backend_server.stop();
        proxy_thread.join();
        backend_thread.join();
        return 1;
    }
    if (!Expect(payload["target_revision_id"] == 7, "rollback route should preserve target revision")) {
        proxy_server.Stop();
        backend_server.stop();
        proxy_thread.join();
        backend_thread.join();
        return 1;
    }
    if (!Expect(reload_call_count.load() == 2, "rollback should also be forwarded through reload endpoint")) {
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
    if (!Expect(rollback_catalog_payload["runtime_revision_id"] == 11, "rollback should refresh catalog revision")) {
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
    std::filesystem::remove(runtime_log_path);
    std::filesystem::remove(audit_log_path);
    return 0;
}
