from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

DEFAULT_FRONTEND_DIST = Path("/workspace/frontend-dist")
RESERVED_FRONTEND_PREFIXES = ("api/", "docs", "openapi.json", "redoc")


def get_frontend_dist(frontend_dist: Path | None = None) -> Path:
    return frontend_dist or DEFAULT_FRONTEND_DIST


def configure_single_page_app(app: FastAPI, *, frontend_dist: Path | None = None, mount_name: str = "frontend-assets") -> Path:
    resolved_frontend_dist = get_frontend_dist(frontend_dist)
    index_path = resolved_frontend_dist / "index.html"
    assets_path = resolved_frontend_dist / "assets"
    if not index_path.is_file():
        return index_path
    if assets_path.is_dir():
        app.mount("/assets", StaticFiles(directory=assets_path), name=mount_name)

    @app.get("/{frontend_path:path}", include_in_schema=False)
    def get_frontend_path(frontend_path: str) -> FileResponse:
        if frontend_path.startswith(RESERVED_FRONTEND_PREFIXES):
            raise HTTPException(status_code=404, detail="Not Found")
        return FileResponse(index_path)

    return index_path


def build_frontend_root_response(fallback_payload: dict[str, str], *, frontend_dist: Path | None = None) -> FileResponse | dict[str, str]:
    index_path = get_frontend_dist(frontend_dist) / "index.html"
    if index_path.is_file():
        return FileResponse(index_path)
    return fallback_payload
