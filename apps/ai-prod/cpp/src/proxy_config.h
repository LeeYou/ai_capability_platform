#ifndef AI_CAPABILITY_PLATFORM_APPS_AI_PROD_CPP_PROXY_CONFIG_H
#define AI_CAPABILITY_PLATFORM_APPS_AI_PROD_CPP_PROXY_CONFIG_H

#include <string>

struct ProxyConfig {
    std::string bind_host = "0.0.0.0";
    int bind_port = 26005;
    std::string backend_host = "127.0.0.1";
    int backend_port = 26004;
    int connect_timeout_ms = 3000;
    int read_timeout_ms = 30000;
    int write_timeout_ms = 30000;
};

ProxyConfig load_proxy_config_from_env();
std::string build_backend_base_url(const ProxyConfig& config);

#endif
