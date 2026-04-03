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
    BuildArtifactItem,
    BuildArtifactListResponse,
    BuildTaskDetailResponse,
    BuildTaskItem,
    BuildTaskListResponse,
    BuildTargetItem,
    BuildTargetListResponse,
    BuilderCatalogResponse,
    CapabilityCatalogItem,
    CreateBuildTaskRequest,
    HealthResponse,
    LicenseIssueCatalogItem,
    LicensePolicyCatalogItem,
    ModelCatalogItem,
    PlatformTargetItem,
    PlatformTargetListResponse,
)
from app.services.audit_service import list_audit_logs
from app.services.build_service import (
    BuildTargetNotFoundError,
    BuildTaskNotFoundError,
    create_build_task,
    get_build_target,
    get_build_task,
    list_build_artifacts,
    list_build_targets,
    list_build_tasks,
    list_platform_targets,
)
from app.services.catalog_service import BuilderCatalogSyncError, get_builder_catalog


router = APIRouter(prefix="/api/v1")


@router.get("/health", response_model=HealthResponse, tags=["system"])
def get_health() -> HealthResponse:
    settings = get_settings()
    return HealthResponse(
        status="ok",
        service=settings.service_name,
        company_name=settings.company_name,
        company_domain=settings.company_domain,
        libs_root=str(settings.libs_root),
    )


@router.get("/catalog", response_model=BuilderCatalogResponse, tags=["catalog"])
def get_catalog() -> BuilderCatalogResponse:
    settings = get_settings()
    try:
        payload = get_builder_catalog(
            settings.build_catalog_snapshot_path,
            settings.ai_train_api_base_url,
            settings.ai_license_mgr_api_base_url,
        )
    except BuilderCatalogSyncError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
    return BuilderCatalogResponse(
        capabilities=[CapabilityCatalogItem(**item) for item in payload.get("capabilities", [])],
        models=[ModelCatalogItem(**item) for item in payload.get("models", [])],
        license_issues=[LicenseIssueCatalogItem(**item) for item in payload.get("license_issues", [])],
        license_policies=[LicensePolicyCatalogItem(**item) for item in payload.get("license_policies", [])],
        synced_at=payload.get("synced_at"),
    )


@router.get("/platform-targets", response_model=PlatformTargetListResponse, tags=["builder"])
def get_platform_targets() -> PlatformTargetListResponse:
    return PlatformTargetListResponse(items=[PlatformTargetItem(**item) for item in list_platform_targets()])


@router.get("/build-tasks", response_model=BuildTaskListResponse, tags=["builder"])
def get_build_tasks(session: Session = Depends(get_db_session)) -> BuildTaskListResponse:
    return BuildTaskListResponse(items=[BuildTaskItem(**item) for item in list_build_tasks(session)])


@router.get("/build-tasks/{task_id}", response_model=BuildTaskDetailResponse, tags=["builder"])
def get_build_task_detail(task_id: int, session: Session = Depends(get_db_session)) -> BuildTaskDetailResponse:
    try:
        return BuildTaskDetailResponse(**get_build_task(session, task_id))
    except BuildTaskNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post("/build-tasks", response_model=BuildTaskDetailResponse, status_code=status.HTTP_201_CREATED, tags=["builder"])
def create_build_task_route(
    request: CreateBuildTaskRequest,
    session: Session = Depends(get_db_session),
) -> BuildTaskDetailResponse:
    settings = get_settings()
    try:
        payload = create_build_task(
            session,
            build_catalog_snapshot_path=settings.build_catalog_snapshot_path,
            ai_train_api_base_url=settings.ai_train_api_base_url,
            ai_license_mgr_api_base_url=settings.ai_license_mgr_api_base_url,
            build_tasks_root=settings.build_tasks_root,
            build_logs_root=settings.build_logs_root,
            delivery_packages_root=settings.delivery_packages_root,
            libs_root=settings.libs_root,
            exports_root=settings.exports_root,
            audit_log_path=settings.audit_log_path,
            task_name=request.task_name,
            capability_name=request.capability_name,
            model_version=request.model_version,
            issue_record_id=request.issue_record_id,
            requested_targets=request.requested_targets,
            jni_enabled=request.jni_enabled,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return BuildTaskDetailResponse(**payload)


@router.get("/build-targets", response_model=BuildTargetListResponse, tags=["builder"])
def get_build_targets(session: Session = Depends(get_db_session)) -> BuildTargetListResponse:
    return BuildTargetListResponse(items=[BuildTargetItem(**item) for item in list_build_targets(session)])


@router.get("/build-targets/{target_id}", response_model=BuildTargetItem, tags=["builder"])
def get_build_target_detail(target_id: int, session: Session = Depends(get_db_session)) -> BuildTargetItem:
    try:
        return BuildTargetItem(**get_build_target(session, target_id))
    except BuildTargetNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get("/build-targets/{target_id}/download", tags=["builder"])
def download_build_target(target_id: int, session: Session = Depends(get_db_session)) -> FileResponse:
    try:
        target = get_build_target(session, target_id)
    except BuildTargetNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    archive_path = target["download_archive_path"]
    return FileResponse(path=archive_path, filename=Path(archive_path).name, media_type="application/zip")


@router.get("/build-tasks/{task_id}/delivery-package/download", tags=["builder"])
def download_delivery_package(task_id: int, session: Session = Depends(get_db_session)) -> FileResponse:
    try:
        task = get_build_task(session, task_id)
    except BuildTaskNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    archive_path = task.get("delivery_package_archive_path")
    if not archive_path:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="当前构建任务尚未生成 delivery_package。")
    return FileResponse(path=archive_path, filename=Path(archive_path).name, media_type="application/zip")


@router.get("/artifacts", response_model=BuildArtifactListResponse, tags=["builder"])
def get_artifacts(session: Session = Depends(get_db_session)) -> BuildArtifactListResponse:
    return BuildArtifactListResponse(items=[BuildArtifactItem(**item) for item in list_build_artifacts(session)])


@router.get("/audit-logs", response_model=AuditLogListResponse, tags=["audit"])
def get_audit_logs(limit: int = Query(default=100, ge=1, le=500)) -> AuditLogListResponse:
    settings = get_settings()
    return AuditLogListResponse(items=[AuditLogItem(**item) for item in list_audit_logs(settings.audit_log_path, limit)])
