from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.database import get_db_session
from app.models import (
    AuditLogItem,
    AuditLogListResponse,
    CapabilityItem,
    CapabilityListResponse,
    HealthResponse,
    InferRequest,
    InferResponse,
    LicenseStatusResponse,
    ReloadRequest,
    ReloadResponse,
    RuntimeOperationItem,
    RuntimeOperationListResponse,
    RuntimeRevisionItem,
    RuntimeRevisionListResponse,
)
from app.services.audit_service import list_audit_logs
from app.services.license_service import LicenseValidationError
from app.services.runtime_service import (
    get_license_status,
    infer,
    list_capabilities,
    list_runtime_operations,
    list_runtime_revisions,
    reload_runtime,
)


router = APIRouter(prefix="/api/v1")


@router.get("/health", response_model=HealthResponse, tags=["system"])
def get_health(session: Session = Depends(get_db_session)) -> HealthResponse:
    settings = get_settings()
    revisions = list_runtime_revisions(session)
    active_revision_id = revisions[-1]["revision_id"] if revisions else None
    try:
        license_status = get_license_status(
            license_root=settings.license_root,
            hardware_features=settings.hardware_features,
        )
    except LicenseValidationError as exc:
        license_status = {"valid": False, "reason": str(exc)}
    capabilities = list_capabilities()
    return HealthResponse(
        status="ok",
        service=settings.service_name,
        company_name=settings.company_name,
        company_domain=settings.company_domain,
        runtime_revision_id=active_revision_id,
        capability_count=len(capabilities),
        license_valid=bool(license_status.get("valid", False)),
    )


@router.get("/capabilities", response_model=CapabilityListResponse, tags=["runtime"])
def get_capabilities() -> CapabilityListResponse:
    return CapabilityListResponse(items=[CapabilityItem(**item) for item in list_capabilities()])


@router.get("/license/status", response_model=LicenseStatusResponse, tags=["runtime"])
def get_license_status_route() -> LicenseStatusResponse:
    settings = get_settings()
    try:
        payload = get_license_status(
            license_root=settings.license_root,
            hardware_features=settings.hardware_features,
        )
    except LicenseValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return LicenseStatusResponse(**payload)


@router.post("/infer/{capability_name}", response_model=InferResponse, tags=["runtime"])
def infer_route(capability_name: str, request: InferRequest) -> InferResponse:
    settings = get_settings()
    try:
        payload = infer(
            runtime_log_path=settings.runtime_log_path,
            audit_log_path=settings.audit_log_path,
            license_root=settings.license_root,
            hardware_features=settings.hardware_features,
            capability_name=capability_name,
            input_type=request.input_type,
            payload=request.payload,
            prefer_device=request.prefer_device,
            options=request.options,
        )
    except (ValueError, LicenseValidationError) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return InferResponse(**payload)


@router.get("/admin/revisions", response_model=RuntimeRevisionListResponse, tags=["admin"])
def get_revisions(session: Session = Depends(get_db_session)) -> RuntimeRevisionListResponse:
    return RuntimeRevisionListResponse(items=[RuntimeRevisionItem(**item) for item in list_runtime_revisions(session)])


@router.get("/admin/operations", response_model=RuntimeOperationListResponse, tags=["admin"])
def get_operations(session: Session = Depends(get_db_session)) -> RuntimeOperationListResponse:
    return RuntimeOperationListResponse(items=[RuntimeOperationItem(**item) for item in list_runtime_operations(session)])


@router.post("/admin/reload", response_model=ReloadResponse, tags=["admin"])
def reload_route(request: ReloadRequest, session: Session = Depends(get_db_session)) -> ReloadResponse:
    settings = get_settings()
    try:
        payload = reload_runtime(
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
            action=request.action,
            target_revision_id=request.target_revision_id,
        )
    except (ValueError, LicenseValidationError) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return ReloadResponse(**payload)


@router.get("/audit-logs", response_model=AuditLogListResponse, tags=["audit"])
def get_audit_logs(limit: int = Query(default=100, ge=1, le=500)) -> AuditLogListResponse:
    settings = get_settings()
    return AuditLogListResponse(items=[AuditLogItem(**item) for item in list_audit_logs(settings.audit_log_path, limit)])
