ARG AI_CAP_BASE_IMAGE=nvidia/cuda:11.8.0-cudnn8-runtime-ubuntu22.04

FROM node:22-bookworm-slim AS frontend-builder

WORKDIR /workspace/apps/ai-test/frontend

COPY apps/ai-test/frontend/package.json apps/ai-test/frontend/package-lock.json /workspace/apps/ai-test/frontend/
RUN npm ci

COPY apps/ai-test/frontend/ /workspace/apps/ai-test/frontend/
COPY apps/frontend-common/ /workspace/apps/frontend-common/
RUN npm run build


ARG AI_CAP_BASE_IMAGE
FROM ${AI_CAP_BASE_IMAGE}

ARG PIP_INDEX_URL=https://pypi.org/simple
ARG PIP_DEFAULT_TIMEOUT=300
ARG PIP_RETRIES=10

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_PREFER_BINARY=1 \
    PIP_INDEX_URL=${PIP_INDEX_URL} \
    PIP_DEFAULT_TIMEOUT=${PIP_DEFAULT_TIMEOUT} \
    PIP_RETRIES=${PIP_RETRIES} \
    AI_CAP_HOST_ROOT=/data/ai_capability_platform

WORKDIR /workspace

COPY apps/ai-test/backend/ /workspace/backend/
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 \
    python3-pip \
    && rm -rf /var/lib/apt/lists/* \
    && python3 -m pip install \
    fastapi==0.116.1 \
    uvicorn==0.35.0 \
    sqlalchemy==2.0.41 \
    onnxruntime==1.23.2

COPY --from=frontend-builder /workspace/apps/ai-test/frontend/dist /workspace/frontend-dist

EXPOSE 26001

CMD ["python3", "-m", "uvicorn", "app.main:app", "--app-dir", "/workspace/backend", "--host", "0.0.0.0", "--port", "26001"]
