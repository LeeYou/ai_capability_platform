#include "http_server.h"
#include "proxy_config.h"

#include <iostream>

int main() {
    const ProxyConfig config = load_proxy_config_from_env();
    AiProdHttpServer server(config);

    std::cout << "[ai-prod-cpp] listening on " << config.bind_host << ':' << config.bind_port
              << ", proxying to " << build_backend_base_url(config) << std::endl;

    if (!server.Start()) {
        std::cerr << "[ai-prod-cpp] failed to start server" << std::endl;
        return 1;
    }
    return 0;
}
