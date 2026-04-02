#include "app_paths.h"
#include "ai_runtime.h"
#include "ai_http_server.h"
#include "license_manager.h"
#include "platform_config.h"

#include <chrono>
#include <iostream>

namespace {

void print_startup_summary(const ai_platform::LoadedPlatformConfig& loaded_config,
                           const ai_platform::ServerConfig& config,
                           std::size_t capability_count) {
    std::cout << "[ai_platform] startup configuration" << std::endl;
    std::cout << "  host=" << config.host << std::endl;
    std::cout << "  port=" << config.port << std::endl;
    std::cout << "  workers=" << config.workers << std::endl;
    std::cout << "  request_timeout_ms=" << config.request_timeout_ms << std::endl;
    std::cout << "  max_body_size_mb=" << config.max_body_size_mb << std::endl;
    std::cout << "  max_video_size_mb=" << config.max_video_size_mb << std::endl;
    std::cout << "  license_auto_reload_interval_seconds=" << loaded_config.license_auto_reload_interval_seconds << std::endl;
    std::cout << "  license_path=" << loaded_config.license_path << std::endl;
    std::cout << "  plugins_registry=" << ai_platform::app_paths().plugins_registry << std::endl;
    std::cout << "  license_audit_log=" << ai_platform::app_paths().license_audit_log << std::endl;
    std::cout << "  runtime_audit_log=" << ai_platform::app_paths().runtime_audit_log << std::endl;
    std::cout << "  capability_count=" << capability_count << std::endl;
}

}

int main() {
    ai_platform::AiRuntime runtime;
    ai_platform::LicenseManager license_manager;
    ai_platform::AiHttpServer server;
    ai_platform::ServerConfig config;

    const ai_platform::LoadedPlatformConfig loaded_config = ai_platform::load_platform_config();
    config.host = loaded_config.host;
    config.port = loaded_config.port;
    config.workers = loaded_config.workers;
    config.request_timeout_ms = loaded_config.request_timeout_ms;
    config.max_body_size_mb = loaded_config.max_body_size_mb;
    config.max_video_size_mb = loaded_config.max_video_size_mb;
    config.admin_token = loaded_config.admin_token;

    ai_platform::configure_app_paths(loaded_config.resolved_app_paths);

    if (!runtime.initialize()) {
        std::cerr << "failed to initialize runtime using registry: " << ai_platform::app_paths().plugins_registry << std::endl;
        return 1;
    }
    if (!license_manager.initialize(loaded_config.license_path)) {
        std::cerr << "failed to initialize license manager using license path: " << loaded_config.license_path << std::endl;
        return 2;
    }
    print_startup_summary(loaded_config, config, runtime.capability_count());
    if (loaded_config.license_auto_reload_interval_seconds > 0) {
        license_manager.start_auto_reload_monitor(std::chrono::seconds(loaded_config.license_auto_reload_interval_seconds));
    }

    if (!server.initialize(config, &runtime, &license_manager)) {
        std::cerr << "failed to initialize http server" << std::endl;
        return 3;
    }
    if (!server.start()) {
        std::cerr << "failed to start http server on " << config.host << ':' << config.port << std::endl;
        return 4;
    }
    return 0;
}
