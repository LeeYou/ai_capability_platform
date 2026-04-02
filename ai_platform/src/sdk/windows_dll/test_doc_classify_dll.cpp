#include "doc_classify_dll.h"

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
    const auto license_path = (std::filesystem::temp_directory_path() / (capability_id + std::string("_dll_test_license.dat"))).string();
    ai_platform::LicenseFileData data;
    data.license_id = "LIC-DLL-004";
    data.version = "1.0";
    data.license_type = "development";
    data.customer_id = "CUST-DLL-004";
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

std::string prepare_invalid_signature_license(const std::string& capability_id) {
    const auto license_path = (std::filesystem::temp_directory_path() / (capability_id + std::string("_dll_test_invalid_license.dat"))).string();
    ai_platform::LicenseFileData data;
    data.license_id = "LIC-DLL-004-INVALID";
    data.version = "1.0";
    data.license_type = "development";
    data.customer_id = "CUST-DLL-004";
    data.customer_name = "demo_customer";
    data.issued_at = "2026-03-01T00:00:00Z";
    data.effective_from = "2026-03-01T00:00:00Z";
    data.expires_at = "2099-12-31T23:59:59Z";
    data.grace_period_hours = 24;
    data.machine_fingerprint = ai_platform::compute_machine_fingerprint();
    data.licensed_capabilities = {capability_id};
    data.denied_capabilities = {};
    data.signature = "invalid-signature";
    std::string error_message;
    assert_true(ai_platform::write_license_file(license_path, data, &error_message), error_message);
    return license_path;
}

}

int main(int argc, char** argv) {
    assert_true(argc >= 3, "usage: test_doc_classify_dll <plugin_path> <model_dir>");
    const auto license_path = prepare_license("doc_classify");
    assert_true(ai_doc_classify_initialize(argv[1], argv[2], license_path.c_str()) == 0, "dll initialize should succeed");
    assert_true(std::string(ai_doc_classify_capability_id()) == "doc_classify", "dll capability id should be doc_classify");

    const auto result = ai_doc_classify_infer_base64("YWJjZA==", "jpg");
    assert_true(result.code == 0, "dll infer code should be zero");
    assert_true(result.result_json != nullptr, "dll infer result json should exist");
    assert_true(std::string(result.result_json).find("\"document_type\":\"id_card\"") != std::string::npos, "dll infer should contain document type field");

    ai_doc_classify_shutdown();

    const auto invalid_license_path = prepare_invalid_signature_license("doc_classify");
    assert_true(ai_doc_classify_initialize(argv[1], argv[2], invalid_license_path.c_str()) == -1, "dll initialize should fail for invalid license");
    assert_true(ai_doc_classify_last_license_failure_reason() != nullptr, "dll invalid license failure reason should exist");
    assert_true(std::string(ai_doc_classify_last_license_failure_reason()) == ai_platform::kLicenseFailureReasonSignatureInvalid, "dll invalid license failure reason should be signature_invalid");
    assert_true(ai_doc_classify_last_license_failure_detail() != nullptr, "dll invalid license failure detail should exist");
    assert_true(std::string(ai_doc_classify_last_license_failure_detail()) == "license signature invalid", "dll invalid license failure detail should expose signature detail");
    const auto invalid_result = ai_doc_classify_infer_base64("YWJjZA==", "jpg");
    assert_true(invalid_result.code == -1, "dll infer should remain uninitialized after invalid license init");
    assert_true(invalid_result.error_message != nullptr, "dll invalid license error message should exist");
    assert_true(std::string(invalid_result.error_message) == "sdk not initialized", "dll infer after failed init should remain sdk not initialized");

    return 0;
}
