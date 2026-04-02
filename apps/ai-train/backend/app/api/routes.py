from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.database import get_db_session
from app.models import (
    AnnotationTaskItem,
    AnnotationTaskListResponse,
    AppendTrainingTaskLogRequest,
    BindDatasetRequest,
    CapabilityItem,
    CapabilityListResponse,
    CreateAnnotationTaskRequest,
    CreateTrainingTaskRequest,
    DatasetItem,
    DatasetListResponse,
    HealthResponse,
    RegisterCapabilityRequest,
    SubmitAnnotationTaskRequest,
    TrainingTaskItem,
    TrainingTaskListResponse,
    UpdateTrainingTaskStatusRequest,
)
from app.services.annotation_service import (
    AnnotationTaskNotFoundError,
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
from app.services.training_service import (
    TrainingTaskNotFoundError,
    append_training_task_log,
    create_training_task,
    get_training_task,
    list_training_tasks,
    update_training_task_status,
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
    except AnnotationTaskNotFoundError as exc:
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
    except AnnotationTaskNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
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


@router.get("/training-tasks", response_model=TrainingTaskListResponse, tags=["training"])
def get_training_tasks(session: Session = Depends(get_db_session)) -> TrainingTaskListResponse:
    items = list_training_tasks(session)
    return TrainingTaskListResponse(
        items=[
            TrainingTaskItem(
                task_id=item.task_id,
                capability_name=item.capability_name,
                task_name=item.task_name,
                dataset_path=item.dataset_path,
                status=item.status,
                framework=item.framework,
                backend_type=item.backend_type,
                annotation_task_id=item.annotation_task_id,
                retry_count=item.retry_count,
                log_path=item.log_path,
                started_at=item.started_at,
                completed_at=item.completed_at,
            )
            for item in items
        ]
    )


@router.get("/training-tasks/{task_id}", response_model=TrainingTaskItem, tags=["training"])
def get_training_task_detail(task_id: int, session: Session = Depends(get_db_session)) -> TrainingTaskItem:
    try:
        item = get_training_task(session, task_id)
    except TrainingTaskNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    return TrainingTaskItem(
        task_id=item.task_id,
        capability_name=item.capability_name,
        task_name=item.task_name,
        dataset_path=item.dataset_path,
        status=item.status,
        framework=item.framework,
        backend_type=item.backend_type,
        annotation_task_id=item.annotation_task_id,
        retry_count=item.retry_count,
        log_path=item.log_path,
        started_at=item.started_at,
        completed_at=item.completed_at,
    )


@router.post(
    "/training-tasks",
    response_model=TrainingTaskItem,
    status_code=status.HTTP_201_CREATED,
    tags=["training"],
)
def create_training_task_route(
    request: CreateTrainingTaskRequest,
    session: Session = Depends(get_db_session),
) -> TrainingTaskItem:
    settings = get_settings()
    try:
        item = create_training_task(
            session=session,
            training_logs_root=settings.training_logs_root,
            capability_name=request.capability_name,
            task_name=request.task_name,
            framework=request.framework,
            backend_type=request.backend_type,
            annotation_task_id=request.annotation_task_id,
            train_params=request.train_params,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    return TrainingTaskItem(
        task_id=item.task_id,
        capability_name=item.capability_name,
        task_name=item.task_name,
        dataset_path=item.dataset_path,
        status=item.status,
        framework=item.framework,
        backend_type=item.backend_type,
        annotation_task_id=item.annotation_task_id,
        retry_count=item.retry_count,
        log_path=item.log_path,
        started_at=item.started_at,
        completed_at=item.completed_at,
    )


@router.patch("/training-tasks/{task_id}/status", response_model=TrainingTaskItem, tags=["training"])
def update_training_task_status_route(
    task_id: int,
    request: UpdateTrainingTaskStatusRequest,
    session: Session = Depends(get_db_session),
) -> TrainingTaskItem:
    try:
        item = update_training_task_status(session, task_id, request.status)
    except TrainingTaskNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    return TrainingTaskItem(
        task_id=item.task_id,
        capability_name=item.capability_name,
        task_name=item.task_name,
        dataset_path=item.dataset_path,
        status=item.status,
        framework=item.framework,
        backend_type=item.backend_type,
        annotation_task_id=item.annotation_task_id,
        retry_count=item.retry_count,
        log_path=item.log_path,
        started_at=item.started_at,
        completed_at=item.completed_at,
    )


@router.post("/training-tasks/{task_id}/logs", response_model=TrainingTaskItem, tags=["training"])
def append_training_task_log_route(
    task_id: int,
    request: AppendTrainingTaskLogRequest,
    session: Session = Depends(get_db_session),
) -> TrainingTaskItem:
    settings = get_settings()
    try:
        item = append_training_task_log(
            session=session,
            training_logs_root=settings.training_logs_root,
            task_id=task_id,
            message=request.message,
        )
    except TrainingTaskNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    return TrainingTaskItem(
        task_id=item.task_id,
        capability_name=item.capability_name,
        task_name=item.task_name,
        dataset_path=item.dataset_path,
        status=item.status,
        framework=item.framework,
        backend_type=item.backend_type,
        annotation_task_id=item.annotation_task_id,
        retry_count=item.retry_count,
        log_path=item.log_path,
        started_at=item.started_at,
        completed_at=item.completed_at,
    )
