from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.database import get_db_session
from app.models import (
    CreateBatchTestRequest,
    CreateSingleTestRequest,
    HealthResponse,
    RemoteCapabilityItem,
    RemoteCapabilityListResponse,
    RemoteModelItem,
    RemoteModelListResponse,
    SyncCatalogResponse,
    TestReportDetailResponse,
    TestReportItem,
    TestReportListResponse,
    TestTaskDetailResponse,
    TestTaskItem,
    TestTaskListResponse,
)
from app.services.model_sync_service import ModelCatalogSyncError, get_model_catalog, sync_remote_model_catalog
from app.services.report_service import TestReportNotFoundError, export_test_report, get_test_report, list_test_reports
from app.services.test_service import (
    TestCaseInputPayload,
    TestTaskNotFoundError,
    create_test_task,
    get_test_task,
    list_test_tasks,
)


router = APIRouter(prefix="/api/v1")


def _task_item(payload: dict[str, object]) -> TestTaskItem:
    return TestTaskItem(**payload)


def _report_item(payload: dict[str, object]) -> TestReportItem:
    copy_payload = dict(payload)
    copy_payload.pop("summary", None)
    return TestReportItem(**copy_payload)


@router.get("/health", response_model=HealthResponse, tags=["system"])
def get_health() -> HealthResponse:
    settings = get_settings()
    return HealthResponse(
        status="ok",
        service=settings.service_name,
        company_name=settings.company_name,
        company_domain=settings.company_domain,
        models_root=str(settings.models_root),
    )


@router.post("/remote-model-catalog/sync", response_model=SyncCatalogResponse, tags=["catalog"])
def sync_model_catalog() -> SyncCatalogResponse:
    settings = get_settings()
    try:
        payload = sync_remote_model_catalog(
            settings.model_catalog_snapshot_path,
            settings.ai_train_api_base_url,
        )
    except ModelCatalogSyncError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc

    return SyncCatalogResponse(
        models=[RemoteModelItem(**item) for item in payload["models"]],
        capabilities=[RemoteCapabilityItem(**item) for item in payload["capabilities"]],
        synced_at=str(payload["synced_at"]),
    )


@router.get("/remote-models", response_model=RemoteModelListResponse, tags=["catalog"])
def get_remote_models() -> RemoteModelListResponse:
    settings = get_settings()
    try:
        payload = get_model_catalog(settings.model_catalog_snapshot_path, settings.ai_train_api_base_url)
    except ModelCatalogSyncError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
    return RemoteModelListResponse(
        items=[RemoteModelItem(**item) for item in payload["models"]],
        synced_at=payload.get("synced_at"),
    )


@router.get("/remote-capabilities", response_model=RemoteCapabilityListResponse, tags=["catalog"])
def get_remote_capabilities() -> RemoteCapabilityListResponse:
    settings = get_settings()
    try:
        payload = get_model_catalog(settings.model_catalog_snapshot_path, settings.ai_train_api_base_url)
    except ModelCatalogSyncError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
    return RemoteCapabilityListResponse(
        items=[RemoteCapabilityItem(**item) for item in payload["capabilities"]],
        synced_at=payload.get("synced_at"),
    )


@router.post("/single-tests", response_model=TestTaskDetailResponse, status_code=status.HTTP_201_CREATED, tags=["test"])
def create_single_test(
    request: CreateSingleTestRequest,
    session: Session = Depends(get_db_session),
) -> TestTaskDetailResponse:
    settings = get_settings()
    try:
        payload = create_test_task(
            session=session,
            model_catalog_snapshot_path=settings.model_catalog_snapshot_path,
            ai_train_api_base_url=settings.ai_train_api_base_url,
            datasets_root=settings.datasets_root,
            test_reports_root=settings.test_reports_root,
            task_type="single",
            capability_name=request.capability_name,
            model_version=request.model_version,
            requested_backend=request.requested_backend,
            timeout_seconds=request.timeout_seconds,
            cases=[
                TestCaseInputPayload(
                    case_name=request.case.case_name,
                    input_path=request.case.input_path,
                    expected_output=request.case.expected_output,
                )
            ],
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    return TestTaskDetailResponse(**payload)


@router.post("/batch-tests", response_model=TestTaskDetailResponse, status_code=status.HTTP_201_CREATED, tags=["test"])
def create_batch_test(
    request: CreateBatchTestRequest,
    session: Session = Depends(get_db_session),
) -> TestTaskDetailResponse:
    settings = get_settings()
    try:
        payload = create_test_task(
            session=session,
            model_catalog_snapshot_path=settings.model_catalog_snapshot_path,
            ai_train_api_base_url=settings.ai_train_api_base_url,
            datasets_root=settings.datasets_root,
            test_reports_root=settings.test_reports_root,
            task_type="batch",
            capability_name=request.capability_name,
            model_version=request.model_version,
            requested_backend=request.requested_backend,
            timeout_seconds=request.timeout_seconds,
            cases=[
                TestCaseInputPayload(
                    case_name=item.case_name,
                    input_path=item.input_path,
                    expected_output=item.expected_output,
                )
                for item in request.cases
            ],
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    return TestTaskDetailResponse(**payload)


@router.get("/test-tasks", response_model=TestTaskListResponse, tags=["test"])
def get_test_tasks(session: Session = Depends(get_db_session)) -> TestTaskListResponse:
    return TestTaskListResponse(items=[_task_item(item) for item in list_test_tasks(session)])


@router.get("/test-tasks/{task_id}", response_model=TestTaskDetailResponse, tags=["test"])
def get_test_task_detail(task_id: int, session: Session = Depends(get_db_session)) -> TestTaskDetailResponse:
    try:
        payload = get_test_task(session, task_id)
    except TestTaskNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return TestTaskDetailResponse(**payload)


@router.get("/test-reports", response_model=TestReportListResponse, tags=["report"])
def get_reports(session: Session = Depends(get_db_session)) -> TestReportListResponse:
    return TestReportListResponse(items=[_report_item(item) for item in list_test_reports(session)])


@router.get("/test-reports/{report_id}", response_model=TestReportDetailResponse, tags=["report"])
def get_report_detail(report_id: int, session: Session = Depends(get_db_session)) -> TestReportDetailResponse:
    try:
        payload = get_test_report(session, report_id)
    except TestReportNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return TestReportDetailResponse(**payload)


@router.get("/test-reports/{report_id}/export", tags=["report"])
def export_report(
    report_id: int,
    export_format: str = Query(default="json", pattern="^(json|html|pdf)$"),
    session: Session = Depends(get_db_session),
) -> FileResponse:
    settings = get_settings()
    try:
        exported_path = export_test_report(session, settings.exports_root, report_id, export_format)
    except TestReportNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    media_type_map = {
        "json": "application/json",
        "html": "text/html",
        "pdf": "application/pdf",
    }
    return FileResponse(path=exported_path, filename=exported_path.name, media_type=media_type_map[export_format])
