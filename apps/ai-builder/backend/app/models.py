from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str = Field(description="服务状态")
    service: str = Field(description="服务名称")
    company_name: str = Field(description="公司名称")
    company_domain: str = Field(description="公司域名")
    libs_root: str = Field(description="libs 根目录")


class CapabilityCatalogItem(BaseModel):
    capability_name: str
    display_name: str
    dataset_path: str
    dataset_status: str
    source: str


class ModelCatalogItem(BaseModel):
    artifact_id: int | None = None
    capability_name: str
    model_version: str
    artifact_path: str
    manifest_path: str
    backend_type: str
    checksum: str
    status: str


class LicenseIssueCatalogItem(BaseModel):
    issue_record_id: int
    policy_id: int
    customer_id: int
    customer_code: str
    key_pair_id: int
    key_name: str
    status: str
    hardware_fingerprint: str | None = None
    capability_scope: list[str] = Field(default_factory=list)
    version_constraints: dict[str, Any] = Field(default_factory=dict)
    license_path: str
    public_key_export_path: str
    issued_at_cst: str
    last_validation_at: str | None = None
    last_validation_result: str | None = None


class LicensePolicyCatalogItem(BaseModel):
    policy_id: int
    policy_name: str
    customer_id: int
    customer_code: str
    key_pair_id: int
    key_name: str
    capability_scope: list[str] = Field(default_factory=list)
    version_constraints: dict[str, Any] = Field(default_factory=dict)
    hardware_fingerprint: str | None = None
    start_at_cst: str
    expire_at_cst: str
    status: str
    notes: str | None = None


class BuilderCatalogResponse(BaseModel):
    capabilities: list[CapabilityCatalogItem] = Field(default_factory=list)
    models: list[ModelCatalogItem] = Field(default_factory=list)
    license_issues: list[LicenseIssueCatalogItem] = Field(default_factory=list)
    license_policies: list[LicensePolicyCatalogItem] = Field(default_factory=list)
    synced_at: str | None = None


class PlatformTargetItem(BaseModel):
    target_name: str
    os_name: str
    arch_name: str
    artifact_format: str
    toolchain_name: str
    supports_native_build: bool
    supports_jni: bool


class PlatformTargetListResponse(BaseModel):
    items: list[PlatformTargetItem] = Field(default_factory=list)


class BuildTaskItem(BaseModel):
    task_id: int
    task_name: str
    capability_name: str
    model_version: str
    issue_record_id: int
    requested_targets: list[str] = Field(default_factory=list)
    jni_enabled: bool
    status: str
    build_root_path: str
    log_path: str
    manifest_path: str | None = None
    started_at: str | None = None
    completed_at: str | None = None


class BuildTargetItem(BaseModel):
    target_id: int
    task_id: int
    target_name: str
    os_name: str
    arch_name: str
    artifact_format: str
    build_mode: str
    toolchain_name: str
    jni_enabled: bool
    status: str
    output_dir: str
    binary_path: str
    header_dir: str
    manifest_path: str
    checksum: str
    log_path: str
    download_archive_path: str


class BuildArtifactItem(BaseModel):
    artifact_id: int
    task_id: int
    target_id: int
    artifact_type: str
    relative_path: str
    absolute_path: str
    checksum: str


class BuildManifestItem(BaseModel):
    manifest_id: int
    task_id: int
    manifest_version: str
    manifest_path: str
    dependency_summary: dict[str, Any] = Field(default_factory=dict)
    manifest: dict[str, Any] = Field(default_factory=dict)


class BuildTaskDetailResponse(BuildTaskItem):
    targets: list[BuildTargetItem] = Field(default_factory=list)
    artifacts: list[BuildArtifactItem] = Field(default_factory=list)
    manifest: BuildManifestItem | None = None


class BuildTaskListResponse(BaseModel):
    items: list[BuildTaskItem] = Field(default_factory=list)


class BuildTargetListResponse(BaseModel):
    items: list[BuildTargetItem] = Field(default_factory=list)


class BuildArtifactListResponse(BaseModel):
    items: list[BuildArtifactItem] = Field(default_factory=list)


class CreateBuildTaskRequest(BaseModel):
    task_name: str = Field(min_length=1, max_length=255)
    capability_name: str = Field(min_length=1, max_length=128)
    model_version: str = Field(min_length=1, max_length=128)
    issue_record_id: int = Field(ge=1)
    requested_targets: list[str] = Field(default_factory=list)
    jni_enabled: bool = False


class AuditLogItem(BaseModel):
    happened_at_cst: str
    action: str
    entity_type: str
    entity_id: str
    detail: dict[str, Any] = Field(default_factory=dict)


class AuditLogListResponse(BaseModel):
    items: list[AuditLogItem] = Field(default_factory=list)
