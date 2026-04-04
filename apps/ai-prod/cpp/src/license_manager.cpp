#include "license_manager.h"

#include <openssl/bio.h>
#include <openssl/evp.h>
#include <openssl/pem.h>

#include <algorithm>
#include <cctype>
#include <cstdio>
#include <ctime>
#include <fstream>
#include <iomanip>
#include <optional>
#include <sstream>
#include <system_error>

namespace {

std::string JsonString(const std::string& value) {
    return nlohmann::json(value).dump();
}

std::vector<int> VersionTuple(const std::string& raw_value) {
    std::string normalized = raw_value;
    normalized.erase(
        std::remove_if(normalized.begin(), normalized.end(), [](unsigned char ch) {
            return std::isspace(ch) != 0;
        }),
        normalized.end());
    if (normalized.empty()) {
        return {};
    }

    std::vector<int> parts;
    std::stringstream input(normalized);
    std::string segment;
    while (std::getline(input, segment, '.')) {
        std::string digits;
        digits.reserve(segment.size());
        for (char ch : segment) {
            if (std::isdigit(static_cast<unsigned char>(ch))) {
                digits.push_back(ch);
            }
        }
        parts.push_back(digits.empty() ? 0 : std::stoi(digits));
    }
    return parts;
}

}

LicenseManager::LicenseManager(
    std::string license_root,
    std::map<std::string, std::string> hardware_features,
    int auto_reload_interval_seconds)
    : licenseRoot(std::move(license_root)),
      hardwareFeatures(std::move(hardware_features)),
      autoReloadIntervalSeconds(auto_reload_interval_seconds) {
}

LicenseManager::~LicenseManager() {
    StopAutoReloadMonitor();
}

bool LicenseManager::Initialize() {
    std::lock_guard<std::mutex> guard(mutex);
    return ReloadLocked(false);
}

bool LicenseManager::Reload() {
    std::lock_guard<std::mutex> guard(mutex);
    return ReloadLocked(true);
}

bool LicenseManager::QuickCheck(const std::string& capability_name, const std::string& product_version) const {
    std::lock_guard<std::mutex> guard(mutex);
    if (!initialized || capability_name.empty() || !status.valid) {
        return false;
    }
    if (!status.capability_scope.empty() &&
        std::find(status.capability_scope.begin(), status.capability_scope.end(), capability_name) == status.capability_scope.end()) {
        return false;
    }
    return IsVersionAllowed(product_version, status.version_constraints);
}

LicenseStatusInfo LicenseManager::GetStatus() const {
    std::lock_guard<std::mutex> guard(mutex);
    return status;
}

LicenseStatusInfo LicenseManager::GetLastReloadFailureStatus() const {
    std::lock_guard<std::mutex> guard(mutex);
    return lastReloadFailureStatus;
}

void LicenseManager::StartAutoReloadMonitor() {
    std::lock_guard<std::mutex> guard(mutex);
    if (autoReloadIntervalSeconds <= 0 || autoReloadRunning) {
        return;
    }
    autoReloadRunning = true;
    autoReloadThread = std::thread(&LicenseManager::AutoReloadLoop, this);
}

void LicenseManager::StopAutoReloadMonitor() {
    {
        std::lock_guard<std::mutex> guard(mutex);
        autoReloadRunning = false;
    }
    autoReloadCondition.notify_all();
    if (autoReloadThread.joinable()) {
        autoReloadThread.join();
    }
}

std::string LicenseManager::BuildCanonicalJson(const nlohmann::json& value) {
    if (value.is_object()) {
        std::vector<std::string> keys;
        keys.reserve(value.size());
        for (auto it = value.begin(); it != value.end(); ++it) {
            keys.push_back(it.key());
        }
        std::sort(keys.begin(), keys.end());

        std::ostringstream output;
        output << '{';
        for (std::size_t index = 0; index < keys.size(); ++index) {
            if (index > 0) {
                output << ',';
            }
            output << JsonString(keys[index]) << ':' << BuildCanonicalJson(value.at(keys[index]));
        }
        output << '}';
        return output.str();
    }
    if (value.is_array()) {
        std::ostringstream output;
        output << '[';
        for (std::size_t index = 0; index < value.size(); ++index) {
            if (index > 0) {
                output << ',';
            }
            output << BuildCanonicalJson(value[index]);
        }
        output << ']';
        return output.str();
    }
    return value.dump();
}

