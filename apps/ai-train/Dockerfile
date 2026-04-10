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

WORKDIR /workspace/apps/ai-train/frontend

COPY apps/ai-train/frontend/package.json apps/ai-train/frontend/package-lock.json /workspace/apps/ai-train/frontend/
RUN npm ci

COPY apps/ai-train/frontend/ /workspace/apps/ai-train/frontend/
COPY apps/frontend-common/ /workspace/apps/frontend-common/
RUN npm run build


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
    AI_CAP_HOST_ROOT=/data/ai_capability_platform

WORKDIR /workspace

RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 \
    python3-pip \
    && rm -rf /var/lib/apt/lists/*
RUN python3 -m pip install \
    fastapi==0.116.1 \
    uvicorn==0.35.0 \
    sqlalchemy==2.0.41
COPY apps/ai-train/backend/ /workspace/backend/

COPY --from=frontend-builder /workspace/apps/ai-train/frontend/dist /workspace/frontend-dist

EXPOSE 26000

CMD ["python3", "-m", "uvicorn", "app.main:app", "--app-dir", "/workspace/backend", "--host", "0.0.0.0", "--port", "26000"]
