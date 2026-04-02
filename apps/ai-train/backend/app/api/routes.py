from __future__ import annotations

from fastapi import APIRouter

from app.config import get_settings
from app.models import CapabilityItem, CapabilityListResponse, DatasetItem, DatasetListResponse, HealthResponse
from app.services.dataset_service import scan_dataset_bindings


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
def list_capabilities() -> CapabilityListResponse:
    settings = get_settings()
    bindings = scan_dataset_bindings(settings.datasets_root)
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


@router.get("/datasets", response_model=DatasetListResponse, tags=["dataset"])
def list_datasets() -> DatasetListResponse:
    settings = get_settings()
    bindings = scan_dataset_bindings(settings.datasets_root)
    return DatasetListResponse(
        items=[
            DatasetItem(
                capability_name=item.capability_name,
                dataset_path=item.dataset_path,
                dataset_status=item.dataset_status,
            )
            for item in bindings
        ]
    )

