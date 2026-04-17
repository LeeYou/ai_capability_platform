from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


ReportTemplateType = Literal["research", "delivery"]


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


class CreateAcceptanceTaskRequest(BaseModel):
    image_uri: str = Field(min_length=1, description="待验收的生产镜像标识")
    target_base_url: str = Field(min_length=1, description="待验收运行实例的公开 API 地址")
    capability_name: str | None = Field(default=None, max_length=128, description="默认验收能力标识")
    input_type: Literal["json", "image", "video", "pdf"] = Field(default="json", description="推理输入类型")
    infer_payload: str = Field(default='{"image":"demo"}', description="推理载荷")
    prefer_device: Literal["auto", "gpu", "cpu"] = Field(default="auto", description="设备偏好")
    acceptance_timeout_seconds: int = Field(default=10, ge=1, le=300, description="验收脚本超时时间")
    run_admin_checks: bool = Field(default=False, description="是否执行 license_reload 等管理接口校验")
    pressure_requests: int = Field(default=32, ge=1, le=2000, description="压测请求数")
    pressure_concurrency: int = Field(default=8, ge=1, le=256, description="压测并发数")
    pressure_timeout_seconds: int = Field(default=10, ge=1, le=300, description="压测超时时间")
    pressure_min_success_rate: float = Field(default=1.0, ge=0.0, le=1.0, description="压测最小成功率")
    pressure_max_p95_ms: int = Field(default=5000, ge=1, le=60000, description="压测 P95 延迟阈值")


class UpsertPerformanceBaselineRequest(BaseModel):
    capability_name: str = Field(min_length=1, max_length=128, description="能力标识，all 表示平台级默认阈值")
    scenario_name: str = Field(min_length=1, max_length=64, description="场景标识")
    latency_max_ms: int | None = Field(default=None, ge=1, le=60000, description="单请求最大时延阈值")
    throughput_min_rps: float | None = Field(default=None, ge=0.0, description="最小吞吐阈值")
    p95_max_ms: int | None = Field(default=None, ge=1, le=60000, description="P95 最大时延阈值")
    p99_max_ms: int | None = Field(default=None, ge=1, le=60000, description="P99 最大时延阈值")
    success_rate_min: float = Field(default=1.0, ge=0.0, le=1.0, description="最小成功率阈值")
    description: str | None = Field(default=None, max_length=2048, description="阈值说明")


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
    execution_mode: str = Field(description="执行模式")
    execution_risk: str | None = Field(default=None, description="执行风险提示")
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
    evidence_chain: dict[str, Any] | None = Field(default=None, description="执行证据链")


class TestTaskListResponse(BaseModel):
    items: list[TestTaskItem] = Field(default_factory=list)


class AcceptanceScriptResultItem(BaseModel):
    case_name: str = Field(description="脚本名称")
    status: str = Field(description="执行状态")
    duration_ms: int = Field(description="执行耗时")
    passed: bool = Field(description="是否通过")
    detail: dict[str, Any] = Field(default_factory=dict, description="脚本原始结果")
    baseline_comparison: dict[str, Any] | None = Field(default=None, description="性能/稳定性基线对比结果")
    passed_baseline: bool | None = Field(default=None, description="是否满足基线")


class AcceptanceTaskItem(BaseModel):
    acceptance_task_id: int = Field(description="验收任务 ID")
    task_id: int = Field(description="关联测试任务 ID")
    image_uri: str = Field(description="生产镜像标识")
    target_base_url: str = Field(description="目标运行地址")
    capability_name: str | None = Field(default=None, description="默认验收能力")
    input_type: str = Field(description="推理输入类型")
    prefer_device: str = Field(description="设备偏好")
    status: str = Field(description="任务状态")
    total_cases: int = Field(description="总脚本数")
    passed_cases: int = Field(description="通过脚本数")
    failed_cases: int = Field(description="失败脚本数")
    report_id: int | None = Field(default=None, description="报告 ID")
    created_at: str | None = Field(default=None, description="创建时间")
    started_at: str | None = Field(default=None, description="开始时间")
    completed_at: str | None = Field(default=None, description="完成时间")


class AcceptanceTaskDetailResponse(AcceptanceTaskItem):
    script_results: list[AcceptanceScriptResultItem] = Field(default_factory=list)


class AcceptanceTaskListResponse(BaseModel):
    items: list[AcceptanceTaskItem] = Field(default_factory=list)


class PerformanceBaselineItem(BaseModel):
    baseline_id: int = Field(description="基线 ID")
    capability_name: str = Field(description="能力标识")
    scenario_name: str = Field(description="场景标识")
    latency_max_ms: int | None = Field(default=None, description="单请求最大时延阈值")
    throughput_min_rps: float | None = Field(default=None, description="最小吞吐阈值")
    p95_max_ms: int | None = Field(default=None, description="P95 最大时延阈值")
    p99_max_ms: int | None = Field(default=None, description="P99 最大时延阈值")
    success_rate_min: float = Field(description="最小成功率阈值")
    description: str | None = Field(default=None, description="基线说明")
    created_at: str | None = Field(default=None, description="创建时间")
    updated_at: str | None = Field(default=None, description="更新时间")


class PerformanceBaselineListResponse(BaseModel):
    items: list[PerformanceBaselineItem] = Field(default_factory=list)


class TestReportItem(BaseModel):
    report_id: int = Field(description="测试报告 ID")
    task_id: int = Field(description="测试任务 ID")
    capability_name: str = Field(description="能力标识")
    model_version: str = Field(description="模型版本")
    status: str = Field(description="报告状态")
    execution_mode: str = Field(description="执行模式")
    execution_risk: str | None = Field(default=None, description="执行风险提示")
    passed_cases: int = Field(description="通过用例数")
    failed_cases: int = Field(description="失败用例数")
    json_report_path: str = Field(description="JSON 报告路径")
    html_report_path: str = Field(description="HTML 报告路径")
    pdf_report_path: str = Field(description="PDF 报告路径")
    available_template_types: list[ReportTemplateType] = Field(default_factory=lambda: ["research", "delivery"], description="可用报告模板")
    active_template_type: ReportTemplateType = Field(default="research", description="当前报告视角")
    exported_at: str | None = Field(default=None, description="导出时间")


class TestReportDetailResponse(TestReportItem):
    summary: dict[str, Any] = Field(default_factory=dict)


class TestReportListResponse(BaseModel):
    items: list[TestReportItem] = Field(default_factory=list)
