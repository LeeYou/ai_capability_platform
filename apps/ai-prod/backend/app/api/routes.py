from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.database import get_db_session
from app.models import (
    AuditLogItem,
    AuditLogListResponse,
    RuntimeOperationItem,
    RuntimeOperationListResponse,
    RuntimeRevisionItem,
    RuntimeRevisionListResponse,
)
from app.services.audit_service import list_audit_logs
from app.services.runtime_service import (
    list_runtime_operations,
    list_runtime_revisions,
)


router = APIRouter()
api_router = APIRouter(prefix="/api/v1")
internal_router = APIRouter(prefix="/internal")

@internal_router.get("/admin/revisions", response_model=RuntimeRevisionListResponse, tags=["internal"])
def get_revisions(session: Session = Depends(get_db_session)) -> RuntimeRevisionListResponse:
    return RuntimeRevisionListResponse(items=[RuntimeRevisionItem(**item) for item in list_runtime_revisions(session)])


@internal_router.get("/admin/operations", response_model=RuntimeOperationListResponse, tags=["internal"])
def get_operations(session: Session = Depends(get_db_session)) -> RuntimeOperationListResponse:
    return RuntimeOperationListResponse(items=[RuntimeOperationItem(**item) for item in list_runtime_operations(session)])


@internal_router.get("/audit-logs", response_model=AuditLogListResponse, tags=["internal"])
def get_audit_logs(limit: int = Query(default=100, ge=1, le=500)) -> AuditLogListResponse:
    settings = get_settings()
    return AuditLogListResponse(items=[AuditLogItem(**item) for item in list_audit_logs(settings.audit_log_path, limit)])


router.include_router(api_router)
router.include_router(internal_router)
