#include "app_paths.h"

#include <cstdlib>

namespace ai_platform {

namespace {

AppPaths build_default_app_paths() {
    return AppPaths{
        resolve_app_path_override("AI_PLATFORM_CONFIG_PATH", "config/platform.yaml"),
        resolve_app_path_override("AI_PLATFORM_PLUGINS_REGISTRY_PATH", "config/plugins_registry.txt"),
        resolve_app_path_override("AI_PLATFORM_LICENSE_AUDIT_LOG_PATH", "logs/audit.log"),
        resolve_app_path_override("AI_PLATFORM_RUNTIME_AUDIT_LOG_PATH", "logs/runtime_audit.log")
    };
}

AppPaths& mutable_app_paths() {
    static AppPaths paths = build_default_app_paths();
    return paths;
}

}

std::string resolve_app_path_override(std::string_view env_name, const std::string& fallback_value) {
    const char* env_value = std::getenv(std::string(env_name).c_str());
    if (env_value == nullptr || env_value[0] == '\0') {
        return fallback_value;
    }
    return env_value;
}

const AppPaths& app_paths() {
    return mutable_app_paths();
}

void configure_app_paths(const AppPaths& paths) {
    mutable_app_paths() = paths;
}

}
