#include "backend_client.h"
#include "http_server.h"
#include "proxy_config.h"

#include <cpp-httplib/httplib.h>
#include <nlohmann/json.hpp>

#include <chrono>
#include <atomic>
#include <cstdlib>
#include <filesystem>
#include <fstream>
#include <iostream>
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

}

int main() {
    const std::filesystem::path snapshot_path = std::filesystem::temp_directory_path() / "ai_prod_cpp_runtime_snapshot_test.json";
    {
        std::ofstream snapshot_output(snapshot_path);
        snapshot_output
            << "{"
            << "\"revision_id\":9,"
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
            << "\"pool_size\":1,"
            << "\"revision_id\":9"
            << "}],"
            << "\"license_status\":{"
            << "\"valid\":true,"
            << "\"reason\":\"ok\","
            << "\"checked_at_cst\":\"2026-04-02T17:00:00+08:00\","
            << "\"customer_code\":\"cust_prod\","
            << "\"capability_scope\":[\"face_detect\"],"
            << "\"version_constraints\":{},"
            << "\"hardware_fingerprint\":\"abc\","
            << "\"runtime_revision_id\":9"
            << "}"
            << "}";
    }

    if (!Expect(
            AiProdBackendClient::NormalizeRollbackBody("{}") == "{\"action\":\"rollback\"}",
            "rollback normalization should add action")) {
        return 1;
    }

    const int backend_port = 29104;
    const int proxy_port = 29105;
    std::string forwarded_reload_body;
    std::string forwarded_infer_instance_id;
    std::string forwarded_infer_device;
    std::string forwarded_infer_revision;
    std::atomic<bool> hold_infer(false);
    std::atomic<bool> infer_started(false);

    httplib::Server backend_server;
    backend_server.Get("/api/v1/health", [](const httplib::Request&, httplib::Response& response) {
        response.set_content("{\"status\":\"ok\",\"service\":\"backend\"}", "application/json");
    });
    backend_server.Post("/api/v1/admin/reload", [&](const httplib::Request& request, httplib::Response& response) {
        forwarded_reload_body = request.body;
        response.set_content(request.body, "application/json");
    });
    backend_server.Post(R"(/api/v1/infer/([^/]+))", [&](const httplib::Request& request, httplib::Response& response) {
        forwarded_infer_instance_id = request.get_header_value("X-AI-Prod-Instance-Id");
        forwarded_infer_device = request.get_header_value("X-AI-Prod-Preferred-Device");
        forwarded_infer_revision = request.get_header_value("X-AI-Prod-Runtime-Revision-Id");
        infer_started = true;
        while (hold_infer.load()) {
            std::this_thread::sleep_for(std::chrono::milliseconds(10));
        }
        nlohmann::json payload = {
            {"status", "ok"},
            {"capability_name", request.matches[1].str()},
            {"instance_id", forwarded_infer_instance_id},
            {"preferred_device", forwarded_infer_device},
            {"runtime_revision_id", forwarded_infer_revision},
        };
        response.set_content(payload.dump(), "application/json");
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
    config.runtime_snapshot_path = snapshot_path.string();
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

    hold_infer = true;
    std::optional<int> infer_status;
    std::string infer_body;
    std::thread infer_thread([&]() {
        httplib::Client infer_client("127.0.0.1", proxy_port);
        const auto infer_result = infer_client.Post(
            "/api/v1/infer/face_detect",
            "{\"input\":\"demo\"}",
            "application/json");
        if (!infer_result) {
            infer_status = 0;
            return;
        }
        infer_status = infer_result->status;
        infer_body = infer_result->body;
    });

    for (int attempt = 0; attempt < 50 && !infer_started.load(); ++attempt) {
        std::this_thread::sleep_for(std::chrono::milliseconds(20));
    }
    if (!Expect(infer_started.load(), "infer request should enter backend")) {
        hold_infer = false;
        infer_thread.join();
        return 1;
    }

    const auto busy_catalog_result = proxy_client.Get("/api/v1/admin/catalog");
    if (!Expect(busy_catalog_result && busy_catalog_result->status == 200, "catalog route should respond during infer")) {
        hold_infer = false;
        infer_thread.join();
        return 1;
    }
    const auto busy_catalog_payload = nlohmann::json::parse(busy_catalog_result->body);
    if (!Expect(busy_catalog_payload["items"][0]["busy_count"] == 1, "catalog busy count should reflect in-flight infer")) {
        hold_infer = false;
        infer_thread.join();
        return 1;
    }

    const auto busy_infer_result = proxy_client.Post(
        "/api/v1/infer/face_detect",
        "{\"input\":\"demo-2\"}",
        "application/json");
    if (!Expect(busy_infer_result && busy_infer_result->status == 503, "infer route should reject when pool is busy")) {
        hold_infer = false;
        infer_thread.join();
        return 1;
    }

    const auto missing_infer_result = proxy_client.Post(
        "/api/v1/infer/ocr",
        "{\"input\":\"demo-3\"}",
        "application/json");
    if (!Expect(missing_infer_result && missing_infer_result->status == 404, "infer route should reject unknown capability")) {
        hold_infer = false;
        infer_thread.join();
        return 1;
    }

    hold_infer = false;
    infer_thread.join();
    if (!Expect(infer_status.has_value() && infer_status.value() == 200, "infer route should proxy successfully")) {
        return 1;
    }
    const auto infer_payload = nlohmann::json::parse(infer_body);
    if (!Expect(infer_payload["instance_id"] == "face_detect-1", "infer should forward instance id header")) {
        return 1;
    }
    if (!Expect(infer_payload["preferred_device"] == "gpu", "infer should forward preferred device header")) {
        return 1;
    }
    if (!Expect(infer_payload["runtime_revision_id"] == "9", "infer should forward runtime revision header")) {
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

    proxy_server.Stop();
    backend_server.stop();
    proxy_thread.join();
    backend_thread.join();
    return 0;
}
