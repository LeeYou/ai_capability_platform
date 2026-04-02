#ifndef AI_PLATFORM_APP_PATHS_H
#define AI_PLATFORM_APP_PATHS_H

#include <string>

#include <string_view>

namespace ai_platform {

struct AppPaths {
    std::string platform_config = "config/platform.yaml";
    std::string plugins_registry = "config/plugins_registry.txt";
    std::string license_audit_log = "logs/audit.log";
    std::string runtime_audit_log = "logs/runtime_audit.log";
};

const AppPaths& app_paths();
void configure_app_paths(const AppPaths& paths);
std::string resolve_app_path_override(std::string_view env_name, const std::string& fallback_value);

}

#endif
