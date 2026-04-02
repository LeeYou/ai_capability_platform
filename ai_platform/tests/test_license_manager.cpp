#include "license_common.h"
#include "license_manager.h"

#include "test_runtime_helpers.h"

#include <filesystem>
#include <string>

int main() {
    const std::filesystem::path temp_dir = std::filesystem::temp_directory_path() / "ai_platform_license_manager_tests";

    ai_platform::LicenseManager license_manager;

    auto valid_license = ai_platform::tests::build_base_license("LIC-TEST-VALID", "face_detect");
    valid_license.denied_capabilities = {"liveness_action"};
    valid_license.signature = ai_platform::build_license_signature(valid_license);
    const std::string valid_license_path = ai_platform::tests::create_license_file(temp_dir, "valid_license.dat", valid_license);

    ai_platform::tests::assert_true(license_manager.initialize(valid_license_path), "license manager should initialize with valid license");
    const auto valid_status = license_manager.get_status();
    ai_platform::tests::assert_true(valid_status.valid, "valid license should report valid status");
    ai_platform::tests::assert_true(valid_status.allow_reload, "valid license should preserve allow_reload feature");
    ai_platform::tests::assert_true(license_manager.quick_check("face_detect"), "licensed capability should pass quick check");
    ai_platform::tests::assert_true(!license_manager.quick_check("liveness_action"), "capability missing from license should fail quick check");

    auto denied_license = ai_platform::tests::build_base_license("LIC-TEST-DENIED", "face_detect");
    denied_license.denied_capabilities = {"face_detect"};
    denied_license.signature = ai_platform::build_license_signature(denied_license);
    const std::string denied_license_path = ai_platform::tests::create_license_file(temp_dir, "denied_license.dat", denied_license);
    ai_platform::tests::assert_true(license_manager.reload_license(denied_license_path), "reload to denied license should still succeed as a valid license file");
    ai_platform::tests::assert_true(!license_manager.quick_check("face_detect"), "denied capability should fail quick check after reload");

    auto invalid_signature_license = ai_platform::tests::build_base_license("LIC-TEST-INVALID-SIGNATURE", "face_detect");
    invalid_signature_license.signature = "invalid-signature";
    const std::string invalid_signature_path = ai_platform::tests::create_license_file(temp_dir, "invalid_signature_license.dat", invalid_signature_license);
    ai_platform::tests::assert_true(!license_manager.reload_license(invalid_signature_path), "reload should fail for invalid signature license");
    const auto invalid_signature_status = license_manager.get_last_reload_failure_status();
    ai_platform::tests::assert_true(invalid_signature_status.failure_reason == ai_platform::kLicenseFailureReasonSignatureInvalid, "invalid signature reload should expose signature_invalid reason");
    ai_platform::tests::assert_true(invalid_signature_status.failure_detail == "license signature invalid", "invalid signature reload should expose detail");

    auto expired_license = ai_platform::tests::build_base_license("LIC-TEST-EXPIRED", "face_detect");
    expired_license.expires_at = "2026-03-02T00:00:00Z";
    expired_license.grace_period_hours = 0;
    expired_license.signature = ai_platform::build_license_signature(expired_license);
    const std::string expired_license_path = ai_platform::tests::create_license_file(temp_dir, "expired_license.dat", expired_license);
    ai_platform::tests::set_env_var("AI_PLATFORM_LICENSE_NOW", "2026-03-03T00:00:00Z");
    ai_platform::tests::assert_true(!license_manager.reload_license(expired_license_path), "reload should fail for expired license when outside grace period");
    const auto expired_status = license_manager.get_last_reload_failure_status();
    ai_platform::tests::assert_true(expired_status.failure_reason == ai_platform::kLicenseFailureReasonExpired, "expired reload should expose expired reason");
    ai_platform::tests::assert_true(expired_status.failure_detail == "license expired", "expired reload should expose expired detail");
    ai_platform::tests::set_env_var("AI_PLATFORM_LICENSE_NOW", "");

    return 0;
}
