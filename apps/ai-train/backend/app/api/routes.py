from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.database import get_db_session
from app.models import (
    AnnotationSampleItem,
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
    ModelArtifactItem,
    ModelArtifactListResponse,
    RecordTrainingTaskResultRequest,
    RegisterCapabilityRequest,
    RegisterModelArtifactRequest,
    SubmitAnnotationTaskRequest,
    TrainingTaskItem,
    TrainingTaskListResponse,
    TrainingTaskLogSnapshot,
    UpdateAnnotationSamplesRequest,
    UpdateTrainingTaskStatusRequest,
)
from app.services.annotation_service import (
    AnnotationTaskNotFoundError,
    create_annotation_task,
    get_annotation_task_detail,
    list_annotation_tasks,
    submit_annotation_task_result,
    update_annotation_task_samples,
)
from app.services.model_service import (
    ModelArtifactNotFoundError,
    create_model_artifact,
    get_model_artifact,
    list_model_artifacts,
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
    execute_training_task,
    get_training_task_detail,
    get_training_task_log_snapshot,
    list_training_tasks,
    prepare_training_workspace,
    record_training_task_result,
    update_training_task_status,
)


router = APIRouter(prefix="/api/v1")


def _annotation_item(item) -> AnnotationTaskItem:
    sample_items = getattr(item, "sample_items", []) or []
    return AnnotationTaskItem(
        task_id=item.task_id,
        capability_name=item.capability_name,
        task_type=item.task_type,
        task_name=item.task_name,
        dataset_path=item.dataset_path,
        status=item.status,
        sample_total=item.sample_total,
        labeled_count=item.labeled_count,
        result_path=item.result_path,
        completion_ratio=item.labeled_count / item.sample_total if item.sample_total > 0 else 0.0,
        sample_items=[
            AnnotationSampleItem(
                sample_id=str(sample.get("sample_id", "")),
                status=str(sample.get("status", "pending")),
                annotation=sample.get("annotation") if isinstance(sample.get("annotation"), dict) else None,
                updated_at=sample.get("updated_at") if isinstance(sample.get("updated_at"), str) else None,
            )
            for sample in sample_items
            if isinstance(sample, dict)
        ],
        annotation_schema=item.annotation_schema,
    )


def _training_item(item) -> TrainingTaskItem:
    return TrainingTaskItem(
        task_id=item.task_id,
        capability_name=item.capability_name,
        task_type=item.task_type,
        task_name=item.task_name,
        dataset_path=item.dataset_path,
        status=item.status,
        execution_mode=item.execution_mode,
        framework=item.framework,
        backend_type=item.backend_type,
        annotation_task_id=item.annotation_task_id,
        retry_count=item.retry_count,
        log_path=item.log_path,
        workspace_path=item.workspace_path,
        started_at=item.started_at,
        completed_at=item.completed_at,
        latest_logs=item.latest_logs,
        execution_plan=item.execution_plan,
        result_summary=item.result_summary,
        training_input_path=item.training_input_path,
        template_bundle_path=item.template_bundle_path,
        export_dir=item.export_dir,
    )


