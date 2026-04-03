#ifndef AI_PLATFORM_TEST_RUNTIME_HELPERS_H
#define AI_PLATFORM_TEST_RUNTIME_HELPERS_H

#include "license_common.h"

#include <cstdlib>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <sstream>
#include <string>

namespace ai_platform::tests {

inline void assert_true(bool condition, const std::string& message) {
    if (!condition) {
        std::cerr << message << std::endl;
        std::exit(1);
    }
}

inline void set_env_var(const char* name, const std::string& value) {
#ifdef _WIN32
    _putenv_s(name, value.c_str());
#else
    setenv(name, value.c_str(), 1);
#endif
}

inline std::string create_model_package(const std::filesystem::path& base_directory,
                                        const std::string& capability_id,
                                        const std::string& package_name = std::string()) {
    const std::filesystem::path model_dir = package_name.empty() ? (base_directory / capability_id) : (base_directory / package_name);
    std::filesystem::create_directories(model_dir);

    const std::filesystem::path manifest_path = model_dir / "manifest.yaml";
    const std::filesystem::path checksum_path = model_dir / "checksum.sha256";
    const std::filesystem::path model_file_path = model_dir / "model.onnx";

    {
        std::ofstream manifest_output(manifest_path, std::ios::trunc);
        manifest_output << "capability_id: " << capability_id << "\n";
        manifest_output << "version: 1.0.0\n";
        manifest_output << "model_file: model.onnx\n";
    }

    {
        std::ofstream model_output(model_file_path, std::ios::trunc);
        model_output << "mock model for " << capability_id << "\n";
    }

    {
        std::ofstream checksum_output(checksum_path, std::ios::trunc);
        checksum_output << "0000000000000000000000000000000000000000000000000000000000000000  model.onnx\n";
    }

    return model_dir.string();
}

inline std::string create_registry_file(const std::filesystem::path& directory,
                                        const std::string& plugin_path_face_detect,
                                        const std::string& plugin_path_liveness_action,
                                        const std::string& plugin_path_idcard_detect,
                                        const std::string& plugin_path_doc_classify,
                                        const std::string& plugin_path_seal_detect) {
    std::filesystem::create_directories(directory);
    const std::filesystem::path models_dir = directory / "models";
    const std::string face_detect_model_dir = create_model_package(models_dir, "face_detect");
    const std::string liveness_action_model_dir = create_model_package(models_dir, "liveness_action");
    const std::string idcard_detect_model_dir = create_model_package(models_dir, "idcard_detect");
    const std::string doc_classify_model_dir = create_model_package(models_dir, "doc_classify");
    const std::string seal_detect_model_dir = create_model_package(models_dir, "seal_detect");
    const auto registry_path = directory / "plugins_registry_test.txt";
    std::ofstream output(registry_path, std::ios::trunc);
    output << "face_detect = " << plugin_path_face_detect << " | " << face_detect_model_dir << " | cpu | 1 | 2\n";
    output << "liveness_action = " << plugin_path_liveness_action << " | " << liveness_action_model_dir << " | cpu | 1 | 1\n";
    output << "idcard_detect = " << plugin_path_idcard_detect << " | " << idcard_detect_model_dir << " | cpu | 1 | 1\n";
    output << "doc_classify = " << plugin_path_doc_classify << " | " << doc_classify_model_dir << " | cpu | 1 | 1\n";
    output << "seal_detect = " << plugin_path_seal_detect << " | " << seal_detect_model_dir << " | cpu | 1 | 1\n";
    output.close();
    return registry_path.string();
}

inline std::string create_license_file(const std::filesystem::path& directory,
                                       const std::string& file_name,
                                       const ai_platform::LicenseFileData& data) {
    std::filesystem::create_directories(directory);
    const auto license_path = directory / file_name;
    std::string error_message;
    assert_true(ai_platform::write_license_file(license_path.string(), data, &error_message), error_message);
    return license_path.string();
}

inline ai_platform::LicenseFileData build_base_license(const std::string& license_id,
                                                       const std::string& capability_id) {
    ai_platform::LicenseFileData data;
    data.license_id = license_id;
    data.version = "1.0";
    data.license_type = "development";
    data.customer_id = "CUST-TEST-001";
    data.customer_name = "demo_customer";
    data.issued_at = "2026-03-01T00:00:00Z";
    data.effective_from = "2026-03-01T00:00:00Z";
    data.expires_at = "2099-12-31T23:59:59Z";
    data.grace_period_hours = 24;
    data.machine_fingerprint = ai_platform::compute_machine_fingerprint();
    data.licensed_capabilities = {capability_id};
    data.denied_capabilities = {};
    data.allow_reload = true;
    data.allow_admin_api = true;
    data.allow_test_page = true;
    data.signature = ai_platform::build_license_signature(data);
    return data;
}

}

#endif
