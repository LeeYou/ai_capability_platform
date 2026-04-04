#include "proxy_config.h"

#include <nlohmann/json.hpp>

#include <cstdlib>
#include <stdexcept>

namespace {

std::string read_string_env(const char* name, const std::string& default_value) {
    const char* value = std::getenv(name);
    if (value == nullptr || *value == '\0') {
        return default_value;
    }
    return value;
}

int read_int_env(const char* name, int default_value, int minimum_value) {
    const char* value = std::getenv(name);
    if (value == nullptr || *value == '\0') {
        return default_value;
    }

    try {
        const int parsed_value = std::stoi(value);
        if (parsed_value < minimum_value) {
            return default_value;
        }
        return parsed_value;
    } catch (const std::exception&) {
        return default_value;
    }
}

std::map<std::string, std::string> read_hardware_features_env(const char* name) {
    std::map<std::string, std::string> features;
    const char* value = std::getenv(name);
    if (value == nullptr || *value == '\0') {
        return features;
    }

    try {
        const auto payload = nlohmann::json::parse(value);
        if (!payload.is_object()) {
            return features;
        }
        for (auto it = payload.begin(); it != payload.end(); ++it) {
            if (it.value().is_string()) {
                features.emplace(it.key(), it.value().get<std::string>());
            } else if (it.value().is_number_integer()) {
                features.emplace(it.key(), std::to_string(it.value().get<long long>()));
            } else if (it.value().is_number_float()) {
                features.emplace(it.key(), std::to_string(it.value().get<double>()));
            } else if (it.value().is_boolean()) {
                features.emplace(it.key(), it.value().get<bool>() ? "true" : "false");
            }
        }
    } catch (const std::exception&) {
        return {};
    }
    return features;
}

}

ProxyConfig load_proxy_config_from_env() {
    ProxyConfig config;
    config.bind_host = read_string_env("AI_PROD_CPP_BIND_HOST", config.bind_host);
    config.bind_port = read_int_env("AI_PROD_CPP_BIND_PORT", config.bind_port, 1);
    config.backend_host = read_string_env("AI_PROD_PY_BACKEND_HOST", config.backend_host);
    config.backend_port = read_int_env("AI_PROD_PY_BACKEND_PORT", config.backend_port, 1);
    config.host_root = read_string_env("AI_CAP_HOST_ROOT", config.host_root);
    config.image_resource_root = read_string_env("AI_PROD_CPP_IMAGE_RESOURCE_ROOT", config.image_resource_root);
    config.license_root = read_string_env("AI_PROD_CPP_LICENSE_ROOT", config.host_root + "/license");
    config.database_path = read_string_env("AI_CAP_DATABASE_PATH", config.host_root + "/data/ai_prod.db");
    config.runtime_snapshot_path = read_string_env("AI_PROD_CPP_RUNTIME_SNAPSHOT_PATH", config.runtime_snapshot_path);
    config.runtime_log_path = read_string_env("AI_PROD_CPP_RUNTIME_LOG_PATH", config.host_root + "/logs/ai_prod_runtime.log");
    config.audit_log_path = read_string_env("AI_PROD_CPP_AUDIT_LOG_PATH", config.host_root + "/logs/ai_prod_audit.log");
    config.pool_size = read_int_env("AI_PROD_CPP_POOL_SIZE", config.pool_size, 1);
    config.gpu_available = read_string_env("AI_CAP_GPU_AVAILABLE", "1") != "0";
    config.connect_timeout_ms = read_int_env("AI_PROD_CPP_CONNECT_TIMEOUT_MS", config.connect_timeout_ms, 1);
    config.read_timeout_ms = read_int_env("AI_PROD_CPP_READ_TIMEOUT_MS", config.read_timeout_ms, 1);
    config.write_timeout_ms = read_int_env("AI_PROD_CPP_WRITE_TIMEOUT_MS", config.write_timeout_ms, 1);
    config.snapshot_max_age_seconds = read_int_env(
        "AI_PROD_CPP_SNAPSHOT_MAX_AGE_SECONDS",
        config.snapshot_max_age_seconds,
        1);
    config.license_auto_reload_interval_seconds = read_int_env(
        "AI_PROD_CPP_LICENSE_AUTO_RELOAD_INTERVAL_SECONDS",
        config.license_auto_reload_interval_seconds,
        1);
    config.infer_queue_wait_timeout_ms = read_int_env(
        "AI_PROD_CPP_INFER_QUEUE_WAIT_TIMEOUT_MS",
        config.infer_queue_wait_timeout_ms,
        0);
    config.infer_queue_max_pending_requests = read_int_env(
        "AI_PROD_CPP_INFER_QUEUE_MAX_PENDING_REQUESTS",
        config.infer_queue_max_pending_requests,
        1);
    config.infer_request_max_deadline_ms = read_int_env(
        "AI_PROD_CPP_INFER_REQUEST_MAX_DEADLINE_MS",
        config.infer_request_max_deadline_ms,
        1);
    config.hardware_features = read_hardware_features_env("AI_CAP_HARDWARE_FEATURES");
    return config;
}

std::string build_backend_base_url(const ProxyConfig& config) {
    return "http://" + config.backend_host + ":" + std::to_string(config.backend_port);
}
