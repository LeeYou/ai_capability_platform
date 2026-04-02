from __future__ import annotations

from fastapi import FastAPI

from app.api.routes import router
from app.config import get_settings


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="ai-train backend",
        version="0.1.0",
        description="ai-train 训练子系统后端基础服务",
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

