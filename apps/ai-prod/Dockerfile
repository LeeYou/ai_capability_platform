ARG AI_CAP_BASE_IMAGE=nvidia/cuda:11.8.0-cudnn8-runtime-ubuntu22.04

FROM node:22-bookworm-slim AS frontend-builder

ARG HTTP_PROXY
ARG HTTPS_PROXY
ARG NO_PROXY

ENV HTTP_PROXY=${HTTP_PROXY} \
    HTTPS_PROXY=${HTTPS_PROXY} \
    NO_PROXY=${NO_PROXY} \
    http_proxy=${HTTP_PROXY} \
    https_proxy=${HTTPS_PROXY} \
    no_proxy=${NO_PROXY}

WORKDIR /workspace/apps/ai-prod/frontend

COPY apps/ai-prod/frontend/package.json apps/ai-prod/frontend/package-lock.json /workspace/apps/ai-prod/frontend/
RUN npm ci

COPY apps/ai-prod/frontend/ /workspace/apps/ai-prod/frontend/
COPY apps/frontend-common/ /workspace/apps/frontend-common/
RUN ln -s /workspace/apps/ai-prod/frontend/node_modules /workspace/apps/frontend-common/node_modules && npm run build


ARG AI_CAP_BASE_IMAGE
FROM ${AI_CAP_BASE_IMAGE} AS cpp-builder

ARG HTTP_PROXY
ARG HTTPS_PROXY
ARG NO_PROXY

ENV DEBIAN_FRONTEND=noninteractive \
    HTTP_PROXY=${HTTP_PROXY} \
    HTTPS_PROXY=${HTTPS_PROXY} \
    NO_PROXY=${NO_PROXY} \
    http_proxy=${HTTP_PROXY} \
    https_proxy=${HTTPS_PROXY} \
    no_proxy=${NO_PROXY}

WORKDIR /workspace

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    cmake \
    libsqlite3-dev \
    libssl-dev \
    pkg-config \
    && rm -rf /var/lib/apt/lists/*

COPY apps/ai-prod/cpp /workspace/apps/ai-prod/cpp

RUN rm -rf /workspace/apps/ai-prod/cpp/build

RUN cmake -S /workspace/apps/ai-prod/cpp -B /workspace/apps/ai-prod/cpp/build \
    && cmake --build /workspace/apps/ai-prod/cpp/build --parallel


ARG AI_CAP_BASE_IMAGE
FROM ${AI_CAP_BASE_IMAGE}

ARG PIP_INDEX_URL=https://pypi.org/simple
ARG PIP_DEFAULT_TIMEOUT=300
ARG PIP_RETRIES=10
ARG HTTP_PROXY
ARG HTTPS_PROXY
ARG NO_PROXY

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HTTP_PROXY=${HTTP_PROXY} \
    HTTPS_PROXY=${HTTPS_PROXY} \
    NO_PROXY=${NO_PROXY} \
    http_proxy=${HTTP_PROXY} \
    https_proxy=${HTTPS_PROXY} \
    no_proxy=${NO_PROXY} \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_PREFER_BINARY=1 \
    PIP_INDEX_URL=${PIP_INDEX_URL} \
    PIP_DEFAULT_TIMEOUT=${PIP_DEFAULT_TIMEOUT} \
    PIP_RETRIES=${PIP_RETRIES} \
    AI_CAP_HOST_ROOT=/data/ai_capability_platform \
    AI_PROD_PY_BACKEND_BIND_HOST=127.0.0.1 \
    AI_PROD_PY_BACKEND_HOST=127.0.0.1 \
    AI_PROD_PY_BACKEND_PORT=26014 \
    AI_PROD_CPP_BIND_HOST=0.0.0.0 \
    AI_PROD_CPP_BIND_PORT=26004

WORKDIR /workspace

RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 \
    python3-pip \
    && rm -rf /var/lib/apt/lists/*
RUN python3 -m pip install \
    cryptography==46.0.6 \
    fastapi==0.116.1 \
    uvicorn==0.35.0 \
    sqlalchemy==2.0.41 \
    onnxruntime==1.18.1 \
    ultralytics==8.2.50 \
    Pillow==10.4.0 \
    numpy==1.26.4
COPY apps/ai-prod/backend/ /workspace/backend/
COPY apps/ai-prod/scripts/run_prod_stack.sh /workspace/run_prod_stack.sh

COPY --from=frontend-builder /workspace/apps/ai-prod/frontend/dist /workspace/frontend-dist
COPY --from=cpp-builder /workspace/apps/ai-prod/cpp/build/ai_prod_cpp_proxy /workspace/cpp/ai_prod_cpp_proxy

RUN chmod +x /workspace/run_prod_stack.sh

EXPOSE 26004 26014

CMD ["/workspace/run_prod_stack.sh"]
