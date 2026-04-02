from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.database import get_db_session
from app.models import (
    AnnotationTaskItem,
    AnnotationTaskListResponse,
    BindDatasetRequest,
    CapabilityItem,
    CapabilityListResponse,
    CreateAnnotationTaskRequest,
    DatasetItem,
    DatasetListResponse,
    HealthResponse,
    RegisterCapabilityRequest,
    SubmitAnnotationTaskRequest,
)
from app.services.annotation_service import (
    create_annotation_task,
    get_annotation_task,
    list_annotation_tasks,
    submit_annotation_task_result,
)
from app.services.registry_service import (
    bind_dataset_to_capability,
    list_capabilities,
    list_dataset_bindings,
    register_capability,
    sync_dataset_bindings_from_filesystem,
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
        datasets_root=str(settings.datasets_root),
    )


@router.get("/capabilities", response_model=CapabilityListResponse, tags=["capability"])
def get_capabilities(session: Session = Depends(get_db_session)) -> CapabilityListResponse:
    settings = get_settings()
    sync_dataset_bindings_from_filesystem(session, settings.datasets_root)
    bindings = list_capabilities(session)
    return CapabilityListResponse(
        items=[
            CapabilityItem(
                capability_name=item.capability_name,
                display_name=item.display_name,
                dataset_path=item.dataset_path,
                dataset_status=item.dataset_status,
                source=item.source,
            )
            for item in bindings
        ]
    )


@router.post(
    "/capabilities",
    response_model=CapabilityItem,
    status_code=status.HTTP_201_CREATED,
    tags=["capability"],
)
def create_capability(
    request: RegisterCapabilityRequest,
    session: Session = Depends(get_db_session),
) -> CapabilityItem:
    try:
        item = register_capability(
            session=session,
            capability_name=request.capability_name,
            display_name=request.display_name,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    return CapabilityItem(
        capability_name=item.capability_name,
        display_name=item.display_name,
        dataset_path=item.dataset_path,
        dataset_status=item.dataset_status,
        source=item.source,
    )


@router.get("/datasets", response_model=DatasetListResponse, tags=["dataset"])
def get_datasets(session: Session = Depends(get_db_session)) -> DatasetListResponse:
    settings = get_settings()
    sync_dataset_bindings_from_filesystem(session, settings.datasets_root)
    bindings = list_dataset_bindings(session)
    return DatasetListResponse(
        items=[
            DatasetItem(
                capability_name=item.capability_name,
                dataset_path=item.dataset_path,
                dataset_status=item.dataset_status,
                source=item.source,
            )
            for item in bindings
        ]
    )


@router.post(
    "/dataset-bindings",
    response_model=DatasetItem,
    status_code=status.HTTP_201_CREATED,
    tags=["dataset"],
)
def create_dataset_binding(
    request: BindDatasetRequest,
    session: Session = Depends(get_db_session),
) -> DatasetItem:
    settings = get_settings()
    try:
        item = bind_dataset_to_capability(
            session=session,
            datasets_root=settings.datasets_root,
            capability_name=request.capability_name,
            dataset_path=request.dataset_path,
            dataset_status=request.dataset_status,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    return DatasetItem(
        capability_name=item.capability_name,
        dataset_path=item.dataset_path,
        dataset_status=item.dataset_status,
        source=item.source,
    )


@router.get("/annotation-tasks", response_model=AnnotationTaskListResponse, tags=["annotation"])
def get_annotation_tasks(session: Session = Depends(get_db_session)) -> AnnotationTaskListResponse:
    items = list_annotation_tasks(session)
    return AnnotationTaskListResponse(
        items=[
            AnnotationTaskItem(
                task_id=item.task_id,
                capability_name=item.capability_name,
                task_name=item.task_name,
                dataset_path=item.dataset_path,
                status=item.status,
                sample_total=item.sample_total,
                labeled_count=item.labeled_count,
                result_path=item.result_path,
            )
            for item in items
        ]
    )


@router.get("/annotation-tasks/{task_id}", response_model=AnnotationTaskItem, tags=["annotation"])
def get_annotation_task_detail(
    task_id: int,
    session: Session = Depends(get_db_session),
) -> AnnotationTaskItem:
    try:
        item = get_annotation_task(session, task_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    return AnnotationTaskItem(
        task_id=item.task_id,
        capability_name=item.capability_name,
        task_name=item.task_name,
        dataset_path=item.dataset_path,
        status=item.status,
        sample_total=item.sample_total,
        labeled_count=item.labeled_count,
        result_path=item.result_path,
    )


@router.post(
    "/annotation-tasks",
    response_model=AnnotationTaskItem,
    status_code=status.HTTP_201_CREATED,
    tags=["annotation"],
)
def create_annotation_task_route(
    request: CreateAnnotationTaskRequest,
    session: Session = Depends(get_db_session),
) -> AnnotationTaskItem:
    try:
        item = create_annotation_task(
            session=session,
            capability_name=request.capability_name,
            task_name=request.task_name,
            sample_total=request.sample_total,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    return AnnotationTaskItem(
        task_id=item.task_id,
        capability_name=item.capability_name,
        task_name=item.task_name,
        dataset_path=item.dataset_path,
        status=item.status,
        sample_total=item.sample_total,
        labeled_count=item.labeled_count,
        result_path=item.result_path,
    )


@router.post(
    "/annotation-tasks/{task_id}/submit",
    response_model=AnnotationTaskItem,
    tags=["annotation"],
)
def submit_annotation_task(
    task_id: int,
    request: SubmitAnnotationTaskRequest,
    session: Session = Depends(get_db_session),
) -> AnnotationTaskItem:
    settings = get_settings()
    try:
        item = submit_annotation_task_result(
            session=session,
            annotation_tasks_root=settings.annotation_tasks_root,
            task_id=task_id,
            annotations=request.annotations,
        )
    except ValueError as exc:
        status_code = status.HTTP_404_NOT_FOUND if "不存在" in str(exc) else status.HTTP_400_BAD_REQUEST
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc

    return AnnotationTaskItem(
        task_id=item.task_id,
        capability_name=item.capability_name,
        task_name=item.task_name,
        dataset_path=item.dataset_path,
        status=item.status,
        sample_total=item.sample_total,
        labeled_count=item.labeled_count,
        result_path=item.result_path,
    )
