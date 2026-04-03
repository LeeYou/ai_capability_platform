#include "license_manager.h"

#include "test_license_helpers.h"

#include <filesystem>
#include <fstream>
#include <iostream>
#include <thread>

namespace {

bool Expect(bool condition, const char* message) {
    if (!condition) {
        std::cerr << message << std::endl;
        return false;
    }
    return true;
}

std::string NowCstWithOffset(int day_offset) {
    const auto now = std::time(nullptr) + 8 * 60 * 60 + day_offset * 24 * 60 * 60;
    std::tm cst_time{};
#ifdef _WIN32
    gmtime_s(&cst_time, &now);
#else
    gmtime_r(&now, &cst_time);
#endif
    std::ostringstream output;
    output << std::put_time(&cst_time, "%Y-%m-%dT%H:%M:%S") << "+08:00";
    return output.str();
}

}

int main() {
    const std::filesystem::path license_root =
        std::filesystem::temp_directory_path() / "ai_prod_cpp_license_manager_test";
    std::filesystem::remove_all(license_root);

    const std::map<std::string, std::string> hardware_features = {
        {"cpu", "intel-i7"},
        {"mac", "00:11:22:33:44:55"},
    };

    nlohmann::json payload = {
        {"customer_code", "cust_prod"},
        {"capability_scope", nlohmann::json::array({"face_detect"})},
        {"hardware_fingerprint", test_license_helpers::BuildHardwareFingerprint(hardware_features)},
        {"start_at_cst", NowCstWithOffset(-1)},
        {"expire_at_cst", NowCstWithOffset(30)},
        {"version_constraints", {{"min_version", "v1_0_0"}, {"max_version", "v9_9_9"}}},
    };
    test_license_helpers::WriteLicenseBundle(license_root, payload);

    LicenseManager manager(license_root.string(), hardware_features, 1);
    if (!Expect(manager.Initialize(), "license manager should initialize with valid license")) {
        return 1;
    }
    const auto valid_status = manager.GetStatus();
    if (!Expect(valid_status.valid, "valid license should report valid status")) {
        return 1;
    }
    if (!Expect(manager.QuickCheck("face_detect", "v1_0_0"), "licensed capability should pass quick check")) {
        return 1;
    }
    if (!Expect(!manager.QuickCheck("ocr", "v1_0_0"), "capability outside scope should fail quick check")) {
        return 1;
    }
    if (!Expect(!manager.QuickCheck("face_detect", "v10_0_0"), "capability outside version range should fail quick check")) {
        return 1;
    }

    payload["capability_scope"] = nlohmann::json::array({"ocr"});
    test_license_helpers::WriteLicenseBundle(license_root, payload);
    if (!Expect(manager.Reload(), "reload should succeed with another valid license")) {
        return 1;
    }
    if (!Expect(!manager.QuickCheck("face_detect", "v1_0_0"), "reloaded capability scope should take effect")) {
        return 1;
    }
    if (!Expect(manager.QuickCheck("ocr", "v1_0_0"), "reloaded licensed capability should pass quick check")) {
        return 1;
    }

    payload["capability_scope"] = nlohmann::json::array({"face_detect"});
    test_license_helpers::WriteLicenseBundle(license_root, payload, false);
    if (!Expect(!manager.Reload(), "reload should fail for invalid signature")) {
        return 1;
    }
    const auto invalid_signature_status = manager.GetLastReloadFailureStatus();
    if (!Expect(invalid_signature_status.reason == "签名校验失败。", "invalid signature should expose reason")) {
        return 1;
    }

    payload["signature"] = nullptr;
    payload["expire_at_cst"] = NowCstWithOffset(-1);
    test_license_helpers::WriteLicenseBundle(license_root, payload);
    if (!Expect(!manager.Reload(), "reload should fail for expired license")) {
        return 1;
    }
    const auto expired_status = manager.GetLastReloadFailureStatus();
    if (!Expect(expired_status.reason == "license 已过期。", "expired license should expose reason")) {
        return 1;
    }

    payload["expire_at_cst"] = NowCstWithOffset(30);
    payload["hardware_fingerprint"] = "mismatch";
    test_license_helpers::WriteLicenseBundle(license_root, payload);
    if (!Expect(!manager.Reload(), "reload should fail for fingerprint mismatch")) {
        return 1;
    }
    const auto mismatch_status = manager.GetLastReloadFailureStatus();
    if (!Expect(mismatch_status.reason == "硬件指纹不匹配。", "fingerprint mismatch should expose reason")) {
        return 1;
    }

    payload["hardware_fingerprint"] = test_license_helpers::BuildHardwareFingerprint(hardware_features);
    payload["capability_scope"] = nlohmann::json::array({"face_detect"});
    test_license_helpers::WriteLicenseBundle(license_root, payload);
    if (!Expect(manager.Reload(), "reload should recover to valid license")) {
        return 1;
    }

    manager.StartAutoReloadMonitor();
    payload["capability_scope"] = nlohmann::json::array({"ocr"});
    test_license_helpers::WriteLicenseBundle(license_root, payload);
    std::this_thread::sleep_for(std::chrono::milliseconds(1300));
    if (!Expect(manager.QuickCheck("ocr", "v1_0_0"), "auto reload should pick up updated license")) {
        manager.StopAutoReloadMonitor();
        return 1;
    }
    manager.StopAutoReloadMonitor();

    std::filesystem::remove_all(license_root);
    return 0;
}
