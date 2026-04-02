#include "backend_client.h"
#include "http_server.h"
#include "proxy_config.h"

#include <cpp-httplib/httplib.h>
#include <nlohmann/json.hpp>

#include <chrono>
#include <cstdlib>
#include <filesystem>
#include <fstream>
#include <iostream>
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
            << "\"pool_size\":2,"
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

    httplib::Server backend_server;
    backend_server.Get("/api/v1/health", [](const httplib::Request&, httplib::Response& response) {
        response.set_content("{\"status\":\"ok\",\"service\":\"backend\"}", "application/json");
    });
    backend_server.Post("/api/v1/admin/reload", [&](const httplib::Request& request, httplib::Response& response) {
        forwarded_reload_body = request.body;
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

    std::filesystem::remove(snapshot_path);
    const auto fallback_health_result = proxy_client.Get("/api/v1/health");
    if (!Expect(fallback_health_result && fallback_health_result->status == 200, "health route should fallback to backend")) {
        return 1;
    }
    const auto fallback_health_payload = nlohmann::json::parse(fallback_health_result->body);
    if (!Expect(fallback_health_payload["service"] == "backend", "health fallback should use backend payload")) {
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
