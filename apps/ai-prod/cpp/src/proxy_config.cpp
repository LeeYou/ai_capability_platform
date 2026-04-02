#include "proxy_config.h"

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

}

ProxyConfig load_proxy_config_from_env() {
    ProxyConfig config;
    config.bind_host = read_string_env("AI_PROD_CPP_BIND_HOST", config.bind_host);
    config.bind_port = read_int_env("AI_PROD_CPP_BIND_PORT", config.bind_port, 1);
    config.backend_host = read_string_env("AI_PROD_PY_BACKEND_HOST", config.backend_host);
    config.backend_port = read_int_env("AI_PROD_PY_BACKEND_PORT", config.backend_port, 1);
    config.connect_timeout_ms = read_int_env("AI_PROD_CPP_CONNECT_TIMEOUT_MS", config.connect_timeout_ms, 1);
    config.read_timeout_ms = read_int_env("AI_PROD_CPP_READ_TIMEOUT_MS", config.read_timeout_ms, 1);
    config.write_timeout_ms = read_int_env("AI_PROD_CPP_WRITE_TIMEOUT_MS", config.write_timeout_ms, 1);
    return config;
}

std::string build_backend_base_url(const ProxyConfig& config) {
    return "http://" + config.backend_host + ":" + std::to_string(config.backend_port);
}
