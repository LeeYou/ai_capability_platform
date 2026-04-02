#include "capability_sdk.h"

#include "license_common.h"
#include "license_manager.h"

#include <algorithm>
#include <cstdlib>
#include <cstdint>
#include <sstream>
#include <string>

namespace ai_platform {

namespace {

std::string build_license_invalid_message(const LicenseStatusInfo& status) {
    std::ostringstream oss;
    oss << "license invalid";
    if (!status.failure_reason.empty()) {
        oss << " [reason=" << status.failure_reason;
        if (!status.failure_detail.empty()) {
            oss << ", detail=" << status.failure_detail;
        }
        oss << "]";
    }
    return oss.str();
}

std::string build_capability_not_licensed_message(const LicenseStatusInfo& status, const std::string& capability_id) {
    std::ostringstream oss;
    oss << "capability not licensed";
    if (!capability_id.empty()) {
        oss << " [capability=" << capability_id;
        const bool denied = std::find(
            status.denied_capabilities.begin(),
            status.denied_capabilities.end(),
            capability_id) != status.denied_capabilities.end();
        oss << ", reason=" << (denied ? kLicenseFailureReasonCapabilityDenied : kLicenseFailureReasonCapabilityNotInLicense) << "]";
    }
    return oss.str();
}

}

class CapabilitySdk::Impl {
public:
    SdkLoader loader;
    LicenseManager license_manager;
    bool license_enabled = false;
    std::string last_error;
};

CapabilitySdk::CapabilitySdk() = default;

CapabilitySdk::~CapabilitySdk() {
    delete impl_;
    impl_ = nullptr;
}

bool CapabilitySdk::initialize(const std::string& library_path, const std::string& model_dir, const std::string& license_path) {
    if (!impl_) {
        impl_ = new Impl();
    }
    impl_->last_error.clear();
    impl_->license_enabled = false;

    if (!impl_->loader.initialize(library_path, model_dir)) {
        impl_->last_error = impl_->loader.last_error();
        return false;
    }

    std::string resolved_license_path = license_path;
    if (resolved_license_path.empty()) {
        const char* license_path_env = std::getenv("AI_PLATFORM_LICENSE_PATH");
        if (license_path_env != nullptr && license_path_env[0] != '\0') {
            resolved_license_path = license_path_env;
        }
    }

    if (!resolved_license_path.empty()) {
        impl_->license_enabled = true;
        if (!impl_->license_manager.initialize(resolved_license_path)) {
            impl_->last_error = build_license_invalid_message(impl_->license_manager.get_status());
            return false;
        }
        if (!impl_->license_manager.quick_check(impl_->loader.capability_id())) {
            impl_->last_error = build_capability_not_licensed_message(
                impl_->license_manager.get_status(),
                impl_->loader.capability_id());
            return false;
        }
    }

    return true;
}

CapabilitySdkResult CapabilitySdk::infer_media_base64(const std::string& media_base64, const std::string& media_format, AiMediaType media_type, const std::string& params_json) const {
    CapabilitySdkResult result;
    if (!impl_) {
        result.error_message = "sdk not initialized";
        return result;
    }

    if (impl_->license_enabled) {
        const auto status = impl_->license_manager.get_status();
        if (!status.valid) {
            result.code = -402;
            result.error_message = build_license_invalid_message(status);
            return result;
        }
        if (!impl_->license_manager.quick_check(impl_->loader.capability_id())) {
            result.code = -401;
            result.error_message = build_capability_not_licensed_message(status, impl_->loader.capability_id());
            return result;
        }
    }

    AiPluginInput input{};
    input.images = nullptr;
    input.image_count = 0;
    input.media_data = reinterpret_cast<const std::uint8_t*>(media_base64.data());
    input.media_size = media_base64.size();
    input.media_type = media_type;
    input.media_format = media_format.c_str();
    input.params_json = params_json.c_str();

    result.ok = impl_->loader.infer(input, &result.result_json, &result.code, &result.error_message);
    return result;
}

std::string CapabilitySdk::last_error() const {
    if (!impl_) {
        return "sdk not initialized";
    }
    if (!impl_->last_error.empty()) {
        return impl_->last_error;
    }
    return impl_->loader.last_error();
}

std::string CapabilitySdk::last_license_failure_reason() const {
    if (!impl_ || !impl_->license_enabled) {
        return std::string();
    }

    const auto status = impl_->license_manager.get_status();
    if (!status.failure_reason.empty()) {
        return status.failure_reason;
    }

    const std::string capability_id = impl_->loader.capability_id();
    if (!capability_id.empty() && !impl_->license_manager.quick_check(capability_id)) {
        const bool denied = std::find(
            status.denied_capabilities.begin(),
            status.denied_capabilities.end(),
            capability_id) != status.denied_capabilities.end();
        return denied ? kLicenseFailureReasonCapabilityDenied : kLicenseFailureReasonCapabilityNotInLicense;
    }

    return std::string();
}

std::string CapabilitySdk::last_license_failure_detail() const {
    if (!impl_ || !impl_->license_enabled) {
        return std::string();
    }

    const auto status = impl_->license_manager.get_status();
    if (!status.failure_detail.empty()) {
        return status.failure_detail;
    }

    const std::string capability_id = impl_->loader.capability_id();
    if (!capability_id.empty() && !impl_->license_manager.quick_check(capability_id)) {
        return capability_id;
    }

    return std::string();
}

std::string CapabilitySdk::capability_id() const {
    if (!impl_) {
        return std::string();
    }
    return impl_->loader.capability_id();
}

}
