FROM ubuntu:22.04 AS builder

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    cmake \
    pkg-config \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /build/src
COPY . /build/src

RUN cmake -S /build/src -B /build/build \
    -DCMAKE_BUILD_TYPE=Release \
    -DBUILD_SERVER=ON \
    -DBUILD_PLUGINS=ON \
    -DBUILD_TESTS=OFF \
    -DBUILD_JNI_WRAPPERS=OFF \
    -DBUILD_WINDOWS_DLL=OFF \
    && cmake --build /build/build --config Release --target ai_platform_server cap_face_detect cap_liveness_action cap_idcard_detect cap_doc_classify cap_seal_detect

FROM ubuntu:22.04 AS runtime

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    curl \
    bash \
    && rm -rf /var/lib/apt/lists/*

RUN mkdir -p /app/bin /app/plugins /app/models /app/config /app/logs \
    && mkdir -p /opt/ai_platform/plugins \
    && mkdir -p /opt/ai_platform/models \
    && mkdir -p /opt/ai_platform/license \
    && mkdir -p /opt/ai_platform/config \
    && mkdir -p /opt/ai_platform/logs

COPY --from=builder /build/build/bin/Release/ai_platform_server /app/bin/ai_platform_server
COPY --from=builder /build/build/bin/Release/libcap_face_detect.so /app/plugins/libcap_face_detect.so
COPY --from=builder /build/build/bin/Release/libcap_liveness_action.so /app/plugins/libcap_liveness_action.so
COPY --from=builder /build/build/bin/Release/libcap_idcard_detect.so /app/plugins/libcap_idcard_detect.so
COPY --from=builder /build/build/bin/Release/libcap_doc_classify.so /app/plugins/libcap_doc_classify.so
COPY --from=builder /build/build/bin/Release/libcap_seal_detect.so /app/plugins/libcap_seal_detect.so
COPY config/ /app/config/
COPY docker/plugins_registry.txt /app/config/plugins_registry.txt
COPY models/ /app/models/
COPY deploy/host_template/ /opt/ai_platform/
COPY docker/plugins_registry.txt /opt/ai_platform/config/plugins_registry.txt
COPY docker/entrypoint.sh /app/entrypoint.sh

RUN chmod +x /app/entrypoint.sh \
    && chmod +x /app/bin/ai_platform_server

WORKDIR /app

ENV AI_PLATFORM_CONFIG_PATH=/opt/ai_platform/config/platform.yaml
ENV AI_PLATFORM_PLUGINS_REGISTRY_PATH=/opt/ai_platform/config/plugins_registry.txt
ENV AI_PLATFORM_LICENSE_AUDIT_LOG_PATH=/opt/ai_platform/logs/audit.log
ENV AI_PLATFORM_RUNTIME_AUDIT_LOG_PATH=/opt/ai_platform/logs/runtime_audit.log

EXPOSE 26000

HEALTHCHECK --interval=30s --timeout=10s --retries=3 --start-period=20s \
    CMD curl -fsS http://127.0.0.1:26000/api/v1/health || exit 1

ENTRYPOINT ["/app/entrypoint.sh"]