std::optional<std::string> LicenseManager::Base64Decode(const std::string& encoded_value) {
    if (encoded_value.empty()) {
        return std::string();
    }
    std::string compact;
    compact.reserve(encoded_value.size());
    for (char ch : encoded_value) {
        if (!std::isspace(static_cast<unsigned char>(ch))) {
            compact.push_back(ch);
        }
    }
    if (compact.empty()) {
        return std::string();
    }

    const std::size_t padding =
        compact.size() >= 2 && compact.compare(compact.size() - 2, 2, "==") == 0 ? 2 :
        (compact.size() >= 1 && compact.back() == '=' ? 1 : 0);
    std::string decoded((compact.size() * 3) / 4 + 4, '\0');
    const int decoded_size = EVP_DecodeBlock(
        reinterpret_cast<unsigned char*>(decoded.data()),
        reinterpret_cast<const unsigned char*>(compact.data()),
        static_cast<int>(compact.size()));
    if (decoded_size < 0) {
        return std::nullopt;
    }
    decoded.resize(static_cast<std::size_t>(decoded_size) - padding);
    return decoded;
}

std::string LicenseManager::Sha256Hex(const std::string& input) {
    unsigned char digest[EVP_MAX_MD_SIZE] = {0};
    unsigned int digest_size = 0;
    EVP_MD_CTX* context = EVP_MD_CTX_new();
    if (!context) {
        return {};
    }
    const bool ok =
        EVP_DigestInit_ex(context, EVP_sha256(), nullptr) == 1 &&
        EVP_DigestUpdate(context, input.data(), input.size()) == 1 &&
        EVP_DigestFinal_ex(context, digest, &digest_size) == 1;
    EVP_MD_CTX_free(context);
    if (!ok) {
        return {};
    }

    std::ostringstream output;
    output << std::hex << std::setfill('0');
    for (unsigned int index = 0; index < digest_size; ++index) {
        output << std::setw(2) << static_cast<int>(digest[index]);
    }
    return output.str();
}

std::string LicenseManager::NormalizeCstDateTime(std::string value) {
    if (value.size() >= 1 && value.back() == 'Z') {
        value.pop_back();
        value += "+00:00";
        return value;
    }
    if (value.size() >= 6 &&
        (value[value.size() - 6] == '+' || value[value.size() - 6] == '-') &&
        value[value.size() - 3] == ':') {
        return value;
    }
    if (value.size() == 19) {
        return value + "+08:00";
    }
    return value;
}

