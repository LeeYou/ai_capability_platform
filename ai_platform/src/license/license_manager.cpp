#include "license_manager.h"

#include "app_paths.h"
#include "license_common.h"

#include <algorithm>

#include <chrono>
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <sstream>

#include <system_error>

namespace ai_platform {

namespace {

std::string build_audit_timestamp() {
    const auto now = std::chrono::system_clock::now();
    const std::time_t now_time = std::chrono::system_clock::to_time_t(now);
    std::tm utc_time{};
#ifdef _WIN32
    gmtime_s(&utc_time, &now_time);
#else
    gmtime_r(&now_time, &now_time);
#endif
    std::ostringstream oss;
    oss << std::put_time(&utc_time, "%Y-%m-%dT%H:%M:%SZ");
    return oss.str();
}

void append_license_audit_log(
    const std::string& event_name,
    const std::string& license_path,
    const LicenseStatusInfo& status,
    const std::string& detail) {
    const std::filesystem::path audit_log_path(app_paths().license_audit_log);
    const auto parent = audit_log_path.parent_path();
    if (!parent.empty()) {
        std::filesystem::create_directories(parent);
    }

    std::ofstream output(audit_log_path, std::ios::app);
    if (!output.is_open()) {
        return;
    }

    output << '[' << build_audit_timestamp() << "] [LICENSE] event=" << event_name
           << " license_path=" << license_path
           << " valid=" << (status.valid ? "true" : "false")
           << " customer_id=" << status.customer_id
           << " license_type=" << status.license_type
           << " expires_at=" << status.expires_at
           << " allow_reload=" << (status.allow_reload ? "true" : "false")
           << " allow_admin_api=" << (status.allow_admin_api ? "true" : "false")
           << " allow_test_page=" << (status.allow_test_page ? "true" : "false")
           << " failure_reason=" << status.failure_reason
           << " detail=" << detail
           << std::endl;
}

std::string map_failure_reason(const std::string& error_message) {
    if (error_message == "license file open failed") {
        return kLicenseFailureReasonFileOpenFailed;
    }
    if (error_message == "license file missing signature separator") {
        return kLicenseFailureReasonFormatInvalid;
    }
    if (error_message == "license file missing required fields") {
        return kLicenseFailureReasonFieldsMissing;
    }
    if (error_message == "machine fingerprint mismatch") {
        return kLicenseFailureReasonFingerprintMismatch;
    }
    if (error_message == "license signature invalid") {
        return kLicenseFailureReasonSignatureInvalid;
    }
    if (error_message == "license not yet effective") {
        return kLicenseFailureReasonNotYetEffective;
    }
    if (error_message == "license expired") {
        return kLicenseFailureReasonExpired;
    }
    if (!error_message.empty()) {
        return kLicenseFailureReasonInvalid;
    }
    return std::string();
}

void fill_status_from_license_data(
    LicenseStatusInfo* status,
    const LicenseFileData& license_data,
    const LicenseTimeStatus& time_status,
    const std::string& failure_detail) {
    if (!status) {
        return;
    }

    status->version = license_data.version;
    status->license_type = license_data.license_type;
    status->customer_id = license_data.customer_id;
    status->customer_name = license_data.customer_name;
    status->issued_at = license_data.issued_at;
    status->effective_from = license_data.effective_from;
    status->expires_at = license_data.expires_at;
    status->grace_period_hours = license_data.grace_period_hours;
    status->effective_now = time_status.effective_now;
    status->in_grace_period = time_status.in_grace_period;
    status->expired = time_status.expired;
    status->failure_reason = map_failure_reason(failure_detail);
    status->failure_detail = failure_detail;
    status->licensed_capabilities = license_data.licensed_capabilities;
    status->denied_capabilities = license_data.denied_capabilities;
    status->allow_reload = license_data.allow_reload;
    status->allow_admin_api = license_data.allow_admin_api;
    status->allow_test_page = license_data.allow_test_page;
}

bool load_license_status(
    const std::string& license_path,
    LicenseStatusInfo* status,
    std::string* last_error,
    bool* initialized) {
    if (!status || !last_error || !initialized) {
        return false;
    }

    *status = LicenseStatusInfo{};
    last_error->clear();
    *initialized = false;

    LicenseFileData license_data;
    if (!parse_license_file(license_path, &license_data, last_error)) {
        return false;
    }

    const auto time_status = get_license_time_status(license_data);
    if (!verify_license_file(license_data, compute_machine_fingerprint(), last_error)) {
        fill_status_from_license_data(status, license_data, time_status, *last_error);
        return false;
    }

    status->valid = true;
    fill_status_from_license_data(status, license_data, time_status, std::string());
    *initialized = true;
    return true;
}

}

LicenseManager::LicenseManager() = default;

LicenseManager::~LicenseManager() {
    stop_auto_reload_monitor();
}

bool LicenseManager::initialize(const std::string& license_path) {
    std::lock_guard<std::mutex> lock(mutex_);
    license_path_ = license_path;
    last_reload_failure_status_ = LicenseStatusInfo{};
    const bool ok = load_license_status(license_path_, &status_, &last_error_, &initialized_);
    bool exists = false;
    last_license_write_time_ = read_license_write_time(license_path_, &exists);
    has_last_license_write_time_ = exists;
    append_license_audit_log(
        ok ? "initialize_success" : "initialize_failure",
        license_path_,
        status_,
        ok ? "license initialized" : last_error_);
    return ok;
}

bool LicenseManager::reload_license(const std::string& license_path) {
    std::lock_guard<std::mutex> lock(mutex_);
    return reload_license_locked(license_path, "reload_success", "reload_failure");
}

bool LicenseManager::reload_license_locked(
    const std::string& license_path,
    const std::string& success_event_name,
    const std::string& failure_event_name) {
    const std::string target_license_path = license_path.empty() ? license_path_ : license_path;
    if (target_license_path.empty()) {
        last_reload_failure_status_ = LicenseStatusInfo{};
        last_reload_failure_status_.failure_reason = map_failure_reason("license file open failed");
        last_reload_failure_status_.failure_detail = "license file open failed";
        if (!initialized_) {
            license_path_.clear();
            status_ = LicenseStatusInfo{};
            last_error_ = "license file open failed";
        }
        append_license_audit_log(
            failure_event_name,
            target_license_path,
            last_reload_failure_status_,
            last_reload_failure_status_.failure_detail);
        return false;
    }

    LicenseStatusInfo reloaded_status;
    std::string reloaded_error;
    bool reloaded_initialized = false;
    const bool ok = load_license_status(target_license_path, &reloaded_status, &reloaded_error, &reloaded_initialized);
    if (!ok) {
        last_reload_failure_status_ = reloaded_status;
        if (last_reload_failure_status_.failure_reason.empty() && !reloaded_error.empty()) {
            last_reload_failure_status_.failure_reason = map_failure_reason(reloaded_error);
            last_reload_failure_status_.failure_detail = reloaded_error;
        }
        if (!initialized_) {
            license_path_ = target_license_path;
            status_ = reloaded_status;
            last_error_ = reloaded_error;
            initialized_ = false;
        }
        bool exists = false;
        last_license_write_time_ = read_license_write_time(target_license_path, &exists);
        has_last_license_write_time_ = exists;
        append_license_audit_log(
            failure_event_name,
            target_license_path,
            last_reload_failure_status_,
            last_reload_failure_status_.failure_detail);
        return false;
    }

    license_path_ = target_license_path;
    status_ = reloaded_status;
    last_error_ = reloaded_error;
    initialized_ = reloaded_initialized;
    last_reload_failure_status_ = LicenseStatusInfo{};
    bool exists = false;
    last_license_write_time_ = read_license_write_time(license_path_, &exists);
    has_last_license_write_time_ = exists;
    append_license_audit_log(
        success_event_name,
        license_path_,
        status_,
        "license reloaded");
    return true;
}

bool LicenseManager::quick_check(const std::string& capability_id) const {
    std::lock_guard<std::mutex> lock(mutex_);
    if (!initialized_ || capability_id.empty()) {
        return false;
    }

    if (!status_.valid) {
        return false;
    }

    if (std::find(
            status_.denied_capabilities.begin(),
            status_.denied_capabilities.end(),
            capability_id) != status_.denied_capabilities.end()) {
        return false;
    }

    return std::find(
        status_.licensed_capabilities.begin(),
        status_.licensed_capabilities.end(),
        capability_id) != status_.licensed_capabilities.end();
}

LicenseStatusInfo LicenseManager::get_status() const {
    std::lock_guard<std::mutex> lock(mutex_);
    return status_;
}

LicenseStatusInfo LicenseManager::get_last_reload_failure_status() const {
    std::lock_guard<std::mutex> lock(mutex_);
    return last_reload_failure_status_;
}

void LicenseManager::start_auto_reload_monitor(std::chrono::seconds interval) {
    if (interval.count() <= 0) {
        return;
    }

    stop_auto_reload_monitor();
    auto_reload_interval_ = interval;
    auto_reload_running_ = true;
    auto_reload_thread_ = std::thread(&LicenseManager::auto_reload_monitor_loop, this);
}

void LicenseManager::stop_auto_reload_monitor() {
    auto_reload_running_ = false;
    auto_reload_cv_.notify_all();
    if (auto_reload_thread_.joinable()) {
        auto_reload_thread_.join();
    }
}

void LicenseManager::auto_reload_monitor_loop() {
    std::unique_lock<std::mutex> wait_lock(mutex_);
    while (auto_reload_running_) {
        if (auto_reload_cv_.wait_for(wait_lock, auto_reload_interval_, [this]() {
                return !auto_reload_running_.load();
            })) {
            break;
        }

        const std::string monitored_path = license_path_;
        wait_lock.unlock();

        bool exists = false;
        const auto current_write_time = read_license_write_time(monitored_path, &exists);

        wait_lock.lock();
        if (!auto_reload_running_) {
            break;
        }

        const bool changed = monitored_path != license_path_
            ? true
            : (exists != has_last_license_write_time_) || (exists && current_write_time != last_license_write_time_);
        if (changed) {
            reload_license_locked(std::string(), "auto_reload_success", "auto_reload_failure");
        }
    }
}

std::filesystem::file_time_type LicenseManager::read_license_write_time(const std::string& license_path, bool* exists) const {
    if (exists) {
        *exists = false;
    }
    if (license_path.empty()) {
        return std::filesystem::file_time_type{};
    }

    std::error_code error_code;
    const auto status = std::filesystem::status(license_path, error_code);
    if (error_code || !std::filesystem::exists(status)) {
        return std::filesystem::file_time_type{};
    }

    const auto write_time = std::filesystem::last_write_time(license_path, error_code);
    if (error_code) {
        return std::filesystem::file_time_type{};
    }

    if (exists) {
        *exists = true;
    }
    return write_time;
}

}
