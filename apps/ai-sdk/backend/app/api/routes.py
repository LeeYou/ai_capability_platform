from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import FileResponse
from pathlib import Path
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.database import get_db_session
from app.models import (
    AuditLogItem,
    AuditLogListResponse,
    CreateSdkPackageRequest,
    HealthResponse,
    SdkCatalogCapabilityItem,
    SdkCatalogResponse,
    SdkPackageDetailResponse,
    SdkPackageItem,
    SdkPackageListResponse,
    SdkTargetItem,
    SdkTargetListResponse,
)
from app.services.audit_service import list_audit_logs
from app.services.sdk_service import (
    SdkPackageNotFoundError,
    SdkTargetNotFoundError,
    create_sdk_package,
    get_sdk_catalog,
    get_sdk_package,
    get_sdk_target,
    list_sdk_packages,
    list_sdk_targets,
)


router = APIRouter(prefix="/api/v1")


@router.get("/health", response_model=HealthResponse, tags=["system"])
def get_health() -> HealthResponse:
    settings = get_settings()
    return HealthResponse(
        status="ok",
        service=settings.service_name,
        company_name=settings.company_name,
        company_domain=settings.company_domain,
        sdk_packages_root=str(settings.sdk_packages_root),
    )


@router.get("/catalog", response_model=SdkCatalogResponse, tags=["sdk"])
def get_catalog() -> SdkCatalogResponse:
    settings = get_settings()
    payload = get_sdk_catalog(settings.libs_root, settings.models_root)
    return SdkCatalogResponse(
        capabilities=[SdkCatalogCapabilityItem(**item) for item in payload["capabilities"]],
    )


@router.get("/sdk-targets", response_model=SdkTargetListResponse, tags=["sdk"])
def get_sdk_targets_route() -> SdkTargetListResponse:
    return SdkTargetListResponse(items=[SdkTargetItem(**item) for item in list_sdk_targets()])


@router.get("/packages", response_model=SdkPackageListResponse, tags=["sdk"])
def get_packages(session: Session = Depends(get_db_session)) -> SdkPackageListResponse:
    return SdkPackageListResponse(items=[SdkPackageItem(**item) for item in list_sdk_packages(session)])


@router.get("/packages/{package_id}", response_model=SdkPackageDetailResponse, tags=["sdk"])
def get_package_detail(package_id: int, session: Session = Depends(get_db_session)) -> SdkPackageDetailResponse:
    try:
        return SdkPackageDetailResponse(**get_sdk_package(session, package_id))
    except SdkPackageNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post("/packages", response_model=SdkPackageDetailResponse, status_code=status.HTTP_201_CREATED, tags=["sdk"])
def create_package_route(
    request: CreateSdkPackageRequest,
    session: Session = Depends(get_db_session),
) -> SdkPackageDetailResponse:
    settings = get_settings()
    try:
        payload = create_sdk_package(
            session,
            sdk_packages_root=settings.sdk_packages_root,
            sdk_logs_root=settings.sdk_logs_root,
            libs_root=settings.libs_root,
            models_root=settings.models_root,
            exports_root=settings.exports_root,
            audit_log_path=settings.audit_log_path,
            package_name=request.package_name,
            capability_name=request.capability_name,
            model_version=request.model_version,
            requested_targets=request.requested_targets,
            jni_enabled=request.jni_enabled,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return SdkPackageDetailResponse(**payload)


@router.get("/targets/{target_id}/download", tags=["sdk"])
def download_sdk_target(target_id: int, session: Session = Depends(get_db_session)) -> FileResponse:
    try:
        target = get_sdk_target(session, target_id)
    except SdkTargetNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    archive_path = target["download_archive_path"]
    return FileResponse(path=archive_path, filename=Path(archive_path).name, media_type="application/zip")


@router.get("/audit-logs", response_model=AuditLogListResponse, tags=["audit"])
def get_audit_logs(limit: int = Query(default=100, ge=1, le=500)) -> AuditLogListResponse:
    settings = get_settings()
    return AuditLogListResponse(items=[AuditLogItem(**item) for item in list_audit_logs(settings.audit_log_path, limit)])
