#ifndef AI_PLATFORM_CAPABILITY_SDK_H
#define AI_PLATFORM_CAPABILITY_SDK_H

#include "sdk_loader.h"

#include <string>

namespace ai_platform {

struct CapabilitySdkResult {
    bool ok = false;
    int code = 0;
    std::string result_json;
    std::string error_message;
};

class CapabilitySdk {
public:
    CapabilitySdk();
    ~CapabilitySdk();

    bool initialize(const std::string& library_path, const std::string& model_dir, const std::string& license_path = std::string());
    CapabilitySdkResult infer_media_base64(const std::string& media_base64, const std::string& media_format, AiMediaType media_type, const std::string& params_json) const;
    std::string last_error() const;
    std::string last_license_failure_reason() const;
    std::string last_license_failure_detail() const;
    std::string capability_id() const;

private:
    class Impl;
    Impl* impl_ = nullptr;
};

}

#endif
