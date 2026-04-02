#!/bin/bash
set -e

echo "=========================================="
echo "  AI Platform Container Startup"
echo "  Started at: $(date -u '+%Y-%m-%dT%H:%M:%SZ')"
echo "=========================================="

APP_ROOT="/app"
HOST_ROOT="/opt/ai_platform"

mkdir -p "${HOST_ROOT}/plugins"
mkdir -p "${HOST_ROOT}/models"
mkdir -p "${HOST_ROOT}/license"
mkdir -p "${HOST_ROOT}/config"
mkdir -p "${HOST_ROOT}/logs"

if [ ! -f "${HOST_ROOT}/config/platform.yaml" ] && [ -f "${APP_ROOT}/config/platform.yaml" ]; then
    cp "${APP_ROOT}/config/platform.yaml" "${HOST_ROOT}/config/platform.yaml"
fi

if [ ! -f "${HOST_ROOT}/config/plugins_registry.txt" ] && [ -f "${APP_ROOT}/config/plugins_registry.txt" ]; then
    cp "${APP_ROOT}/config/plugins_registry.txt" "${HOST_ROOT}/config/plugins_registry.txt"
fi

export AI_PLATFORM_CONFIG_PATH="${AI_PLATFORM_CONFIG_PATH:-${HOST_ROOT}/config/platform.yaml}"
export AI_PLATFORM_PLUGINS_REGISTRY_PATH="${AI_PLATFORM_PLUGINS_REGISTRY_PATH:-${HOST_ROOT}/config/plugins_registry.txt}"
export AI_PLATFORM_LICENSE_AUDIT_LOG_PATH="${AI_PLATFORM_LICENSE_AUDIT_LOG_PATH:-${HOST_ROOT}/logs/audit.log}"
export AI_PLATFORM_RUNTIME_AUDIT_LOG_PATH="${AI_PLATFORM_RUNTIME_AUDIT_LOG_PATH:-${HOST_ROOT}/logs/runtime_audit.log}"

if [ -f "${HOST_ROOT}/license/license.dat" ]; then
    export AI_PLATFORM_LICENSE_PATH="${HOST_ROOT}/license/license.dat"
elif [ -f "${APP_ROOT}/config/license.dat" ]; then
    export AI_PLATFORM_LICENSE_PATH="${APP_ROOT}/config/license.dat"
fi

echo "[INIT] config path: ${AI_PLATFORM_CONFIG_PATH}"
echo "[INIT] plugins registry: ${AI_PLATFORM_PLUGINS_REGISTRY_PATH}"
echo "[INIT] license audit log: ${AI_PLATFORM_LICENSE_AUDIT_LOG_PATH}"
echo "[INIT] runtime audit log: ${AI_PLATFORM_RUNTIME_AUDIT_LOG_PATH}"
if [ -n "${AI_PLATFORM_LICENSE_PATH}" ]; then
    echo "[INIT] license path: ${AI_PLATFORM_LICENSE_PATH}"
else
    echo "[WARN] no license file detected under ${HOST_ROOT}/license or ${APP_ROOT}/config"
fi

if [ ! -f "${AI_PLATFORM_CONFIG_PATH}" ]; then
    echo "[ERROR] platform config not found: ${AI_PLATFORM_CONFIG_PATH}"
    exit 1
fi

if [ ! -f "${AI_PLATFORM_PLUGINS_REGISTRY_PATH}" ]; then
    echo "[ERROR] plugins registry not found: ${AI_PLATFORM_PLUGINS_REGISTRY_PATH}"
    exit 1
fi

exec "${APP_ROOT}/bin/ai_platform_server" "$@"
