ARG AI_CAP_BASE_IMAGE=nvidia/cuda:11.8.0-cudnn8-runtime-ubuntu22.04

FROM node:22-bookworm-slim AS frontend-builder

WORKDIR /workspace/apps/ai-train/frontend

COPY apps/ai-train/frontend/package.json apps/ai-train/frontend/package-lock.json ./
RUN npm ci

COPY apps/ai-train/frontend/ /workspace/apps/ai-train/frontend/
COPY apps/frontend-common/ /workspace/apps/frontend-common/
RUN npm run build


ARG AI_CAP_BASE_IMAGE
FROM ${AI_CAP_BASE_IMAGE}

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    AI_CAP_HOST_ROOT=/data/ai_capability_platform

WORKDIR /workspace

COPY apps/ai-train/backend/ /workspace/backend/
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 \
    python3-pip \
    && rm -rf /var/lib/apt/lists/* \
    && python3 -m pip install --no-cache-dir \
    fastapi==0.116.1 \
    uvicorn==0.35.0 \
    sqlalchemy==2.0.41

COPY --from=frontend-builder /workspace/apps/ai-train/frontend/dist /workspace/frontend-dist

EXPOSE 26000

CMD ["python3", "-m", "uvicorn", "app.main:app", "--app-dir", "/workspace/backend", "--host", "0.0.0.0", "--port", "26000"]
