from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.routes import router
from app.config import get_settings
from app.services.license_service import initialize_database
from platform_shared.backend.frontend import build_frontend_root_response, configure_single_page_app


@asynccontextmanager
async def lifespan(_: FastAPI):
    initialize_database()
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="ai-license-mgr backend",
        version="0.1.0",
        description="ai-license-mgr 授权管理子系统后端服务",
        lifespan=lifespan,
    )
    app.include_router(router)
    configure_single_page_app(app)

    @app.get("/", tags=["system"], response_model=None)
    def get_root() -> object:
        return build_frontend_root_response(
            {
                "service": settings.service_name,
                "company_name": settings.company_name,
                "company_domain": settings.company_domain,
            }
        )

    return app


app = create_app()
