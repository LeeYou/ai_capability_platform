#include "face_detect_sdk.h"

#include "license_common.h"

#include <cstdlib>
#include <filesystem>
#include <iostream>
#include <string>

namespace {

void assert_true(bool condition, const std::string& message) {
    if (!condition) {
        std::cerr << message << std::endl;
        std::exit(1);
    }
}

std::string prepare_license(const std::string& capability_id) {
    const auto license_path = (std::filesystem::temp_directory_path() / (capability_id + std::string("_sdk_test_license.dat"))).string();
    ai_platform::LicenseFileData data;
    data.license_id = "LIC-SDK-001";
    data.version = "1.0";
    data.license_type = "development";
    data.customer_id = "CUST-SDK-001";
    data.customer_name = "demo_customer";
    data.issued_at = "2026-03-01T00:00:00Z";
    data.effective_from = "2026-03-01T00:00:00Z";
    data.expires_at = "2099-12-31T23:59:59Z";
    data.grace_period_hours = 24;
    data.machine_fingerprint = ai_platform::compute_machine_fingerprint();
    data.licensed_capabilities = {capability_id};
    data.denied_capabilities = {};
    data.signature = ai_platform::build_license_signature(data);
    std::string error_message;
    assert_true(ai_platform::write_license_file(license_path, data, &error_message), error_message);
    return license_path;
}

std::string prepare_denied_license(const std::string& capability_id) {
    const auto license_path = (std::filesystem::temp_directory_path() / (capability_id + std::string("_sdk_test_denied_license.dat"))).string();
    ai_platform::LicenseFileData data;
    data.license_id = "LIC-SDK-001-DENIED";
    data.version = "1.0";
    data.license_type = "development";
    data.customer_id = "CUST-SDK-001";
    data.customer_name = "demo_customer";
    data.issued_at = "2026-03-01T00:00:00Z";
    data.effective_from = "2026-03-01T00:00:00Z";
    data.expires_at = "2099-12-31T23:59:59Z";
    data.grace_period_hours = 24;
    data.machine_fingerprint = ai_platform::compute_machine_fingerprint();
    data.licensed_capabilities = {capability_id};
    data.denied_capabilities = {capability_id};
    data.signature = ai_platform::build_license_signature(data);
    std::string error_message;
    assert_true(ai_platform::write_license_file(license_path, data, &error_message), error_message);
    return license_path;
}

}

int main(int argc, char** argv) {
    assert_true(argc >= 3, "usage: test_face_detect_sdk <plugin_path> <model_dir>");

    ai_platform::FaceDetectSdk sdk;
    const auto license_path = prepare_license("face_detect");
    assert_true(sdk.initialize(argv[1], argv[2], license_path), "sdk initialize should succeed");
    assert_true(sdk.capability_id() == "face_detect", "sdk capability id should be face_detect");

    const auto infer_result = sdk.infer_image_base64("YWJjZA==", "jpg");
    assert_true(infer_result.ok, "sdk infer should succeed");
    assert_true(infer_result.code == 0, "sdk infer code should be zero");
    assert_true(infer_result.result_json.find("\"mock\":true") != std::string::npos, "sdk infer result should contain mock marker");
    assert_true(infer_result.result_json.find("\"media_format\":\"jpg\"") != std::string::npos, "sdk infer result should contain media format");

    ai_platform::FaceDetectSdk denied_sdk;
    const auto denied_license_path = prepare_denied_license("face_detect");
    assert_true(!denied_sdk.initialize(argv[1], argv[2], denied_license_path), "sdk initialize should fail when capability is denied");
    assert_true(denied_sdk.last_error().find("capability not licensed") != std::string::npos, "sdk denied last_error should keep compatibility prefix");
    assert_true(denied_sdk.last_error().find(std::string("reason=") + ai_platform::kLicenseFailureReasonCapabilityDenied) != std::string::npos, "sdk denied last_error should expose capability_denied reason");
    assert_true(denied_sdk.last_license_failure_reason() == ai_platform::kLicenseFailureReasonCapabilityDenied, "sdk denied failure reason accessor should be capability_denied");
    assert_true(denied_sdk.last_license_failure_detail() == "face_detect", "sdk denied failure detail accessor should expose capability id");

    return 0;
}
