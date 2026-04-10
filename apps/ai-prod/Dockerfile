ARG AI_CAP_BASE_IMAGE=nvidia/cuda:11.8.0-cudnn8-runtime-ubuntu22.04

FROM node:22-bookworm-slim AS frontend-builder

WORKDIR /workspace/frontend

COPY apps/ai-prod/frontend/package.json apps/ai-prod/frontend/package-lock.json ./
RUN npm ci

COPY apps/ai-prod/frontend/ ./
RUN npm run build


ARG AI_CAP_BASE_IMAGE
FROM ${AI_CAP_BASE_IMAGE} AS cpp-builder

ENV DEBIAN_FRONTEND=noninteractive

WORKDIR /workspace

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    cmake \
    libssl-dev \
    pkg-config \
    && rm -rf /var/lib/apt/lists/*

COPY apps/ai-prod/cpp /workspace/apps/ai-prod/cpp

RUN rm -rf /workspace/apps/ai-prod/cpp/build

RUN cmake -S /workspace/apps/ai-prod/cpp -B /workspace/apps/ai-prod/cpp/build \
    && cmake --build /workspace/apps/ai-prod/cpp/build --parallel


ARG AI_CAP_BASE_IMAGE
FROM ${AI_CAP_BASE_IMAGE}

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    AI_CAP_HOST_ROOT=/data/ai_capability_platform \
    AI_PROD_PY_BACKEND_BIND_HOST=127.0.0.1 \
    AI_PROD_PY_BACKEND_HOST=127.0.0.1 \
    AI_PROD_PY_BACKEND_PORT=26014 \
    AI_PROD_CPP_BIND_HOST=0.0.0.0 \
    AI_PROD_CPP_BIND_PORT=26004

WORKDIR /workspace

COPY apps/ai-prod/backend/ /workspace/backend/
COPY apps/ai-prod/scripts/run_prod_stack.sh /workspace/run_prod_stack.sh
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 \
    python3-pip \
    && rm -rf /var/lib/apt/lists/*
RUN python3 -m pip install --no-cache-dir \
    cryptography==46.0.6 \
    fastapi==0.116.1 \
    uvicorn==0.35.0 \
    sqlalchemy==2.0.41

COPY --from=frontend-builder /workspace/frontend/dist /workspace/frontend-dist
COPY --from=cpp-builder /workspace/apps/ai-prod/cpp/build/ai_prod_cpp_proxy /workspace/cpp/ai_prod_cpp_proxy

RUN chmod +x /workspace/run_prod_stack.sh

EXPOSE 26004 26014

CMD ["/workspace/run_prod_stack.sh"]
