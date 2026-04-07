#ifndef AI_CAPABILITY_PLATFORM_APPS_AI_PROD_CPP_LICENSE_MANAGER_H
#define AI_CAPABILITY_PLATFORM_APPS_AI_PROD_CPP_LICENSE_MANAGER_H

#include <chrono>
#include <condition_variable>
#include <filesystem>
#include <map>
#include <mutex>
#include <optional>
#include <string>
#include <thread>
#include <vector>

#include <nlohmann/json.hpp>

struct LicenseStatusInfo {
    bool valid = false;
    std::string reason = "标准 license 文件不存在。";
    std::string result = "failed";
    std::string code = "bundle_missing";
    std::string stage = "bundle";
    nlohmann::json details = nlohmann::json::object();
    std::string diagnostics_version = "1.0";
    std::string checked_at_cst;
    std::string customer_code;
    std::vector<std::string> capability_scope;
    nlohmann::json version_constraints = nlohmann::json::object();
    std::string hardware_fingerprint;
};

class LicenseManager {
public:
    LicenseManager(
        std::string license_root,
        std::map<std::string, std::string> hardware_features,
        int auto_reload_interval_seconds);
    ~LicenseManager();

    bool Initialize();
    bool Reload();
    bool QuickCheck(const std::string& capability_name, const std::string& product_version = std::string()) const;
    LicenseStatusInfo Evaluate(const std::string& capability_name = std::string(), const std::string& product_version = std::string()) const;
    LicenseStatusInfo GetStatus() const;
    LicenseStatusInfo GetLastReloadFailureStatus() const;
    void StartAutoReloadMonitor();
    void StopAutoReloadMonitor();

private:
    struct BundlePaths {
        std::filesystem::path license_path;
        std::filesystem::path pubkey_path;
    };

    static std::string BuildCanonicalJson(const nlohmann::json& value);
    static std::optional<std::string> Base64Decode(const std::string& encoded_value);
    static std::string Sha256Hex(const std::string& input);
    static std::string NormalizeCstDateTime(std::string value);
    static std::string CurrentCstIsoString();
    static bool IsVersionAllowed(const std::string& product_version, const nlohmann::json& version_constraints);
    bool VerifySignature(const nlohmann::json& payload, const std::string& signature_base64, const BundlePaths& paths) const;
    BundlePaths GetBundlePaths() const;
    std::filesystem::file_time_type GetBundleWriteTime(bool* exists) const;
    std::string BuildHardwareFingerprint() const;
    bool ReloadLocked(bool keep_last_valid_status);
    void AutoReloadLoop();

    mutable std::mutex mutex;
    std::condition_variable autoReloadCondition;
    std::filesystem::path licenseRoot;
    std::map<std::string, std::string> hardwareFeatures;
    int autoReloadIntervalSeconds = 0;
    LicenseStatusInfo status;
    LicenseStatusInfo lastReloadFailureStatus;
    bool initialized = false;
    bool autoReloadRunning = false;
    std::thread autoReloadThread;
    std::filesystem::file_time_type lastBundleWriteTime{};
    bool hasLastBundleWriteTime = false;
};

#endif
