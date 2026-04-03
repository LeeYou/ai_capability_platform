#include "proxy_config.h"

#include <cstdlib>
#include <iostream>

namespace {

void clear_env() {
    unsetenv("AI_PROD_CPP_BIND_HOST");
    unsetenv("AI_PROD_CPP_BIND_PORT");
    unsetenv("AI_PROD_PY_BACKEND_HOST");
    unsetenv("AI_PROD_PY_BACKEND_PORT");
    unsetenv("AI_PROD_CPP_CONNECT_TIMEOUT_MS");
    unsetenv("AI_PROD_CPP_READ_TIMEOUT_MS");
    unsetenv("AI_PROD_CPP_WRITE_TIMEOUT_MS");
    unsetenv("AI_PROD_CPP_RUNTIME_SNAPSHOT_PATH");
    unsetenv("AI_PROD_CPP_RUNTIME_LOG_PATH");
    unsetenv("AI_PROD_CPP_AUDIT_LOG_PATH");
    unsetenv("AI_PROD_CPP_POOL_SIZE");
    unsetenv("AI_PROD_CPP_SNAPSHOT_MAX_AGE_SECONDS");
}

bool expect(bool condition, const char* message) {
    if (!condition) {
        std::cerr << message << std::endl;
        return false;
    }
    return true;
}

}

int main() {
    clear_env();

    {
        const ProxyConfig config = load_proxy_config_from_env();
        if (!expect(config.bind_host == "0.0.0.0", "default bind host mismatch")) return 1;
        if (!expect(config.bind_port == 26005, "default bind port mismatch")) return 1;
        if (!expect(config.backend_host == "127.0.0.1", "default backend host mismatch")) return 1;
        if (!expect(config.backend_port == 26004, "default backend port mismatch")) return 1;
    }

    setenv("AI_PROD_CPP_BIND_HOST", "127.0.0.1", 1);
    setenv("AI_PROD_CPP_BIND_PORT", "26105", 1);
    setenv("AI_PROD_PY_BACKEND_HOST", "127.0.0.2", 1);
    setenv("AI_PROD_PY_BACKEND_PORT", "26104", 1);
    setenv("AI_PROD_CPP_CONNECT_TIMEOUT_MS", "1234", 1);
    setenv("AI_PROD_CPP_READ_TIMEOUT_MS", "2345", 1);
    setenv("AI_PROD_CPP_WRITE_TIMEOUT_MS", "3456", 1);
    setenv("AI_PROD_CPP_RUNTIME_SNAPSHOT_PATH", "/tmp/ai_prod_runtime_snapshot.json", 1);
    setenv("AI_PROD_CPP_RUNTIME_LOG_PATH", "/tmp/ai_prod_runtime.log", 1);
    setenv("AI_PROD_CPP_AUDIT_LOG_PATH", "/tmp/ai_prod_audit.log", 1);
    setenv("AI_PROD_CPP_POOL_SIZE", "4", 1);
    setenv("AI_PROD_CPP_SNAPSHOT_MAX_AGE_SECONDS", "45", 1);

    {
        const ProxyConfig config = load_proxy_config_from_env();
        if (!expect(config.bind_host == "127.0.0.1", "override bind host mismatch")) return 1;
        if (!expect(config.bind_port == 26105, "override bind port mismatch")) return 1;
        if (!expect(config.backend_host == "127.0.0.2", "override backend host mismatch")) return 1;
        if (!expect(config.backend_port == 26104, "override backend port mismatch")) return 1;
        if (!expect(config.connect_timeout_ms == 1234, "override connect timeout mismatch")) return 1;
        if (!expect(config.read_timeout_ms == 2345, "override read timeout mismatch")) return 1;
        if (!expect(config.write_timeout_ms == 3456, "override write timeout mismatch")) return 1;
        if (!expect(config.runtime_snapshot_path == "/tmp/ai_prod_runtime_snapshot.json", "snapshot path mismatch")) return 1;
        if (!expect(config.runtime_log_path == "/tmp/ai_prod_runtime.log", "runtime log path mismatch")) return 1;
        if (!expect(config.audit_log_path == "/tmp/ai_prod_audit.log", "audit log path mismatch")) return 1;
        if (!expect(config.pool_size == 4, "pool size mismatch")) return 1;
        if (!expect(config.snapshot_max_age_seconds == 45, "snapshot max age mismatch")) return 1;
        if (!expect(build_backend_base_url(config) == "http://127.0.0.2:26104", "backend base url mismatch")) return 1;
    }

    clear_env();
    return 0;
}
