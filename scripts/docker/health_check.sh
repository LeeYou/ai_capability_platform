#!/usr/bin/env bash
set -euo pipefail

declare -A SERVICES=(
  [ai-train]="http://127.0.0.1:26000/api/v1/health"
  [ai-test]="http://127.0.0.1:26001/api/v1/health"
  [ai-license-mgr]="http://127.0.0.1:26002/api/v1/health"
  [ai-builder]="http://127.0.0.1:26003/api/v1/health"
  [ai-prod]="http://127.0.0.1:26004/api/v1/health"
  [ai-sdk]="http://127.0.0.1:26005/api/v1/health"
)

for service in "${!SERVICES[@]}"; do
  url="${SERVICES[${service}]}"
  echo "检查 ${service}: ${url}"
  curl --fail --silent --show-error "${url}" >/dev/null
done

echo "全部服务健康检查通过。"
