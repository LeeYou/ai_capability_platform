ARG AI_CAP_BASE_IMAGE=nvidia/cuda:11.8.0-cudnn8-runtime-ubuntu22.04

FROM node:22-bookworm-slim AS frontend-builder

WORKDIR /workspace/apps/ai-license-mgr/frontend

COPY apps/ai-license-mgr/frontend/package.json apps/ai-license-mgr/frontend/package-lock.json /workspace/apps/ai-license-mgr/frontend/
RUN npm ci

COPY apps/ai-license-mgr/frontend/ /workspace/apps/ai-license-mgr/frontend/
COPY apps/frontend-common/ /workspace/apps/frontend-common/
RUN npm run build


ARG AI_CAP_BASE_IMAGE
FROM ${AI_CAP_BASE_IMAGE}

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    AI_CAP_HOST_ROOT=/data/ai_capability_platform

WORKDIR /workspace

COPY apps/ai-license-mgr/backend/ /workspace/backend/
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 \
    python3-pip \
    && rm -rf /var/lib/apt/lists/* \
    && python3 -m pip install --no-cache-dir \
    cryptography==46.0.6 \
    fastapi==0.116.1 \
    uvicorn==0.35.0 \
    sqlalchemy==2.0.41

COPY --from=frontend-builder /workspace/apps/ai-license-mgr/frontend/dist /workspace/frontend-dist

EXPOSE 26002

CMD ["python3", "-m", "uvicorn", "app.main:app", "--app-dir", "/workspace/backend", "--host", "0.0.0.0", "--port", "26002"]
