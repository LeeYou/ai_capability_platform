FROM node:22-bookworm-slim AS frontend-builder

WORKDIR /workspace/frontend

COPY apps/ai-license-mgr/frontend/package.json apps/ai-license-mgr/frontend/package-lock.json ./
RUN npm ci

COPY apps/ai-license-mgr/frontend/ ./
RUN npm run build


FROM nvidia/cuda:11.8.0-cudnn8-runtime-ubuntu22.04

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    AI_CAP_HOST_ROOT=/data/ai_capability_platform

WORKDIR /workspace

RUN apt-get update \
    && apt-get install -y --no-install-recommends python3 python3-pip python3-venv ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY apps/ai-license-mgr/backend/ /workspace/backend/
RUN python3 -m pip install --no-cache-dir \
    cryptography==46.0.6 \
    fastapi==0.116.1 \
    uvicorn==0.35.0 \
    sqlalchemy==2.0.41

COPY --from=frontend-builder /workspace/frontend/dist /workspace/frontend-dist

EXPOSE 26002

CMD ["python3", "-m", "uvicorn", "app.main:app", "--app-dir", "/workspace/backend", "--host", "0.0.0.0", "--port", "26002"]
