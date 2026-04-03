#ifndef AI_CAPABILITY_PLATFORM_APPS_AI_PROD_CPP_PROXY_CONFIG_H
#define AI_CAPABILITY_PLATFORM_APPS_AI_PROD_CPP_PROXY_CONFIG_H

#include <map>
#include <string>

struct ProxyConfig {
    std::string bind_host = "0.0.0.0";
    int bind_port = 26005;
    std::string backend_host = "127.0.0.1";
    int backend_port = 26004;
    std::string host_root = "/data/ai_capability_platform";
    std::string license_root = "/data/ai_capability_platform/license";
    std::string runtime_snapshot_path = "/data/ai_capability_platform/data/ai_prod_runtime_snapshot.json";
    std::string runtime_log_path = "/data/ai_capability_platform/logs/ai_prod_runtime.log";
    std::string audit_log_path = "/data/ai_capability_platform/logs/ai_prod_audit.log";
    int pool_size = 2;
    int connect_timeout_ms = 3000;
    int read_timeout_ms = 30000;
    int write_timeout_ms = 30000;
    int snapshot_max_age_seconds = 30;
    int license_auto_reload_interval_seconds = 60;
    std::map<std::string, std::string> hardware_features;
};

ProxyConfig load_proxy_config_from_env();
std::string build_backend_base_url(const ProxyConfig& config);

#endif
