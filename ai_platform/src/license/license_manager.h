#ifndef AI_PLATFORM_LICENSE_MANAGER_H
#define AI_PLATFORM_LICENSE_MANAGER_H

#include <atomic>
#include <chrono>
#include <condition_variable>
#include <filesystem>
#include <mutex>
#include <string>
#include <thread>

#include <vector>

namespace ai_platform {

struct LicenseFileData;

struct LicenseStatusInfo {
    bool valid = false;
    std::string version;
    std::string license_type;
    std::string customer_id;
    std::string customer_name;
    std::string issued_at;
    std::string effective_from;
    std::string expires_at;
    int grace_period_hours = 0;
    bool effective_now = false;
    bool in_grace_period = false;
    bool expired = false;
    std::string failure_reason;
    std::string failure_detail;
    std::vector<std::string> licensed_capabilities;
    std::vector<std::string> denied_capabilities;
    bool allow_reload = false;
    bool allow_admin_api = false;
    bool allow_test_page = false;
};

class LicenseManager {
public:
    LicenseManager();
    ~LicenseManager();

    bool initialize(const std::string& license_path);
    bool reload_license(const std::string& license_path = std::string());
    bool quick_check(const std::string& capability_id) const;
    LicenseStatusInfo get_status() const;
    LicenseStatusInfo get_last_reload_failure_status() const;
    void start_auto_reload_monitor(std::chrono::seconds interval);
    void stop_auto_reload_monitor();

private:
    bool reload_license_locked(const std::string& license_path, const std::string& success_event_name, const std::string& failure_event_name);
    void auto_reload_monitor_loop();
    std::filesystem::file_time_type read_license_write_time(const std::string& license_path, bool* exists) const;

    mutable std::mutex mutex_;
    std::string license_path_;
    LicenseStatusInfo status_;
    LicenseStatusInfo last_reload_failure_status_;
    std::string last_error_;
    bool initialized_ = false;
    std::filesystem::file_time_type last_license_write_time_{};
    bool has_last_license_write_time_ = false;
    std::thread auto_reload_thread_;
    std::condition_variable auto_reload_cv_;
    std::atomic<bool> auto_reload_running_{false};
    std::chrono::seconds auto_reload_interval_{0};
};

}

#endif
