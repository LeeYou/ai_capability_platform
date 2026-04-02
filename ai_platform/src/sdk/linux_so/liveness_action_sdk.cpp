#include "liveness_action_sdk.h"

namespace ai_platform {

LivenessActionSdk::LivenessActionSdk() = default;

LivenessActionSdk::~LivenessActionSdk() = default;

bool LivenessActionSdk::initialize(const std::string& library_path, const std::string& model_dir, const std::string& license_path) {
    return sdk_.initialize(library_path, model_dir, license_path);
}

LivenessActionSdkResult LivenessActionSdk::infer_video_base64(const std::string& media_base64, const std::string& media_format, const std::string& action) const {
    const std::string params_json = std::string("{\"action\":\"") + action + "\"}";
    return sdk_.infer_media_base64(media_base64, media_format, AI_MEDIA_TYPE_VIDEO, params_json);
}

std::string LivenessActionSdk::last_error() const {
    return sdk_.last_error();
}

std::string LivenessActionSdk::last_license_failure_reason() const {
    return sdk_.last_license_failure_reason();
}

std::string LivenessActionSdk::last_license_failure_detail() const {
    return sdk_.last_license_failure_detail();
}

std::string LivenessActionSdk::capability_id() const {
    return sdk_.capability_id();
}

}
