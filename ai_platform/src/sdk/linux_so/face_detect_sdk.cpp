#include "face_detect_sdk.h"

#include <string>

namespace ai_platform {

class FaceDetectSdk::Impl {
public:
    CapabilitySdk sdk;
};

FaceDetectSdk::FaceDetectSdk() = default;

FaceDetectSdk::~FaceDetectSdk() {
    delete impl_;
    impl_ = nullptr;
}

bool FaceDetectSdk::initialize(const std::string& library_path, const std::string& model_dir, const std::string& license_path) {
    if (!impl_) {
        impl_ = new Impl();
    }
    return impl_->sdk.initialize(library_path, model_dir, license_path);
}

FaceDetectSdkResult FaceDetectSdk::infer_image_base64(const std::string& image_base64, const std::string& image_format) const {
    if (!impl_) {
        FaceDetectSdkResult result;
        result.error_message = "sdk not initialized";
        return result;
    }
    return impl_->sdk.infer_media_base64(image_base64, image_format, AI_MEDIA_TYPE_IMAGE, "{}");
}

std::string FaceDetectSdk::last_error() const {
    if (!impl_) {
        return "sdk not initialized";
    }
    return impl_->sdk.last_error();
}

std::string FaceDetectSdk::last_license_failure_reason() const {
    if (!impl_) {
        return std::string();
    }
    return impl_->sdk.last_license_failure_reason();
}

std::string FaceDetectSdk::last_license_failure_detail() const {
    if (!impl_) {
        return std::string();
    }
    return impl_->sdk.last_license_failure_detail();
}

std::string FaceDetectSdk::capability_id() const {
    if (!impl_) {
        return std::string();
    }
    return impl_->sdk.capability_id();
}

}
