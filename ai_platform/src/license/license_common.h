#ifndef AI_PLATFORM_LICENSE_COMMON_H
#define AI_PLATFORM_LICENSE_COMMON_H

#include <string>
#include <vector>

namespace ai_platform {

inline constexpr const char* kLicenseFailureReasonFileOpenFailed = "license_file_open_failed";
inline constexpr const char* kLicenseFailureReasonFormatInvalid = "license_format_invalid";
inline constexpr const char* kLicenseFailureReasonFieldsMissing = "license_fields_missing";
inline constexpr const char* kLicenseFailureReasonFingerprintMismatch = "fingerprint_mismatch";
inline constexpr const char* kLicenseFailureReasonSignatureInvalid = "signature_invalid";
inline constexpr const char* kLicenseFailureReasonNotYetEffective = "not_yet_effective";
inline constexpr const char* kLicenseFailureReasonExpired = "expired";
inline constexpr const char* kLicenseFailureReasonInvalid = "license_invalid";
inline constexpr const char* kLicenseFailureReasonCapabilityDenied = "capability_denied";
inline constexpr const char* kLicenseFailureReasonCapabilityNotInLicense = "capability_not_in_license";

struct LicenseTimeStatus {
    bool effective_now = false;
    bool in_grace_period = false;
    bool expired = false;
};

struct LicenseFileData {
    std::string license_id;
    std::string version;
    std::string license_type;
    std::string customer_id;
    std::string customer_name;
    std::string issued_at;
    std::string effective_from;
    std::string expires_at;
    int grace_period_hours = 0;
    std::string machine_fingerprint;
    std::string operating_system;
    std::string min_operating_system_version;
    std::string system_architecture;
    std::string application_name;
    std::vector<std::string> licensed_capabilities;
    std::vector<std::string> denied_capabilities;
    bool allow_reload = false;
    bool allow_admin_api = false;
    bool allow_test_page = false;
    std::string signature;
};

std::string compute_machine_fingerprint();
std::string build_license_payload(const LicenseFileData& data);
std::string sign_license_payload(const std::string& payload);
std::string build_license_signature(const LicenseFileData& data);
bool verify_license_signature(const std::string& payload, const std::string& signature);
LicenseTimeStatus get_license_time_status(const LicenseFileData& data);
bool parse_license_file(const std::string& license_path, LicenseFileData* out_data, std::string* out_error_message);
bool write_license_file(const std::string& license_path, const LicenseFileData& data, std::string* out_error_message);
bool verify_license_file(const LicenseFileData& data, const std::string& expected_fingerprint, std::string* out_error_message);

}

#endif
