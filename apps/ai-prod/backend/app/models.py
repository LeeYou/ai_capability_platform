from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str
    service: str
    company_name: str
    company_domain: str
    runtime_revision_id: int | None = None
    capability_count: int = 0
    license_valid: bool = False


class CapabilityItem(BaseModel):
    capability_name: str
    plugin_target: str
    model_version: str
    backend_type: str
    active_source: str
    device_mode: str
    pool_size: int
    revision_id: int | None = None


class CapabilityListResponse(BaseModel):
    items: list[CapabilityItem] = Field(default_factory=list)


class LicenseStatusResponse(BaseModel):
    valid: bool
    reason: str
    result: str
    code: str
    stage: str
    details: dict[str, Any] = Field(default_factory=dict)
    diagnostics_version: str
    checked_at_cst: str
    customer_code: str | None = None
    capability_scope: list[str] = Field(default_factory=list)
    version_constraints: dict[str, Any] = Field(default_factory=dict)
    hardware_fingerprint: str | None = None
    runtime_revision_id: int | None = None


class RuntimeRevisionItem(BaseModel):
    revision_id: int
    revision_token: str
    action: str
    status: str
    license_valid: bool
    capability_names: list[str] = Field(default_factory=list)
    source_summary: dict[str, Any] = Field(default_factory=dict)
    detail: dict[str, Any] = Field(default_factory=dict)
    rollback_of_revision_id: int | None = None
    created_at: str | None = None


class RuntimeRevisionListResponse(BaseModel):
    items: list[RuntimeRevisionItem] = Field(default_factory=list)


class RuntimeOperationItem(BaseModel):
    operation_id: int
    action: str
    status: str
    detail: dict[str, Any] = Field(default_factory=dict)
    revision_id: int | None = None
    created_at: str | None = None


class RuntimeOperationListResponse(BaseModel):
    items: list[RuntimeOperationItem] = Field(default_factory=list)


class InferRequest(BaseModel):
    input_type: Literal["json", "image", "video", "pdf"] = "json"
    payload: str = Field(min_length=1)
    prefer_device: Literal["auto", "gpu", "cpu"] = "auto"
    options: dict[str, Any] = Field(default_factory=dict)


class InferResponse(BaseModel):
    request_id: str
    capability_name: str
    model_version: str
    backend_type: str
    plugin_target: str
    device: str
    runtime_revision_id: int
    license_valid: bool
    result: dict[str, Any] = Field(default_factory=dict)


class ReloadRequest(BaseModel):
    action: Literal["reload", "rollback"] = "reload"
    target_revision_id: int | None = Field(default=None, ge=1)


class ReloadResponse(BaseModel):
    operation_id: int
    revision: RuntimeRevisionItem | None = None
    active_capability_count: int = 0


class AuditLogItem(BaseModel):
    happened_at_cst: str
    action: str
    entity_type: str
    entity_id: str
    detail: dict[str, Any] = Field(default_factory=dict)


class AuditLogListResponse(BaseModel):
    items: list[AuditLogItem] = Field(default_factory=list)
