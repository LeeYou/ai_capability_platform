#ifndef AI_PLATFORM_IDCARD_DETECT_SDK_H
#define AI_PLATFORM_IDCARD_DETECT_SDK_H

#include "capability_sdk.h"

#include <string>

namespace ai_platform {

using IdCardDetectSdkResult = CapabilitySdkResult;

class IdCardDetectSdk {
public:
    IdCardDetectSdk();
    ~IdCardDetectSdk();

    bool initialize(const std::string& library_path, const std::string& model_dir, const std::string& license_path = std::string());
    IdCardDetectSdkResult infer_image_base64(const std::string& image_base64, const std::string& image_format) const;
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
