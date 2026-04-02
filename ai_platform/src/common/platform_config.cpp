#include "platform_config.h"

#include "app_paths.h"

#include <cstdlib>
#include <filesystem>
#include <fstream>
#include <optional>
#include <string>

namespace ai_platform {
namespace {

struct PlatformServerConfigValues {
    std::optional<std::string> host;
    std::optional<int> port;
    std::optional<int> workers;
    std::optional<int> request_timeout_ms;
    std::optional<int> max_body_size_mb;
    std::optional<int> max_video_size_mb;
    std::optional<int> license_auto_reload_interval_seconds;
    std::optional<std::string> admin_token;
};

struct PlatformPathConfigValues {
    std::optional<std::string> host_plugin_dir;
    std::optional<std::string> host_model_dir;
    std::optional<std::string> host_license_dir;
    std::optional<std::string> host_config_dir;
    std::optional<std::string> host_log_dir;
    std::optional<std::string> builtin_plugin_dir;
    std::optional<std::string> builtin_model_dir;
    std::optional<std::string> builtin_config_dir;
};

std::string trim_copy(const std::string& value) {
    const std::size_t first = value.find_first_not_of(" \t\r\n");
    if (first == std::string::npos) {
        return "";
    }
    const std::size_t last = value.find_last_not_of(" \t\r\n");
    return value.substr(first, last - first + 1);
}

std::string unquote_copy(const std::string& value) {
    if (value.size() >= 2 && ((value.front() == '"' && value.back() == '"') || (value.front() == '\'' && value.back() == '\''))) {
        return value.substr(1, value.size() - 2);
    }
    return value;
}

std::optional<int> parse_int_value(const std::string& value) {
    const std::string trimmed = trim_copy(value);
    if (trimmed.empty()) {
        return std::nullopt;
    }
    try {
        std::size_t parsed_length = 0;
        const int parsed_value = std::stoi(trimmed, &parsed_length);
        if (parsed_length != trimmed.size()) {
            return std::nullopt;
        }
        return parsed_value;
    } catch (const std::exception&) {
        return std::nullopt;
    }
}

PlatformServerConfigValues load_server_config_from_platform_config(const std::string& platform_config_path) {
    PlatformServerConfigValues values;
    std::ifstream input(platform_config_path);
    if (!input.is_open()) {
        return values;
    }

    bool in_server_section = false;
    std::string line;
    while (std::getline(input, line)) {
        const std::size_t indent = line.find_first_not_of(' ');
        const std::string trimmed = trim_copy(line);
        if (trimmed.empty() || trimmed[0] == '#') {
            continue;
        }

        if ((indent == std::string::npos || indent == 0) && trimmed == "server:") {
            in_server_section = true;
            continue;
        }
        if (indent == std::string::npos || indent == 0) {
            in_server_section = false;
        }
        if (!in_server_section) {
            continue;
        }

        const std::size_t colon = trimmed.find(':');
        if (colon == std::string::npos) {
            continue;
        }

        const std::string key = trim_copy(trimmed.substr(0, colon));
        const std::string raw_value = trim_copy(trimmed.substr(colon + 1));
        if (key == "host") {
            const std::string parsed_value = unquote_copy(raw_value);
            if (!parsed_value.empty()) {
                values.host = parsed_value;
            }
        } else if (key == "port") {
            const auto parsed_value = parse_int_value(raw_value);
            if (parsed_value.has_value()) {
                values.port = parsed_value;
            }
        } else if (key == "workers") {
            const auto parsed_value = parse_int_value(raw_value);
            if (parsed_value.has_value()) {
                values.workers = parsed_value;
            }
        } else if (key == "request_timeout_ms") {
            const auto parsed_value = parse_int_value(raw_value);
            if (parsed_value.has_value()) {
                values.request_timeout_ms = parsed_value;
            }
        } else if (key == "max_body_size_mb") {
            const auto parsed_value = parse_int_value(raw_value);
            if (parsed_value.has_value()) {
                values.max_body_size_mb = parsed_value;
            }
        } else if (key == "max_video_size_mb") {
            const auto parsed_value = parse_int_value(raw_value);
            if (parsed_value.has_value()) {
                values.max_video_size_mb = parsed_value;
            }
        } else if (key == "license_auto_reload_interval_seconds") {
            const auto parsed_value = parse_int_value(raw_value);
            if (parsed_value.has_value()) {
                values.license_auto_reload_interval_seconds = parsed_value;
            }
        } else if (key == "admin_token") {
            values.admin_token = unquote_copy(raw_value);
        }
    }

    return values;
}

PlatformPathConfigValues load_path_config_from_platform_config(const std::string& platform_config_path) {
    PlatformPathConfigValues values;
    std::ifstream input(platform_config_path);
    if (!input.is_open()) {
        return values;
    }

    bool in_paths_section = false;
    std::string line;
    while (std::getline(input, line)) {
        const std::size_t indent = line.find_first_not_of(' ');
        const std::string trimmed = trim_copy(line);
        if (trimmed.empty() || trimmed[0] == '#') {
            continue;
        }

        if ((indent == std::string::npos || indent == 0) && trimmed == "paths:") {
            in_paths_section = true;
            continue;
        }
        if (indent == std::string::npos || indent == 0) {
            in_paths_section = false;
        }
        if (!in_paths_section) {
            continue;
        }

        const std::size_t colon = trimmed.find(':');
        if (colon == std::string::npos) {
            continue;
        }

        const std::string key = trim_copy(trimmed.substr(0, colon));
        const std::string parsed_value = unquote_copy(trim_copy(trimmed.substr(colon + 1)));
        if (parsed_value.empty()) {
            continue;
        }

        if (key == "host_plugin_dir") {
            values.host_plugin_dir = parsed_value;
        } else if (key == "host_model_dir") {
            values.host_model_dir = parsed_value;
        } else if (key == "host_license_dir") {
            values.host_license_dir = parsed_value;
        } else if (key == "host_config_dir") {
            values.host_config_dir = parsed_value;
        } else if (key == "host_log_dir") {
            values.host_log_dir = parsed_value;
        } else if (key == "builtin_plugin_dir") {
            values.builtin_plugin_dir = parsed_value;
        } else if (key == "builtin_model_dir") {
            values.builtin_model_dir = parsed_value;
        } else if (key == "builtin_config_dir") {
            values.builtin_config_dir = parsed_value;
        }
    }

    return values;
}

std::string first_existing_path(const std::initializer_list<std::string>& candidates) {
    for (const auto& candidate : candidates) {
        if (candidate.empty()) {
            continue;
        }
        std::error_code ec;
        if (std::filesystem::exists(candidate, ec)) {
            return candidate;
        }
    }
    for (const auto& candidate : candidates) {
        if (!candidate.empty()) {
            return candidate;
        }
    }
    return std::string();
}

std::string join_if_not_empty(const std::string& base, const std::string& child) {
    if (base.empty()) {
        return std::string();
    }
    return (std::filesystem::path(base) / child).string();
}

}

LoadedPlatformConfig load_platform_config() {
    LoadedPlatformConfig config;
    config.resolved_app_paths = app_paths();

    const std::string platform_config_path = app_paths().platform_config;
    const PlatformServerConfigValues platform_server_config = load_server_config_from_platform_config(platform_config_path);
    const PlatformPathConfigValues platform_path_config = load_path_config_from_platform_config(platform_config_path);
    if (platform_server_config.host.has_value()) {
        config.host = *platform_server_config.host;
    }
    if (platform_server_config.port.has_value()) {
        config.port = *platform_server_config.port;
    }
    if (platform_server_config.workers.has_value() && *platform_server_config.workers > 0) {
        config.workers = *platform_server_config.workers;
    }
    if (platform_server_config.request_timeout_ms.has_value() && *platform_server_config.request_timeout_ms > 0) {
        config.request_timeout_ms = *platform_server_config.request_timeout_ms;
    }
    if (platform_server_config.max_body_size_mb.has_value() && *platform_server_config.max_body_size_mb > 0) {
        config.max_body_size_mb = *platform_server_config.max_body_size_mb;
    }
    if (platform_server_config.max_video_size_mb.has_value() && *platform_server_config.max_video_size_mb > 0) {
        config.max_video_size_mb = *platform_server_config.max_video_size_mb;
    }
    if (platform_server_config.license_auto_reload_interval_seconds.has_value() && *platform_server_config.license_auto_reload_interval_seconds >= 0) {
        config.license_auto_reload_interval_seconds = *platform_server_config.license_auto_reload_interval_seconds;
    }
    if (platform_server_config.admin_token.has_value() && !platform_server_config.admin_token->empty()) {
        config.admin_token = *platform_server_config.admin_token;
    }

    const std::string host_config_dir = platform_path_config.host_config_dir.value_or(std::string());
    const std::string host_license_dir = platform_path_config.host_license_dir.value_or(std::string());
    const std::string host_log_dir = platform_path_config.host_log_dir.value_or(std::string());
    const std::string builtin_config_dir = platform_path_config.builtin_config_dir.value_or(std::string());

    const std::string configured_registry_path = first_existing_path({
        join_if_not_empty(host_config_dir, "plugins_registry.txt"),
        join_if_not_empty(builtin_config_dir, "plugins_registry.txt"),
        config.resolved_app_paths.plugins_registry
    });
    if (!configured_registry_path.empty()) {
        config.resolved_app_paths.plugins_registry = configured_registry_path;
    }

    const std::string configured_license_path = first_existing_path({
        join_if_not_empty(host_license_dir, "license.dat"),
        std::string("build/tmp/demo_license.dat")
    });
    if (!configured_license_path.empty()) {
        config.license_path = configured_license_path;
    }

    if (!host_log_dir.empty()) {
        config.resolved_app_paths.license_audit_log = join_if_not_empty(host_log_dir, "audit.log");
        config.resolved_app_paths.runtime_audit_log = join_if_not_empty(host_log_dir, "runtime_audit.log");
    }

    const char* license_path_env = std::getenv("AI_PLATFORM_LICENSE_PATH");
    const char* server_host_env = std::getenv("AI_PLATFORM_SERVER_HOST");
    const char* server_port_env = std::getenv("AI_PLATFORM_SERVER_PORT");
    const char* server_workers_env = std::getenv("AI_PLATFORM_SERVER_WORKERS");
    const char* request_timeout_env = std::getenv("AI_PLATFORM_SERVER_REQUEST_TIMEOUT_MS");
    const char* max_body_size_env = std::getenv("AI_PLATFORM_SERVER_MAX_BODY_SIZE_MB");
    const char* max_video_size_env = std::getenv("AI_PLATFORM_SERVER_MAX_VIDEO_SIZE_MB");
    const char* license_auto_reload_interval_env = std::getenv("AI_PLATFORM_LICENSE_AUTO_RELOAD_INTERVAL_SECONDS");
    const char* admin_token_env = std::getenv("AI_PLATFORM_ADMIN_TOKEN");
    const char* registry_path_env = std::getenv("AI_PLATFORM_PLUGINS_REGISTRY_PATH");
    const char* license_audit_log_env = std::getenv("AI_PLATFORM_LICENSE_AUDIT_LOG_PATH");
    const char* runtime_audit_log_env = std::getenv("AI_PLATFORM_RUNTIME_AUDIT_LOG_PATH");

    if (license_path_env != nullptr && license_path_env[0] != '\0') {
        config.license_path = license_path_env;
    }
    if (server_host_env != nullptr && server_host_env[0] != '\0') {
        config.host = server_host_env;
    }
    if (server_port_env != nullptr && server_port_env[0] != '\0') {
        const auto parsed_value = parse_int_value(server_port_env);
        if (parsed_value.has_value() && *parsed_value > 0) {
            config.port = *parsed_value;
        }
    }
    if (server_workers_env != nullptr && server_workers_env[0] != '\0') {
        const auto parsed_value = parse_int_value(server_workers_env);
        if (parsed_value.has_value() && *parsed_value > 0) {
            config.workers = *parsed_value;
        }
    }
    if (request_timeout_env != nullptr && request_timeout_env[0] != '\0') {
        const auto parsed_value = parse_int_value(request_timeout_env);
        if (parsed_value.has_value() && *parsed_value > 0) {
            config.request_timeout_ms = *parsed_value;
        }
    }
    if (max_body_size_env != nullptr && max_body_size_env[0] != '\0') {
        const auto parsed_value = parse_int_value(max_body_size_env);
        if (parsed_value.has_value() && *parsed_value > 0) {
            config.max_body_size_mb = *parsed_value;
        }
    }
    if (max_video_size_env != nullptr && max_video_size_env[0] != '\0') {
        const auto parsed_value = parse_int_value(max_video_size_env);
        if (parsed_value.has_value() && *parsed_value > 0) {
            config.max_video_size_mb = *parsed_value;
        }
    }
    if (license_auto_reload_interval_env != nullptr && license_auto_reload_interval_env[0] != '\0') {
        const auto parsed_value = parse_int_value(license_auto_reload_interval_env);
        if (parsed_value.has_value() && *parsed_value >= 0) {
            config.license_auto_reload_interval_seconds = *parsed_value;
        }
    }
    if (admin_token_env != nullptr && admin_token_env[0] != '\0') {
        config.admin_token = admin_token_env;
    }
    if (registry_path_env != nullptr && registry_path_env[0] != '\0') {
        config.resolved_app_paths.plugins_registry = registry_path_env;
    }
    if (license_audit_log_env != nullptr && license_audit_log_env[0] != '\0') {
        config.resolved_app_paths.license_audit_log = license_audit_log_env;
    }
    if (runtime_audit_log_env != nullptr && runtime_audit_log_env[0] != '\0') {
        config.resolved_app_paths.runtime_audit_log = runtime_audit_log_env;
    }

    return config;
}

}
