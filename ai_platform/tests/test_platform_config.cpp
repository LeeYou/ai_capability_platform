#include "app_paths.h"
#include "platform_config.h"

#include "test_runtime_helpers.h"

#include <filesystem>
#include <fstream>
#include <string>

namespace {

void reset_platform_env() {
    ai_platform::tests::set_env_var("AI_PLATFORM_CONFIG_PATH", "");
    ai_platform::tests::set_env_var("AI_PLATFORM_LICENSE_PATH", "");
    ai_platform::tests::set_env_var("AI_PLATFORM_SERVER_HOST", "");
    ai_platform::tests::set_env_var("AI_PLATFORM_SERVER_PORT", "");
    ai_platform::tests::set_env_var("AI_PLATFORM_SERVER_WORKERS", "");
    ai_platform::tests::set_env_var("AI_PLATFORM_SERVER_REQUEST_TIMEOUT_MS", "");
    ai_platform::tests::set_env_var("AI_PLATFORM_SERVER_MAX_BODY_SIZE_MB", "");
    ai_platform::tests::set_env_var("AI_PLATFORM_SERVER_MAX_VIDEO_SIZE_MB", "");
    ai_platform::tests::set_env_var("AI_PLATFORM_LICENSE_AUTO_RELOAD_INTERVAL_SECONDS", "");
    ai_platform::tests::set_env_var("AI_PLATFORM_ADMIN_TOKEN", "");
    ai_platform::tests::set_env_var("AI_PLATFORM_PLUGINS_REGISTRY_PATH", "");
    ai_platform::tests::set_env_var("AI_PLATFORM_LICENSE_AUDIT_LOG_PATH", "");
    ai_platform::tests::set_env_var("AI_PLATFORM_RUNTIME_AUDIT_LOG_PATH", "");
}

void reset_app_paths_state() {
    ai_platform::configure_app_paths(ai_platform::AppPaths{
        "config/platform.yaml",
        "config/plugins_registry.txt",
        "logs/audit.log",
        "logs/runtime_audit.log"
    });
}

std::filesystem::path write_platform_config(const std::filesystem::path& directory,
                                            const std::string& file_name,
                                            const std::string& content) {
    std::filesystem::create_directories(directory);
    const std::filesystem::path config_path = directory / file_name;
    std::ofstream output(config_path, std::ios::trunc);
    output << content;
    output.close();
    return config_path;
}

void write_text_file(const std::filesystem::path& path, const std::string& content) {
    std::filesystem::create_directories(path.parent_path());
    std::ofstream output(path, std::ios::trunc);
    output << content;
    output.close();
}

void test_host_paths_drive_runtime_defaults(const std::filesystem::path& temp_dir) {
    const auto host_license_dir = temp_dir / "host_license";
    const auto host_config_dir = temp_dir / "host_config";
    const auto host_log_dir = temp_dir / "host_logs";
    const auto platform_config_path = write_platform_config(
        temp_dir,
        "platform_host_paths.yaml",
        "server:\n"
        "  host: 127.0.0.1\n"
        "  port: 26010\n"
        "  workers: 6\n"
        "  request_timeout_ms: 12000\n"
        "  max_body_size_mb: 16\n"
        "  max_video_size_mb: 32\n"
        "  license_auto_reload_interval_seconds: 5\n"
        "  admin_token: host-config-token\n"
        "paths:\n"
        "  host_license_dir: \"" + host_license_dir.string() + "\"\n"
        "  host_config_dir: \"" + host_config_dir.string() + "\"\n"
        "  host_log_dir: \"" + host_log_dir.string() + "\"\n");

    write_text_file(host_license_dir / "license.dat", "demo-license");
    write_text_file(host_config_dir / "plugins_registry.txt", "demo-registry");

    reset_platform_env();
    reset_app_paths_state();
    ai_platform::configure_app_paths(ai_platform::AppPaths{
        platform_config_path.string(),
        "config/plugins_registry.txt",
        "logs/audit.log",
        "logs/runtime_audit.log"
    });

    const auto loaded = ai_platform::load_platform_config();
    ai_platform::tests::assert_true(loaded.host == "127.0.0.1", "platform config host should be loaded from server section");
    ai_platform::tests::assert_true(loaded.port == 26010, "platform config port should be loaded from server section");
    ai_platform::tests::assert_true(loaded.workers == 6, "platform config workers should be loaded from server section");
    ai_platform::tests::assert_true(loaded.request_timeout_ms == 12000, "platform config request timeout should be loaded from server section");
    ai_platform::tests::assert_true(loaded.max_body_size_mb == 16, "platform config max body size should be loaded from server section");
    ai_platform::tests::assert_true(loaded.max_video_size_mb == 32, "platform config max video size should be loaded from server section");
    ai_platform::tests::assert_true(loaded.license_auto_reload_interval_seconds == 5, "platform config auto reload interval should be loaded from server section");
    ai_platform::tests::assert_true(loaded.admin_token == "host-config-token", "platform config admin token should be loaded from server section");
    ai_platform::tests::assert_true(loaded.license_path == (host_license_dir / "license.dat").string(), "license path should prefer host license dir");
    ai_platform::tests::assert_true(loaded.resolved_app_paths.plugins_registry == (host_config_dir / "plugins_registry.txt").string(), "plugins registry should prefer host config dir");
    ai_platform::tests::assert_true(loaded.resolved_app_paths.license_audit_log == (host_log_dir / "audit.log").string(), "license audit log should be derived from host log dir");
    ai_platform::tests::assert_true(loaded.resolved_app_paths.runtime_audit_log == (host_log_dir / "runtime_audit.log").string(), "runtime audit log should be derived from host log dir");
}

void test_builtin_registry_fallback(const std::filesystem::path& temp_dir) {
    const auto builtin_config_dir = temp_dir / "builtin_config";
    const auto platform_config_path = write_platform_config(
        temp_dir,
        "platform_builtin_paths.yaml",
        "paths:\n"
        "  builtin_config_dir: \"" + builtin_config_dir.string() + "\"\n");

    write_text_file(builtin_config_dir / "plugins_registry.txt", "builtin-registry");

    reset_platform_env();
    reset_app_paths_state();
    ai_platform::configure_app_paths(ai_platform::AppPaths{
        platform_config_path.string(),
        "config/plugins_registry.txt",
        "logs/audit.log",
        "logs/runtime_audit.log"
    });

    const auto loaded = ai_platform::load_platform_config();
    ai_platform::tests::assert_true(loaded.resolved_app_paths.plugins_registry == (builtin_config_dir / "plugins_registry.txt").string(), "plugins registry should fall back to builtin config dir when host registry is absent");
}

void test_environment_variables_override_platform_config(const std::filesystem::path& temp_dir) {
    const auto host_license_dir = temp_dir / "env_host_license";
    const auto host_config_dir = temp_dir / "env_host_config";
    const auto host_log_dir = temp_dir / "env_host_logs";
    const auto override_license_path = temp_dir / "override" / "license_override.dat";
    const auto override_registry_path = temp_dir / "override" / "plugins_registry_override.txt";
    const auto override_license_audit_path = temp_dir / "override_logs" / "license_audit_override.log";
    const auto override_runtime_audit_path = temp_dir / "override_logs" / "runtime_audit_override.log";
    const auto platform_config_path = write_platform_config(
        temp_dir,
        "platform_env_override.yaml",
        "server:\n"
        "  host: 127.0.0.1\n"
        "  port: 26011\n"
        "  workers: 2\n"
        "  request_timeout_ms: 15000\n"
        "  max_body_size_mb: 25\n"
        "  max_video_size_mb: 35\n"
        "  license_auto_reload_interval_seconds: 8\n"
        "  admin_token: config-admin-token\n"
        "paths:\n"
        "  host_license_dir: \"" + host_license_dir.string() + "\"\n"
        "  host_config_dir: \"" + host_config_dir.string() + "\"\n"
        "  host_log_dir: \"" + host_log_dir.string() + "\"\n");

    write_text_file(host_license_dir / "license.dat", "config-license");
    write_text_file(host_config_dir / "plugins_registry.txt", "config-registry");

    reset_platform_env();
    reset_app_paths_state();
    ai_platform::configure_app_paths(ai_platform::AppPaths{
        platform_config_path.string(),
        "config/plugins_registry.txt",
        "logs/audit.log",
        "logs/runtime_audit.log"
    });

    ai_platform::tests::set_env_var("AI_PLATFORM_SERVER_HOST", "0.0.0.0");
    ai_platform::tests::set_env_var("AI_PLATFORM_SERVER_PORT", "27000");
    ai_platform::tests::set_env_var("AI_PLATFORM_SERVER_WORKERS", "9");
    ai_platform::tests::set_env_var("AI_PLATFORM_SERVER_REQUEST_TIMEOUT_MS", "45000");
    ai_platform::tests::set_env_var("AI_PLATFORM_SERVER_MAX_BODY_SIZE_MB", "64");
    ai_platform::tests::set_env_var("AI_PLATFORM_SERVER_MAX_VIDEO_SIZE_MB", "96");
    ai_platform::tests::set_env_var("AI_PLATFORM_LICENSE_AUTO_RELOAD_INTERVAL_SECONDS", "0");
    ai_platform::tests::set_env_var("AI_PLATFORM_ADMIN_TOKEN", "env-admin-token");
    ai_platform::tests::set_env_var("AI_PLATFORM_LICENSE_PATH", override_license_path.string());
    ai_platform::tests::set_env_var("AI_PLATFORM_PLUGINS_REGISTRY_PATH", override_registry_path.string());
    ai_platform::tests::set_env_var("AI_PLATFORM_LICENSE_AUDIT_LOG_PATH", override_license_audit_path.string());
    ai_platform::tests::set_env_var("AI_PLATFORM_RUNTIME_AUDIT_LOG_PATH", override_runtime_audit_path.string());

    const auto loaded = ai_platform::load_platform_config();
    ai_platform::tests::assert_true(loaded.host == "0.0.0.0", "server host env should override platform config");
    ai_platform::tests::assert_true(loaded.port == 27000, "server port env should override platform config");
    ai_platform::tests::assert_true(loaded.workers == 9, "server workers env should override platform config");
    ai_platform::tests::assert_true(loaded.request_timeout_ms == 45000, "request timeout env should override platform config");
    ai_platform::tests::assert_true(loaded.max_body_size_mb == 64, "max body size env should override platform config");
    ai_platform::tests::assert_true(loaded.max_video_size_mb == 96, "max video size env should override platform config");
    ai_platform::tests::assert_true(loaded.license_auto_reload_interval_seconds == 0, "license auto reload env should override platform config");
    ai_platform::tests::assert_true(loaded.admin_token == "env-admin-token", "admin token env should override platform config");
    ai_platform::tests::assert_true(loaded.license_path == override_license_path.string(), "license path env should override platform config");
    ai_platform::tests::assert_true(loaded.resolved_app_paths.plugins_registry == override_registry_path.string(), "registry env should override platform config");
    ai_platform::tests::assert_true(loaded.resolved_app_paths.license_audit_log == override_license_audit_path.string(), "license audit log env should override platform config");
    ai_platform::tests::assert_true(loaded.resolved_app_paths.runtime_audit_log == override_runtime_audit_path.string(), "runtime audit log env should override platform config");
}

}

int main() {
    const std::filesystem::path temp_dir = std::filesystem::temp_directory_path() / "ai_platform_platform_config_tests";
    std::filesystem::remove_all(temp_dir);
    std::filesystem::create_directories(temp_dir);

    test_host_paths_drive_runtime_defaults(temp_dir / "host_paths_case");
    test_builtin_registry_fallback(temp_dir / "builtin_fallback_case");
    test_environment_variables_override_platform_config(temp_dir / "env_override_case");

    reset_platform_env();
    reset_app_paths_state();
    return 0;
}
