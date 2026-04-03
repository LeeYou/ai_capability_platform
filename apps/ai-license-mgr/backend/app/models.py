from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str = Field(description="服务状态")
    service: str = Field(description="服务名称")
    company_name: str = Field(description="公司名称")
    company_domain: str = Field(description="公司域名")
    license_root: str = Field(description="license 根目录")


class CustomerItem(BaseModel):
    customer_id: int = Field(description="客户 ID")
    customer_code: str = Field(description="客户编码")
    customer_name: str = Field(description="客户名称")
    contact_name: str | None = Field(default=None, description="联系人")
    contact_email: str | None = Field(default=None, description="联系邮箱")
    status: str = Field(description="客户状态")


class CustomerListResponse(BaseModel):
    items: list[CustomerItem] = Field(default_factory=list)


class CreateCustomerRequest(BaseModel):
    customer_code: str = Field(min_length=1, max_length=128, description="客户编码")
    customer_name: str = Field(min_length=1, max_length=255, description="客户名称")
    contact_name: str | None = Field(default=None, max_length=255, description="联系人")
    contact_email: str | None = Field(default=None, max_length=255, description="联系邮箱")


class KeyPairItem(BaseModel):
    key_pair_id: int = Field(description="密钥对 ID")
    key_name: str = Field(description="密钥名称")
    algorithm: str = Field(description="算法")
    public_key_path: str = Field(description="公钥路径")
    private_key_path: str = Field(description="私钥路径")
    status: str = Field(description="状态")


class KeyPairListResponse(BaseModel):
    items: list[KeyPairItem] = Field(default_factory=list)


class CreateKeyPairRequest(BaseModel):
    key_name: str = Field(min_length=1, max_length=128, description="密钥名称")


class LicensePolicyItem(BaseModel):
    policy_id: int = Field(description="策略 ID")
    policy_name: str = Field(description="策略名称")
    customer_id: int = Field(description="客户 ID")
    customer_code: str = Field(description="客户编码")
    key_pair_id: int = Field(description="密钥对 ID")
    key_name: str = Field(description="密钥名称")
    capability_scope: list[str] = Field(default_factory=list, description="能力范围")
    version_constraints: dict[str, Any] = Field(default_factory=dict, description="版本约束")
    hardware_fingerprint: str | None = Field(default=None, description="硬件指纹")
    start_at_cst: str = Field(description="生效时间")
    expire_at_cst: str = Field(description="到期时间")
    status: str = Field(description="状态")
    notes: str | None = Field(default=None, description="备注")


class LicensePolicyListResponse(BaseModel):
    items: list[LicensePolicyItem] = Field(default_factory=list)


class CreateLicensePolicyRequest(BaseModel):
    policy_name: str = Field(min_length=1, max_length=128, description="策略名称")
    customer_id: int = Field(description="客户 ID")
    key_pair_id: int = Field(description="密钥对 ID")
    capability_scope: list[str] = Field(default_factory=list, description="能力范围")
    version_constraints: dict[str, Any] = Field(default_factory=dict, description="版本约束")
    hardware_fingerprint: str | None = Field(default=None, min_length=1, max_length=128, description="硬件指纹")
    start_at_cst: str = Field(min_length=1, description="生效时间，必须为 CST 时区 ISO 8601")
    expire_at_cst: str = Field(min_length=1, description="到期时间，必须为 CST 时区 ISO 8601")
    notes: str | None = Field(default=None, max_length=2000, description="备注")


class IssueLicenseRequest(BaseModel):
    policy_id: int = Field(description="策略 ID")


class LicenseIssueItem(BaseModel):
    issue_record_id: int = Field(description="签发记录 ID")
    policy_id: int = Field(description="策略 ID")
    customer_id: int = Field(description="客户 ID")
    customer_code: str = Field(description="客户编码")
    key_pair_id: int = Field(description="密钥对 ID")
    key_name: str = Field(description="密钥名称")
    status: str = Field(description="状态")
    hardware_fingerprint: str | None = Field(default=None, description="硬件指纹")
    capability_scope: list[str] = Field(default_factory=list, description="能力范围")
    version_constraints: dict[str, Any] = Field(default_factory=dict, description="版本约束")
    license_path: str = Field(description="license 文件路径")
    public_key_export_path: str = Field(description="公钥文件路径")
    issued_at_cst: str = Field(description="签发时间")
    last_validation_at: str | None = Field(default=None, description="最近校验时间")
    last_validation_result: str | None = Field(default=None, description="最近校验结果")


class LicenseIssueDetailResponse(LicenseIssueItem):
    payload: dict[str, Any] = Field(default_factory=dict, description="签发载荷")


class LicenseIssueListResponse(BaseModel):
    items: list[LicenseIssueItem] = Field(default_factory=list)


class ValidateLicenseRequest(BaseModel):
    hardware_fingerprint: str | None = Field(default=None, max_length=128, description="待校验硬件指纹")
    capability_name: str | None = Field(default=None, max_length=128, description="待校验能力")
    product_version: str | None = Field(default=None, max_length=128, description="待校验产品版本")


class ValidateLicenseResponse(BaseModel):
    valid: bool = Field(description="校验结果")
    reason: str = Field(description="校验说明")
    issue_record_id: int = Field(description="签发记录 ID")
    checked_at_cst: str = Field(description="校验时间")


class ExportLicenseResponse(BaseModel):
    exported_path: str = Field(description="导出文件路径")
    export_format: str = Field(description="导出格式")


class GenerateFingerprintRequest(BaseModel):
    features: dict[str, str] = Field(default_factory=dict, description="硬件特征键值对")


class GenerateFingerprintResponse(BaseModel):
    hardware_fingerprint: str = Field(description="硬件指纹")


class AuditLogItem(BaseModel):
    happened_at_cst: str = Field(description="发生时间")
    action: str = Field(description="操作类型")
    entity_type: str = Field(description="实体类型")
    entity_id: str = Field(description="实体 ID")
    detail: dict[str, Any] = Field(default_factory=dict, description="详情")


class AuditLogListResponse(BaseModel):
    items: list[AuditLogItem] = Field(default_factory=list)
