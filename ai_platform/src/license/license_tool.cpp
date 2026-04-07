#include "license_common.h"

#include <iostream>
#include <sstream>
#include <string>
#include <vector>

namespace {

std::vector<std::string> split_capabilities(const std::string& value) {
    std::vector<std::string> result;
    std::string current;
    for (char ch : value) {
        if (ch == ',') {
            if (!current.empty()) {
                result.push_back(current);
                current.clear();
            }
            continue;
        }
        current.push_back(ch);
    }
    if (!current.empty()) {
        result.push_back(current);
    }
    return result;
}

bool parse_bool_flag(const std::string& value, bool* out_value) {
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

}

int main(int argc, char** argv) {
    if (argc < 3) {
        std::cerr << "usage: license_tool <generate|verify> <license_path> [customer_name] [capabilities_csv] [--operating-system value] [--min-operating-system-version value] [--system-architecture value] [--application-name value] [--denied-capabilities value] [--allow-reload true|false] [--allow-admin-api true|false] [--allow-test-page true|false]" << std::endl;
        return 1;
    }

    const std::string mode = argv[1];
    const std::string license_path = argv[2];
    std::string error_message;

    if (mode == "generate") {
        if (argc < 5) {
            std::cerr << "generate mode requires customer_name and capabilities_csv" << std::endl;
            return 2;
        }
        ai_platform::LicenseFileData data;
        data.license_id = "LIC-DEMO-001";
        data.version = "1.0";
        data.license_type = "development";
        data.customer_id = "CUST-DEMO-001";
        data.customer_name = argv[3];
        data.issued_at = "2026-03-01T00:00:00Z";
        data.effective_from = "2026-03-01T00:00:00Z";
        data.expires_at = "2099-12-31T23:59:59Z";
        data.grace_period_hours = 24;
        data.machine_fingerprint = ai_platform::compute_machine_fingerprint();
        data.operating_system = "linux";
        data.min_operating_system_version = "";
        data.system_architecture = "";
        data.application_name = "ai-prod";
        data.licensed_capabilities = split_capabilities(argv[4]);
        data.denied_capabilities = {};
        data.allow_reload = true;
        data.allow_admin_api = true;
        data.allow_test_page = true;

        for (int i = 5; i < argc; i += 2) {
            if (i + 1 >= argc) {
                std::cerr << "missing value for option: " << argv[i] << std::endl;
                return 2;
            }

            const std::string option = argv[i];
            const std::string value = argv[i + 1];
            if (option == "--denied-capabilities") {
                data.denied_capabilities = split_capabilities(value);
            } else if (option == "--operating-system") {
                data.operating_system = value;
            } else if (option == "--min-operating-system-version") {
                data.min_operating_system_version = value;
            } else if (option == "--system-architecture") {
                data.system_architecture = value;
            } else if (option == "--application-name") {
                data.application_name = value;
            } else if (option == "--allow-reload") {
                if (!parse_bool_flag(value, &data.allow_reload)) {
                    std::cerr << "invalid bool for --allow-reload" << std::endl;
                    return 2;
                }
            } else if (option == "--allow-admin-api") {
                if (!parse_bool_flag(value, &data.allow_admin_api)) {
                    std::cerr << "invalid bool for --allow-admin-api" << std::endl;
                    return 2;
                }
            } else if (option == "--allow-test-page") {
                if (!parse_bool_flag(value, &data.allow_test_page)) {
                    std::cerr << "invalid bool for --allow-test-page" << std::endl;
                    return 2;
                }
            } else {
                std::cerr << "unknown option: " << option << std::endl;
                return 2;
            }
        }

        data.signature = ai_platform::build_license_signature(data);
        if (!ai_platform::write_license_file(license_path, data, &error_message)) {
            std::cerr << error_message << std::endl;
            return 3;
        }
        std::cout << "generated: " << license_path << std::endl;
        return 0;
    }

    if (mode == "verify") {
        ai_platform::LicenseFileData data;
        if (!ai_platform::parse_license_file(license_path, &data, &error_message)) {
            std::cerr << error_message << std::endl;
            return 4;
        }
        if (!ai_platform::verify_license_file(data, ai_platform::compute_machine_fingerprint(), &error_message)) {
            std::cerr << error_message << std::endl;
            return 5;
        }
        std::cout << "valid" << std::endl;
        return 0;
    }

    std::cerr << "unknown mode" << std::endl;
    return 6;
}
