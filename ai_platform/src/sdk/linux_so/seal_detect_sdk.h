#ifndef AI_PLATFORM_SEAL_DETECT_SDK_H
#define AI_PLATFORM_SEAL_DETECT_SDK_H

#include "capability_sdk.h"

#include <string>

namespace ai_platform {

using SealDetectSdkResult = CapabilitySdkResult;

class SealDetectSdk {
public:
    SealDetectSdk();
    ~SealDetectSdk();

    bool initialize(const std::string& library_path, const std::string& model_dir, const std::string& license_path = std::string());
    SealDetectSdkResult infer_image_base64(const std::string& image_base64, const std::string& image_format) const;
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
