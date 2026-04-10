from __future__ import annotations

import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api.routes import router
from app.config import get_settings
from app.services.license_service import initialize_database


@asynccontextmanager
async def lifespan(_: FastAPI):
    initialize_database()
    yield


def _configure_frontend_routes(app: FastAPI) -> None:
    frontend_dist = Path(os.environ.get("AI_CAP_FRONTEND_DIST", "/workspace/frontend-dist"))
    index_path = frontend_dist / "index.html"
    assets_path = frontend_dist / "assets"
    if not index_path.is_file():
        return
    if assets_path.is_dir():
        app.mount("/assets", StaticFiles(directory=assets_path), name="frontend-assets")

    frontend_root = frontend_dist.resolve()

    @app.get("/", include_in_schema=False)
    def get_frontend_index() -> FileResponse:
        return FileResponse(index_path)

    @app.get("/{frontend_path:path}", include_in_schema=False)
    def get_frontend_path(frontend_path: str) -> FileResponse:
        if frontend_path.startswith(("api/", "docs", "openapi.json", "redoc")):
            raise HTTPException(status_code=404, detail="Not Found")
        candidate = (frontend_dist / frontend_path).resolve()
        if candidate.is_relative_to(frontend_root) and candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(index_path)


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="ai-license-mgr backend",
        version="0.1.0",
        description="ai-license-mgr 授权管理子系统后端服务",
        lifespan=lifespan,
    )
    app.include_router(router)
    _configure_frontend_routes(app)

    @app.get("/", tags=["system"])
    def get_root() -> dict[str, str]:
        return {
            "service": settings.service_name,
            "company_name": settings.company_name,
            "company_domain": settings.company_domain,
        }

    return app


app = create_app()
