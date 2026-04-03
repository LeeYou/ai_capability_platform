#!/usr/bin/env bash
set -euo pipefail

HOST_ROOT="${AI_CAP_HOST_ROOT:-/data/ai_capability_platform}"

for directory in \
  data \
  datasets \
  models \
  license \
  libs \
  configs \
  logs \
  exports
do
  mkdir -p "${HOST_ROOT}/${directory}"
done

echo "初始化完成: ${HOST_ROOT}"
