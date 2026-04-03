from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.routes import router
from app.config import get_settings
from app.services.build_service import initialize_database


@asynccontextmanager
async def lifespan(_: FastAPI):
    initialize_database()
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="ai-builder backend",
        version="0.1.0",
        description="ai-builder 推理库构建子系统后端服务",
        lifespan=lifespan,
    )
    app.include_router(router)

    @app.get("/", tags=["system"])
    def get_root() -> dict[str, str]:
        return {
            "service": settings.service_name,
            "company_name": settings.company_name,
            "company_domain": settings.company_domain,
        }

    return app


app = create_app()
