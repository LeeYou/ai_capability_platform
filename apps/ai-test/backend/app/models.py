from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str = Field(description="服务状态")
    service: str = Field(description="服务名称")
    company_name: str = Field(description="公司名称")
    company_domain: str = Field(description="公司域名")
    models_root: str = Field(description="模型根目录")


class RemoteCapabilityItem(BaseModel):
    capability_name: str = Field(description="能力标识")
    display_name: str = Field(description="能力名称")
    dataset_path: str = Field(description="数据集路径")
    dataset_status: str = Field(description="数据集状态")
    source: str = Field(description="来源")


class RemoteCapabilityListResponse(BaseModel):
    items: list[RemoteCapabilityItem] = Field(default_factory=list)
    synced_at: str | None = Field(default=None, description="最近同步时间")


class RemoteModelItem(BaseModel):
    capability_name: str = Field(description="能力标识")
    model_version: str = Field(description="模型版本")
    source_training_task_id: int = Field(description="来源训练任务 ID")
    artifact_path: str = Field(description="模型目录")
    manifest_path: str = Field(description="manifest 路径")
    backend_type: str = Field(description="执行后端")
    checksum: str = Field(description="校验值")
    status: str = Field(description="状态")


class RemoteModelListResponse(BaseModel):
    items: list[RemoteModelItem] = Field(default_factory=list)
    synced_at: str | None = Field(default=None, description="最近同步时间")


class SyncCatalogResponse(BaseModel):
    models: list[RemoteModelItem] = Field(default_factory=list)
    capabilities: list[RemoteCapabilityItem] = Field(default_factory=list)
    synced_at: str = Field(description="同步时间")


class TestCaseInput(BaseModel):
    case_name: str = Field(min_length=1, max_length=255, description="测试用例名称")
    input_path: str = Field(min_length=1, description="测试输入路径")
    expected_output: str | None = Field(default=None, max_length=2048, description="期望输出")


class CreateSingleTestRequest(BaseModel):
    capability_name: str = Field(min_length=1, max_length=128, description="能力标识")
    model_version: str = Field(min_length=1, max_length=128, description="模型版本")
    requested_backend: Literal["auto", "gpu", "cpu"] = Field(default="auto", description="期望执行后端")
    timeout_seconds: int = Field(default=30, ge=1, le=300, description="超时时间")
    case: TestCaseInput = Field(description="单接口测试用例")


class CreateBatchTestRequest(BaseModel):
    capability_name: str = Field(min_length=1, max_length=128, description="能力标识")
    model_version: str = Field(min_length=1, max_length=128, description="模型版本")
    requested_backend: Literal["auto", "gpu", "cpu"] = Field(default="auto", description="期望执行后端")
    timeout_seconds: int = Field(default=30, ge=1, le=300, description="超时时间")
    cases: list[TestCaseInput] = Field(min_length=1, description="批量测试用例")


class TestCaseResultItem(BaseModel):
    case_id: int = Field(description="测试用例 ID")
    case_name: str = Field(description="测试用例名称")
    input_path: str = Field(description="输入路径")
    input_type: str = Field(description="输入类型")
    status: str = Field(description="执行状态")
    expected_output: str | None = Field(default=None, description="期望输出")
    actual_output: str | None = Field(default=None, description="实际输出")
    duration_ms: int = Field(description="执行时长")
    score: float = Field(description="得分")
    provider: str | None = Field(default=None, description="推理 provider")


class TestTaskItem(BaseModel):
    task_id: int = Field(description="测试任务 ID")
    task_type: str = Field(description="任务类型")
    capability_name: str = Field(description="能力标识")
    model_version: str = Field(description="模型版本")
    requested_backend: str = Field(description="期望后端")
    execution_backend: str | None = Field(default=None, description="实际后端")
    timeout_seconds: int = Field(description="超时时间")
    status: str = Field(description="任务状态")
    total_cases: int = Field(description="总用例数")
    passed_cases: int = Field(description="通过用例数")
    failed_cases: int = Field(description="失败用例数")
    error_message: str | None = Field(default=None, description="错误信息")
    report_id: int | None = Field(default=None, description="测试报告 ID")
    started_at: str | None = Field(default=None, description="开始时间")
    completed_at: str | None = Field(default=None, description="完成时间")


class TestTaskDetailResponse(TestTaskItem):
    cases: list[TestCaseResultItem] = Field(default_factory=list)


class TestTaskListResponse(BaseModel):
    items: list[TestTaskItem] = Field(default_factory=list)


class TestReportItem(BaseModel):
    report_id: int = Field(description="测试报告 ID")
    task_id: int = Field(description="测试任务 ID")
    capability_name: str = Field(description="能力标识")
    model_version: str = Field(description="模型版本")
    status: str = Field(description="报告状态")
    passed_cases: int = Field(description="通过用例数")
    failed_cases: int = Field(description="失败用例数")
    json_report_path: str = Field(description="JSON 报告路径")
    html_report_path: str = Field(description="HTML 报告路径")
    pdf_report_path: str = Field(description="PDF 报告路径")
    exported_at: str | None = Field(default=None, description="导出时间")


class TestReportDetailResponse(TestReportItem):
    summary: dict[str, Any] = Field(default_factory=dict)


class TestReportListResponse(BaseModel):
    items: list[TestReportItem] = Field(default_factory=list)
