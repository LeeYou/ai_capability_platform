from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.database import get_db_session
from app.models import (
    BindDatasetRequest,
    CapabilityItem,
    CapabilityListResponse,
    DatasetItem,
    DatasetListResponse,
    HealthResponse,
    RegisterCapabilityRequest,
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
