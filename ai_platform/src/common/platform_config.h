#ifndef AI_PLATFORM_PLATFORM_CONFIG_H
#define AI_PLATFORM_PLATFORM_CONFIG_H

#include "app_paths.h"

#include <string>

namespace ai_platform {

struct LoadedPlatformConfig {
    std::string host = "0.0.0.0";
    int port = 26000;
    int workers = 4;
    int request_timeout_ms = 30000;
    int max_body_size_mb = 50;
    int max_video_size_mb = 200;
    int license_auto_reload_interval_seconds = 60;
    std::string admin_token = "demo-admin-token";
    std::string license_path = "build/tmp/demo_license.dat";
    AppPaths resolved_app_paths{};
};

LoadedPlatformConfig load_platform_config();

}

#endif
