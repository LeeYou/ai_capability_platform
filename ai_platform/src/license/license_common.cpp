#include "license_common.h"

#include <algorithm>
#include <cstdlib>
#include <filesystem>
#include <fstream>
#include <functional>
#include <ctime>
#include <cstdio>
#include <string_view>
#include <sstream>

namespace {

constexpr const char* kLicenseSignatureSeparator = "---SIGNATURE---";

}

namespace ai_platform {

namespace {

std::string trim(const std::string& value) {
    const auto first = value.find_first_not_of(" \t\r\n");
    if (first == std::string::npos) {
        return std::string();
    }
    const auto last = value.find_last_not_of(" \t\r\n");
    return value.substr(first, last - first + 1);
}

std::vector<std::string> split(const std::string& value, char delimiter) {
    std::vector<std::string> parts;
    std::stringstream ss(value);
    std::string item;
    while (std::getline(ss, item, delimiter)) {
        item = trim(item);
        if (!item.empty()) {
            parts.push_back(item);
        }
    }
    return parts;
}

std::string join(const std::vector<std::string>& values, char delimiter) {
    std::ostringstream output;
    for (std::size_t i = 0; i < values.size(); ++i) {
        if (i > 0) {
            output << delimiter;
        }
        output << values[i];
    }
    return output.str();
}

bool parse_int(const std::string& value, int* out_value) {
    if (!out_value) {
        return false;
    }
    try {
        *out_value = std::stoi(value);
        return true;
    } catch (...) {
        return false;
    }
}

bool parse_bool(const std::string& value, bool* out_value) {
    if (!out_value) {
        return false;
    }
    if (value == "true" || value == "1") {
        *out_value = true;
        return true;
    }
    if (value == "false" || value == "0") {
        *out_value = false;
        return true;
    }
    return false;
}

bool parse_iso8601_utc(const std::string& value, std::tm* out_time) {
    if (!out_time) {
        return false;
    }

    std::tm parsed_time{};
    int year = 0;
    int month = 0;
    int day = 0;
    int hour = 0;
    int minute = 0;
    int second = 0;
    if (std::sscanf(value.c_str(), "%4d-%2d-%2dT%2d:%2d:%2dZ", &year, &month, &day, &hour, &minute, &second) != 6) {
        return false;
    }

    parsed_time.tm_year = year - 1900;
    parsed_time.tm_mon = month - 1;
    parsed_time.tm_mday = day;
    parsed_time.tm_hour = hour;
    parsed_time.tm_min = minute;
    parsed_time.tm_sec = second;
    parsed_time.tm_isdst = 0;
    *out_time = parsed_time;
    return true;
}

bool format_iso8601_utc(const std::tm& utc_time, std::string* out_value) {
    if (!out_value) {
        return false;
    }

    char buffer[32] = {0};
    if (std::strftime(buffer, sizeof(buffer), "%Y-%m-%dT%H:%M:%SZ", &utc_time) == 0) {
        return false;
    }
    *out_value = buffer;
    return true;
}

bool add_hours_to_iso8601_utc(const std::string& value, int hours, std::string* out_value) {
    std::tm utc_time{};
    if (!parse_iso8601_utc(value, &utc_time)) {
        return false;
    }

#ifdef _WIN32
    std::time_t timestamp = _mkgmtime(&utc_time);
#else
    std::time_t timestamp = timegm(&utc_time);
#endif
    if (timestamp == static_cast<std::time_t>(-1)) {
        return false;
    }

    timestamp += static_cast<std::time_t>(hours) * 60 * 60;
    std::tm adjusted_time{};
#ifdef _WIN32
    gmtime_s(&adjusted_time, &timestamp);
#else
    gmtime_r(&timestamp, &adjusted_time);
#endif
    return format_iso8601_utc(adjusted_time, out_value);
}

std::string current_time_iso8601_utc() {
    const char* override_now = std::getenv("AI_PLATFORM_LICENSE_NOW");
    if (override_now != nullptr && override_now[0] != '\0') {
        return override_now;
    }

    std::time_t now = std::time(nullptr);
    std::tm utc_time{};
#ifdef _WIN32
    gmtime_s(&utc_time, &now);
#else
    gmtime_r(&now, &utc_time);
#endif
    char buffer[32] = {0};
    std::strftime(buffer, sizeof(buffer), "%Y-%m-%dT%H:%M:%SZ", &utc_time);
    return buffer;
}

bool validate_license_time_window(const LicenseFileData& data, std::string* out_error_message) {
    const LicenseTimeStatus time_status = get_license_time_status(data);

    if (!time_status.effective_now) {
        if (out_error_message) {
            *out_error_message = "license not yet effective";
        }
        return false;
    }

    if (time_status.expired) {
        if (out_error_message) {
            *out_error_message = "license expired";
        }
        return false;
    }

    return true;
}

std::string simple_signature(const std::string& payload) {
    return std::to_string(std::hash<std::string>{}(payload));
}

bool parse_payload(const std::string& payload, LicenseFileData* out_data) {
    if (!out_data) {
        return false;
    }

    LicenseFileData data;
    std::stringstream input(payload);
    std::string line;
    while (std::getline(input, line)) {
        const auto pos = line.find('=');
        if (pos == std::string::npos) {
            continue;
        }
        const std::string key = trim(line.substr(0, pos));
        const std::string value = trim(line.substr(pos + 1));
        if (key == "license_id") {
            data.license_id = value;
        } else if (key == "version") {
            data.version = value;
        } else if (key == "license_type") {
            data.license_type = value;
        } else if (key == "customer_id") {
            data.customer_id = value;
        } else if (key == "customer_name") {
            data.customer_name = value;
        } else if (key == "issued_at") {
            data.issued_at = value;
        } else if (key == "effective_from") {
            data.effective_from = value;
        } else if (key == "expires_at") {
            data.expires_at = value;
        } else if (key == "grace_period_hours") {
            parse_int(value, &data.grace_period_hours);
        } else if (key == "machine_fingerprint") {
            data.machine_fingerprint = value;
        } else if (key == "licensed_capabilities") {
            data.licensed_capabilities = split(value, ',');
        } else if (key == "denied_capabilities") {
            data.denied_capabilities = split(value, ',');
        } else if (key == "allow_reload") {
            parse_bool(value, &data.allow_reload);
        } else if (key == "allow_admin_api") {
            parse_bool(value, &data.allow_admin_api);
        } else if (key == "allow_test_page") {
            parse_bool(value, &data.allow_test_page);
        }
    }

    if (data.license_id.empty() || data.machine_fingerprint.empty()) {
        return false;
    }

    *out_data = data;
    return true;
}

}

std::string compute_machine_fingerprint() {
    const char* computer_name = std::getenv("COMPUTERNAME");
    const char* user_name = std::getenv("USERNAME");
    std::string raw = std::string("host:") + (computer_name ? computer_name : "unknown") +
                      "|user:" + (user_name ? user_name : "unknown") +
                      "|platform:windows";
    return std::string("sha256:") + std::to_string(std::hash<std::string>{}(raw));
}

std::string build_license_payload(const LicenseFileData& data) {
    std::ostringstream output;
    output << "license_id=" << data.license_id << '\n';
    output << "version=" << data.version << '\n';
    output << "license_type=" << data.license_type << '\n';
    output << "customer_id=" << data.customer_id << '\n';
    output << "customer_name=" << data.customer_name << '\n';
    output << "issued_at=" << data.issued_at << '\n';
    output << "effective_from=" << data.effective_from << '\n';
    output << "expires_at=" << data.expires_at << '\n';
    output << "grace_period_hours=" << data.grace_period_hours << '\n';
    output << "machine_fingerprint=" << data.machine_fingerprint << '\n';
    output << "licensed_capabilities=" << join(data.licensed_capabilities, ',') << '\n';
    output << "denied_capabilities=" << join(data.denied_capabilities, ',') << '\n';
    output << "allow_reload=" << (data.allow_reload ? "true" : "false") << '\n';
    output << "allow_admin_api=" << (data.allow_admin_api ? "true" : "false") << '\n';
    output << "allow_test_page=" << (data.allow_test_page ? "true" : "false") << '\n';
    return output.str();
}

std::string sign_license_payload(const std::string& payload) {
    return simple_signature(payload);
}

std::string build_license_signature(const LicenseFileData& data) {
    return sign_license_payload(build_license_payload(data));
}

bool verify_license_signature(const std::string& payload, const std::string& signature) {
    return signature == sign_license_payload(payload);
}

LicenseTimeStatus get_license_time_status(const LicenseFileData& data) {
    LicenseTimeStatus status;
    const std::string now = current_time_iso8601_utc();

    status.effective_now = data.effective_from.empty() || now >= data.effective_from;

    if (data.expires_at.empty()) {
        return status;
    }

    std::string effective_expires_at = data.expires_at;
    if (data.grace_period_hours > 0) {
        std::string expires_at_with_grace;
        if (add_hours_to_iso8601_utc(data.expires_at, data.grace_period_hours, &expires_at_with_grace)) {
            effective_expires_at = expires_at_with_grace;
        }
    }

    status.expired = now > effective_expires_at;
    status.in_grace_period = now > data.expires_at && !status.expired;
    return status;
}

bool parse_license_file(const std::string& license_path, LicenseFileData* out_data, std::string* out_error_message) {
    if (!out_data) {
        if (out_error_message) {
            *out_error_message = "output license data is null";
        }
        return false;
    }

    std::ifstream input(license_path);
    if (!input.is_open()) {
        if (out_error_message) {
            *out_error_message = "license file open failed";
        }
        return false;
    }

    std::ostringstream buffer;
    buffer << input.rdbuf();
    const std::string content = buffer.str();

    const auto separator_pos = content.find(kLicenseSignatureSeparator);
    if (separator_pos == std::string::npos) {
        if (out_error_message) {
            *out_error_message = "license file missing signature separator";
        }
        return false;
    }

    const std::string payload = trim(content.substr(0, separator_pos));
    const std::string signature = trim(content.substr(separator_pos + std::string(kLicenseSignatureSeparator).size()));

    LicenseFileData data;
    if (!parse_payload(payload, &data) || signature.empty()) {
        if (out_error_message) {
            *out_error_message = "license file missing required fields";
        }
        return false;
    }
    data.signature = signature;

    *out_data = data;
    return true;
}

bool write_license_file(const std::string& license_path, const LicenseFileData& data, std::string* out_error_message) {
    const auto parent = std::filesystem::path(license_path).parent_path();
    if (!parent.empty()) {
        std::filesystem::create_directories(parent);
    }

    std::ofstream output(license_path, std::ios::trunc);
    if (!output.is_open()) {
        if (out_error_message) {
            *out_error_message = "license file open for write failed";
        }
        return false;
    }

    output << build_license_payload(data);
    output << kLicenseSignatureSeparator << '\n';
    output << data.signature << '\n';
    return true;
}

bool verify_license_file(const LicenseFileData& data, const std::string& expected_fingerprint, std::string* out_error_message) {
    if (data.machine_fingerprint != expected_fingerprint) {
        if (out_error_message) {
            *out_error_message = "machine fingerprint mismatch";
        }
        return false;
    }

    if (!verify_license_signature(build_license_payload(data), data.signature)) {
        if (out_error_message) {
            *out_error_message = "license signature invalid";
        }
        return false;
    }

    if (!validate_license_time_window(data, out_error_message)) {
        return false;
    }

    return true;
}

}
