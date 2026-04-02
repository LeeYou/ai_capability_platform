from __future__ import annotations

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str = Field(description="服务状态")
    service: str = Field(description="服务名称")
    company_name: str = Field(description="公司名称")
    company_domain: str = Field(description="公司域名")
    datasets_root: str = Field(description="数据集根目录")


class CapabilityItem(BaseModel):
    capability_name: str = Field(description="能力标识")
    display_name: str = Field(description="能力显示名称")
    dataset_path: str = Field(description="数据集路径")
    dataset_status: str = Field(description="数据集状态")
    source: str = Field(description="能力来源")


class DatasetItem(BaseModel):
    capability_name: str = Field(description="能力标识")
    dataset_path: str = Field(description="数据集路径")
    dataset_status: str = Field(description="数据集状态")
    source: str = Field(description="绑定来源")


class CapabilityListResponse(BaseModel):
    items: list[CapabilityItem] = Field(default_factory=list)


class DatasetListResponse(BaseModel):
    items: list[DatasetItem] = Field(default_factory=list)


class RegisterCapabilityRequest(BaseModel):
    capability_name: str = Field(min_length=1, max_length=128, description="能力标识")
    display_name: str | None = Field(default=None, min_length=1, max_length=255, description="能力显示名称")


class BindDatasetRequest(BaseModel):
    capability_name: str = Field(min_length=1, max_length=128, description="能力标识")
    dataset_path: str = Field(min_length=1, description="数据集路径，支持相对 datasets 根目录的路径")
    dataset_status: str = Field(default="ready", min_length=1, max_length=64, description="数据集状态")