def _model_item(item) -> ModelArtifactItem:
    return ModelArtifactItem(
        artifact_id=item.artifact_id,
        capability_name=item.capability_name,
        task_type=item.task_type,
        model_version=item.model_version,
        source_training_task_id=item.source_training_task_id,
        artifact_path=item.artifact_path,
        manifest_path=item.manifest_path,
        backend_type=item.backend_type,
        checksum=item.checksum,
        status=item.status,
        manifest_preview=item.manifest_preview,
        delivery_metadata=item.delivery_metadata,
        runtime_contract=item.runtime_contract,
    )


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
            task_type=item.task_type,
            dataset_path=item.dataset_path,
            dataset_status=item.dataset_status,
            source=item.source,
            annotation_schema=item.annotation_schema,
            template_bundle=item.template_bundle,
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
            task_type=request.task_type,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    return CapabilityItem(
        capability_name=item.capability_name,
        display_name=item.display_name,
        task_type=item.task_type,
        dataset_path=item.dataset_path,
        dataset_status=item.dataset_status,
        source=item.source,
        annotation_schema=item.annotation_schema,
        template_bundle=item.template_bundle,
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
    return AnnotationTaskListResponse(items=[_annotation_item(item) for item in items])


@router.get("/annotation-tasks/{task_id}", response_model=AnnotationTaskItem, tags=["annotation"])
def get_annotation_task_detail_route(
    task_id: int,
    session: Session = Depends(get_db_session),
) -> AnnotationTaskItem:
    settings = get_settings()
    try:
        item = get_annotation_task_detail(session, settings.annotation_tasks_root, task_id)
    except AnnotationTaskNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    return _annotation_item(item)


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

    return _annotation_item(item)


@router.patch(
    "/annotation-tasks/{task_id}/samples",
    response_model=AnnotationTaskItem,
    tags=["annotation"],
)
def update_annotation_task_samples_route(
    task_id: int,
    request: UpdateAnnotationSamplesRequest,
    session: Session = Depends(get_db_session),
) -> AnnotationTaskItem:
    settings = get_settings()
    try:
        item = update_annotation_task_samples(
            session=session,
            annotation_tasks_root=settings.annotation_tasks_root,
            task_id=task_id,
            annotations=request.annotations,
            mark_submitted=request.mark_submitted,
        )
    except AnnotationTaskNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    return _annotation_item(item)


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

    return _annotation_item(item)


@router.get("/training-tasks", response_model=TrainingTaskListResponse, tags=["training"])
def get_training_tasks(session: Session = Depends(get_db_session)) -> TrainingTaskListResponse:
    items = list_training_tasks(session)
    return TrainingTaskListResponse(items=[_training_item(item) for item in items])


@router.get("/training-tasks/{task_id}", response_model=TrainingTaskItem, tags=["training"])
def get_training_task_detail_route(task_id: int, session: Session = Depends(get_db_session)) -> TrainingTaskItem:
    settings = get_settings()
    try:
        item = get_training_task_detail(session, settings.training_jobs_root, task_id)
    except TrainingTaskNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    return _training_item(item)


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

    return _training_item(item)


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

    return _training_item(item)


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

    return _training_item(item)


@router.get("/training-tasks/{task_id}/logs", response_model=TrainingTaskLogSnapshot, tags=["training"])
def get_training_task_logs_route(task_id: int, session: Session = Depends(get_db_session)) -> TrainingTaskLogSnapshot:
    settings = get_settings()
    try:
        item = get_training_task_log_snapshot(session, settings.training_jobs_root, task_id)
    except TrainingTaskNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    return TrainingTaskLogSnapshot(
        task_id=item.task_id,
        status=item.status,
        execution_mode=item.execution_mode,
        log_path=item.log_path,
        latest_logs=item.latest_logs,
        execution_plan=item.execution_plan,
        result_summary=item.result_summary,
    )


@router.post("/training-tasks/{task_id}/result", response_model=TrainingTaskItem, tags=["training"])
def record_training_task_result_route(
    task_id: int,
    request: RecordTrainingTaskResultRequest,
    session: Session = Depends(get_db_session),
) -> TrainingTaskItem:
    settings = get_settings()
    try:
        item = record_training_task_result(
            session=session,
            training_jobs_root=settings.training_jobs_root,
            task_id=task_id,
            result_summary=request.result_summary,
        )
    except TrainingTaskNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    return _training_item(item)


@router.post("/training-tasks/{task_id}/prepare", response_model=TrainingTaskItem, tags=["training"])
def prepare_training_task_route(
    task_id: int,
    session: Session = Depends(get_db_session),
) -> TrainingTaskItem:
    settings = get_settings()
    try:
        item = prepare_training_workspace(
            session=session,
            training_jobs_root=settings.training_jobs_root,
            task_id=task_id,
        )
    except TrainingTaskNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    return _training_item(item)


@router.post("/training-tasks/{task_id}/execute", response_model=TrainingTaskItem, tags=["training"])
def execute_training_task_route(
    task_id: int,
    session: Session = Depends(get_db_session),
) -> TrainingTaskItem:
    settings = get_settings()
    try:
        item = execute_training_task(
            session=session,
            training_jobs_root=settings.training_jobs_root,
            training_logs_root=settings.training_logs_root,
            task_id=task_id,
        )
    except TrainingTaskNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    return _training_item(item)


@router.get("/models", response_model=ModelArtifactListResponse, tags=["model"])
def get_models(session: Session = Depends(get_db_session)) -> ModelArtifactListResponse:
    items = list_model_artifacts(session)
    return ModelArtifactListResponse(items=[_model_item(item) for item in items])


@router.get("/models/{artifact_id}", response_model=ModelArtifactItem, tags=["model"])
def get_model_detail(artifact_id: int, session: Session = Depends(get_db_session)) -> ModelArtifactItem:
    try:
        item = get_model_artifact(session, artifact_id)
    except ModelArtifactNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    return _model_item(item)


@router.post("/models", response_model=ModelArtifactItem, status_code=status.HTTP_201_CREATED, tags=["model"])
def create_model_route(
    request: RegisterModelArtifactRequest,
    session: Session = Depends(get_db_session),
) -> ModelArtifactItem:
    settings = get_settings()
    try:
        item = create_model_artifact(
            session=session,
            models_root=settings.models_root,
            capability_name=request.capability_name,
            model_version=request.model_version,
            source_training_task_id=request.source_training_task_id,
            backend_type=request.backend_type,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    return _model_item(item)
