from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str
    service: str
    company_name: str
    company_domain: str
    sdk_packages_root: str


class SdkTargetItem(BaseModel):
    target_name: str
    os_name: str
    arch_name: str
    artifact_format: str
    supports_jni: bool


class SdkTargetListResponse(BaseModel):
    items: list[SdkTargetItem] = Field(default_factory=list)


class SdkCatalogCapabilityItem(BaseModel):
    capability_name: str
    model_versions: list[str] = Field(default_factory=list)
    available_targets: list[str] = Field(default_factory=list)
    jni_available_targets: list[str] = Field(default_factory=list)


class SdkCatalogResponse(BaseModel):
    capabilities: list[SdkCatalogCapabilityItem] = Field(default_factory=list)


class CreateSdkPackageRequest(BaseModel):
    package_name: str = Field(min_length=1, max_length=128)
    capability_name: str = Field(min_length=1, max_length=128)
    model_version: str = Field(min_length=1, max_length=128)
    requested_targets: list[str] = Field(default_factory=list)
    jni_enabled: bool = False


class SdkArtifactItem(BaseModel):
    artifact_id: int
    target_id: int
    artifact_type: str
    relative_path: str
    absolute_path: str
    checksum: str


class SdkTargetDetailItem(BaseModel):
    target_id: int
    package_id: int
    target_name: str
    os_name: str
    arch_name: str
    artifact_format: str
    jni_enabled: bool
    status: str
    output_dir: str
    binary_path: str
    manifest_path: str
    checksum: str
    log_path: str
    download_archive_path: str
    artifacts: list[SdkArtifactItem] = Field(default_factory=list)


class SdkPackageItem(BaseModel):
    package_id: int
    package_name: str
    capability_name: str
    model_version: str
    requested_targets: list[str] = Field(default_factory=list)
    jni_enabled: bool
    status: str
    package_root_path: str
    log_path: str
    manifest_path: str
    started_at: str | None = None
    completed_at: str | None = None


class SdkPackageDetailResponse(SdkPackageItem):
    targets: list[SdkTargetDetailItem] = Field(default_factory=list)
    manifest: dict[str, Any] | None = None


class SdkPackageListResponse(BaseModel):
    items: list[SdkPackageItem] = Field(default_factory=list)


class AuditLogItem(BaseModel):
    happened_at_cst: str
    action: str
    entity_type: str
    entity_id: str
    detail: dict[str, Any] = Field(default_factory=dict)


class AuditLogListResponse(BaseModel):
    items: list[AuditLogItem] = Field(default_factory=list)