std::string LicenseManager::CurrentCstIsoString() {
    const std::time_t now = std::time(nullptr) + 8 * 60 * 60;
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

bool LicenseManager::IsVersionAllowed(const std::string& product_version, const nlohmann::json& version_constraints) {
    if (!version_constraints.is_object() || version_constraints.empty()) {
        return true;
    }
    if (product_version.empty()) {
        return false;
    }
    const auto allowed_versions_it = version_constraints.find("allowed_versions");
    if (allowed_versions_it != version_constraints.end() && allowed_versions_it->is_array() && !allowed_versions_it->empty()) {
        bool matched = false;
        for (const auto& item : *allowed_versions_it) {
            if (item.is_string() && item.get<std::string>() == product_version) {
                matched = true;
                break;
            }
        }
        if (!matched) {
            return false;
        }
    }
    const auto prefix_it = version_constraints.find("prefix");
    if (prefix_it != version_constraints.end() && prefix_it->is_string()) {
        const std::string prefix = prefix_it->get<std::string>();
        if (!prefix.empty() && product_version.rfind(prefix, 0) != 0) {
            return false;
        }
    }

    const std::vector<int> current_version = VersionTuple(product_version);
    const auto min_version_it = version_constraints.find("min_version");
    if (min_version_it != version_constraints.end() && min_version_it->is_string() &&
        !min_version_it->get<std::string>().empty() &&
        current_version < VersionTuple(min_version_it->get<std::string>())) {
        return false;
    }
    const auto max_version_it = version_constraints.find("max_version");
    if (max_version_it != version_constraints.end() && max_version_it->is_string() &&
        !max_version_it->get<std::string>().empty() &&
        current_version > VersionTuple(max_version_it->get<std::string>())) {
        return false;
    }
    return true;
}

bool LicenseManager::VerifySignature(
    const nlohmann::json& payload,
    const std::string& signature_base64,
    const BundlePaths& paths) const {
    const auto decoded_signature = Base64Decode(signature_base64);
    if (!decoded_signature.has_value()) {
        return false;
    }

    std::ifstream input(paths.pubkey_path);
    if (!input.is_open()) {
        return false;
    }
    std::stringstream buffer;
    buffer << input.rdbuf();
    const std::string pubkey_pem = buffer.str();

    BIO* bio = BIO_new_mem_buf(pubkey_pem.data(), static_cast<int>(pubkey_pem.size()));
    if (!bio) {
        return false;
    }
    EVP_PKEY* pkey = PEM_read_bio_PUBKEY(bio, nullptr, nullptr, nullptr);
    BIO_free(bio);
    if (!pkey) {
        return false;
    }

    EVP_MD_CTX* verify_context = EVP_MD_CTX_new();
    if (!verify_context) {
        EVP_PKEY_free(pkey);
        return false;
    }

    const std::string canonical_payload = BuildCanonicalJson(payload);
    const bool ok =
        EVP_DigestVerifyInit(verify_context, nullptr, nullptr, nullptr, pkey) == 1 &&
        EVP_DigestVerify(
            verify_context,
            reinterpret_cast<const unsigned char*>(decoded_signature->data()),
            decoded_signature->size(),
            reinterpret_cast<const unsigned char*>(canonical_payload.data()),
            canonical_payload.size()) == 1;

    EVP_MD_CTX_free(verify_context);
    EVP_PKEY_free(pkey);
    return ok;
}

LicenseManager::BundlePaths LicenseManager::GetBundlePaths() const {
    return {
        licenseRoot / "license.bin",
        licenseRoot / "pubkey.pem",
    };
}

std::filesystem::file_time_type LicenseManager::GetBundleWriteTime(bool* exists) const {
    if (exists) {
        *exists = false;
    }
    const auto paths = GetBundlePaths();
    std::error_code error_code;
    const bool license_exists = std::filesystem::exists(paths.license_path, error_code);
    if (error_code) {
        return {};
    }
    const bool pubkey_exists = std::filesystem::exists(paths.pubkey_path, error_code);
    if (error_code) {
        return {};
    }
    if (!license_exists && !pubkey_exists) {
        return {};
    }
    if (exists) {
        *exists = true;
    }

    std::filesystem::file_time_type latest_time{};
    bool has_latest_time = false;
    if (license_exists) {
        const auto license_time = std::filesystem::last_write_time(paths.license_path, error_code);
        if (!error_code) {
            latest_time = license_time;
            has_latest_time = true;
        }
    }
    if (pubkey_exists) {
        const auto pubkey_time = std::filesystem::last_write_time(paths.pubkey_path, error_code);
        if (!error_code && (!has_latest_time || pubkey_time > latest_time)) {
            latest_time = pubkey_time;
            has_latest_time = true;
        }
    }
    return has_latest_time ? latest_time : std::filesystem::file_time_type{};
}

std::string LicenseManager::BuildHardwareFingerprint() const {
    std::vector<std::pair<std::string, std::string>> features(hardwareFeatures.begin(), hardwareFeatures.end());
    std::sort(features.begin(), features.end(), [](const auto& left, const auto& right) {
        return left.first < right.first;
    });

    std::ostringstream output;
    for (std::size_t index = 0; index < features.size(); ++index) {
        if (index > 0) {
            output << '|';
        }
        std::string key = features[index].first;
        std::transform(key.begin(), key.end(), key.begin(), [](unsigned char ch) {
            return static_cast<char>(std::tolower(ch));
        });
        output << key << '=' << features[index].second;
    }
    const std::string normalized = output.str();
    return normalized.empty() ? std::string() : Sha256Hex(normalized);
}

bool LicenseManager::ReloadLocked(bool keep_last_valid_status) {
    const auto paths = GetBundlePaths();
    LicenseStatusInfo next_status;
    next_status.checked_at_cst = CurrentCstIsoString();

    if (!std::filesystem::exists(paths.license_path) || !std::filesystem::exists(paths.pubkey_path)) {
        next_status.reason = "标准 license 文件不存在。";
        lastReloadFailureStatus = next_status;
        if (!keep_last_valid_status || !initialized) {
            status = next_status;
            initialized = false;
        }
        bool exists = false;
        lastBundleWriteTime = GetBundleWriteTime(&exists);
        hasLastBundleWriteTime = exists;
        return false;
    }

    nlohmann::json bundle;
    try {
        std::ifstream input(paths.license_path);
        if (!input.is_open()) {
            throw std::runtime_error("标准 license 文件不存在。");
        }
        input >> bundle;
    } catch (const std::exception&) {
        next_status.reason = "license 文件格式非法。";
        lastReloadFailureStatus = next_status;
        if (!keep_last_valid_status || !initialized) {
            status = next_status;
            initialized = false;
        }
        return false;
    }

    const auto payload_it = bundle.find("payload");
    const auto signature_it = bundle.find("signature");
    if (payload_it == bundle.end() || signature_it == bundle.end() || !payload_it->is_object() || !signature_it->is_string()) {
        next_status.reason = "license 文件内容非法。";
        lastReloadFailureStatus = next_status;
        if (!keep_last_valid_status || !initialized) {
            status = next_status;
            initialized = false;
        }
        return false;
    }

    const nlohmann::json payload = *payload_it;
    const std::string signature_base64 = signature_it->get<std::string>();
    next_status.customer_code = payload.value("customer_code", std::string());
    if (payload.contains("capability_scope") && payload["capability_scope"].is_array()) {
        for (const auto& item : payload["capability_scope"]) {
            if (item.is_string()) {
                next_status.capability_scope.push_back(item.get<std::string>());
            }
        }
    }
    next_status.version_constraints = payload.value("version_constraints", nlohmann::json::object());
    next_status.hardware_fingerprint = payload.value("hardware_fingerprint", std::string());

    if (!VerifySignature(payload, signature_base64, paths)) {
        next_status.reason = "签名校验失败。";
        lastReloadFailureStatus = next_status;
        if (!keep_last_valid_status || !initialized) {
            status = next_status;
            initialized = false;
        }
        return false;
    }

    const std::string start_at = NormalizeCstDateTime(payload.value("start_at_cst", std::string()));
    const std::string expire_at = NormalizeCstDateTime(payload.value("expire_at_cst", std::string()));
    const std::string now_cst = NormalizeCstDateTime(next_status.checked_at_cst);
    if (!start_at.empty() && now_cst < start_at) {
        next_status.reason = "license 尚未生效。";
        lastReloadFailureStatus = next_status;
        if (!keep_last_valid_status || !initialized) {
            status = next_status;
            initialized = false;
        }
        return false;
    }
    if (!expire_at.empty() && now_cst > expire_at) {
        next_status.reason = "license 已过期。";
        lastReloadFailureStatus = next_status;
        if (!keep_last_valid_status || !initialized) {
            status = next_status;
            initialized = false;
        }
        return false;
    }

    const std::string expected_fingerprint = payload.value("hardware_fingerprint", std::string());
    const std::string actual_fingerprint = BuildHardwareFingerprint();
    if (!expected_fingerprint.empty() && !actual_fingerprint.empty() && expected_fingerprint != actual_fingerprint) {
        next_status.reason = "硬件指纹不匹配。";
        lastReloadFailureStatus = next_status;
        if (!keep_last_valid_status || !initialized) {
            status = next_status;
            initialized = false;
        }
        return false;
    }

    next_status.valid = true;
    next_status.reason = "license 校验通过。";
    status = next_status;
    lastReloadFailureStatus = LicenseStatusInfo{};
    initialized = true;
    bool exists = false;
    lastBundleWriteTime = GetBundleWriteTime(&exists);
    hasLastBundleWriteTime = exists;
    return true;
}

void LicenseManager::AutoReloadLoop() {
    std::unique_lock<std::mutex> lock(mutex);
    while (autoReloadRunning) {
        if (autoReloadCondition.wait_for(lock, std::chrono::seconds(autoReloadIntervalSeconds), [&]() {
                return !autoReloadRunning;
            })) {
            break;
        }

        bool exists = false;
        const auto current_write_time = GetBundleWriteTime(&exists);
        const bool changed =
            exists != hasLastBundleWriteTime ||
            (exists && current_write_time != lastBundleWriteTime);
        if (!changed) {
            continue;
        }
        ReloadLocked(true);
    }
}
