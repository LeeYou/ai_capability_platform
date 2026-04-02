from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.routes import router
from app.config import get_settings
from app.db.database import get_session_factory
from app.services.runtime_service import bootstrap_runtime, initialize_database


@asynccontextmanager
async def lifespan(_: FastAPI):
    initialize_database()
    settings = get_settings()
    with get_session_factory()() as session:
        bootstrap_runtime(
            session,
            runtime_snapshot_path=settings.runtime_snapshot_path,
            runtime_log_path=settings.runtime_log_path,
            audit_log_path=settings.audit_log_path,
            host_root=settings.host_root,
            image_resource_root=settings.image_resource_root,
            license_root=settings.license_root,
            hardware_features=settings.hardware_features,
            pool_size=settings.pool_size,
            gpu_available=settings.gpu_available,
            service_name=settings.service_name,
            company_name=settings.company_name,
            company_domain=settings.company_domain,
        )
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="ai-prod backend",
        version="0.1.0",
        description="ai-prod 生产交付子系统后端服务",
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
