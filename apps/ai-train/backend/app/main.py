from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.routes import router
from app.config import get_settings
from app.db.database import get_session_factory
from app.services.registry_service import initialize_database, sync_dataset_bindings_from_filesystem
from platform_shared.backend.frontend import build_frontend_root_response, configure_single_page_app


@asynccontextmanager
async def lifespan(_: FastAPI):
    settings = get_settings()
    initialize_database()
    with get_session_factory()() as session:
        sync_dataset_bindings_from_filesystem(session, settings.datasets_root)
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="ai-train backend",
        version="0.1.0",
        description="ai-train 训练子系统后端基础服务",
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
