#include "proxy_config.h"

#include <nlohmann/json.hpp>

#include <cctype>
#include <cstdlib>
#include <string>
#include <stdexcept>

#ifndef _WIN32
#include <sys/utsname.h>
#endif

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

std::string detect_operating_system() {
#ifdef _WIN32
    return "windows";
#else
    struct utsname info {};
    if (uname(&info) == 0) {
        std::string system_name = info.sysname;
        for (char& ch : system_name) {
            ch = static_cast<char>(std::tolower(static_cast<unsigned char>(ch)));
        }
        if (system_name == "linux") {
            return "linux";
        }
    }
    return "linux";
#endif
}

std::string detect_operating_system_version() {
#ifdef _WIN32
    const char* env_value = std::getenv("OS");
    return env_value != nullptr ? std::string(env_value) : std::string();
#else
    struct utsname info {};
    return uname(&info) == 0 ? std::string(info.release) : std::string();
#endif
}

std::string detect_system_architecture() {
#ifdef _WIN32
#if defined(_M_X64) || defined(_M_AMD64)
    return "x86_64";
#elif defined(_M_IX86)
    return "x86";
#elif defined(_M_ARM64)
    return "arm64";
#else
    return "x86_64";
#endif
#else
    struct utsname info {};
    if (uname(&info) != 0) {
        return "x86_64";
    }
    std::string machine = info.machine;
    if (machine == "amd64") {
        return "x86_64";
    }
    if (machine == "aarch64") {
        return "arm64";
    }
    return machine;
#endif
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
    config.infer_batch_wait_timeout_ms = read_int_env(
        "AI_PROD_CPP_INFER_BATCH_WAIT_TIMEOUT_MS",
        config.infer_batch_wait_timeout_ms,
        0);
    config.infer_request_max_deadline_ms = read_int_env(
        "AI_PROD_CPP_INFER_REQUEST_MAX_DEADLINE_MS",
        config.infer_request_max_deadline_ms,
        1);
    config.operating_system = read_string_env("AI_CAP_OPERATING_SYSTEM", detect_operating_system());
    config.operating_system_version = read_string_env("AI_CAP_OPERATING_SYSTEM_VERSION", detect_operating_system_version());
    config.system_architecture = read_string_env("AI_CAP_SYSTEM_ARCHITECTURE", detect_system_architecture());
    config.application_name = read_string_env("AI_CAP_APPLICATION_NAME", config.application_name);
    config.hardware_features = read_hardware_features_env("AI_CAP_HARDWARE_FEATURES");
    return config;
}

std::string build_backend_base_url(const ProxyConfig& config) {
    return "http://" + config.backend_host + ":" + std::to_string(config.backend_port);
}
