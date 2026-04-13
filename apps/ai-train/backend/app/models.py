from __future__ import annotations

from datetime import datetime
from typing import Any

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
    task_type: str = Field(description="任务类型")
    dataset_path: str = Field(description="数据集路径")
    dataset_status: str = Field(description="数据集状态")
    source: str = Field(description="能力来源")
    created_at: datetime | None = Field(default=None, description="创建时间")
    updated_at: datetime | None = Field(default=None, description="最近更新时间")
    annotation_schema: dict[str, Any] = Field(default_factory=dict, description="标注 schema")
    template_bundle: dict[str, Any] = Field(default_factory=dict, description="训练/测试/推理/构建模板")


class DatasetItem(BaseModel):
    capability_name: str = Field(description="能力标识")
    dataset_path: str = Field(description="数据集路径")
    dataset_status: str = Field(description="数据集状态")
    source: str = Field(description="绑定来源")
    file_count: int = Field(default=0, description="文件数量")
    total_size_bytes: int = Field(default=0, description="总大小（字节）")
    last_modified: str | None = Field(default=None, description="最后更新时间")
    created_at: datetime | None = Field(default=None, description="创建时间")
    updated_at: datetime | None = Field(default=None, description="最近更新时间")


class CapabilityListResponse(BaseModel):
    items: list[CapabilityItem] = Field(default_factory=list)


class DatasetListResponse(BaseModel):
    items: list[DatasetItem] = Field(default_factory=list)


class RegisterCapabilityRequest(BaseModel):
    capability_name: str = Field(min_length=1, max_length=128, description="能力标识")
    display_name: str | None = Field(default=None, min_length=1, max_length=255, description="能力显示名称")
    task_type: str | None = Field(default=None, min_length=1, max_length=64, description="任务类型")


class BindDatasetRequest(BaseModel):
    capability_name: str = Field(min_length=1, max_length=128, description="能力标识")
    dataset_path: str = Field(min_length=1, description="数据集路径，支持相对 datasets 根目录的路径")
    dataset_status: str = Field(default="ready", min_length=1, max_length=64, description="数据集状态")


class AnnotationTaskItem(BaseModel):
    task_id: int = Field(description="标注任务 ID")
    capability_name: str = Field(description="能力标识")
    task_type: str = Field(description="任务类型")
    task_name: str = Field(description="任务名称")
    dataset_path: str = Field(description="数据集路径")
    status: str = Field(description="任务状态")
    sample_total: int = Field(description="样本总数")
    labeled_count: int = Field(description="已标注数量")
    result_path: str | None = Field(default=None, description="结果文件路径")
    completion_ratio: float = Field(default=0.0, description="标注完成比例")
    sample_items: list["AnnotationSampleItem"] = Field(default_factory=list, description="样本级标注详情")
    annotation_schema: dict[str, Any] = Field(default_factory=dict, description="当前任务标注 schema")
    created_at: datetime | None = Field(default=None, description="创建时间")
    updated_at: datetime | None = Field(default=None, description="最近更新时间")


class AnnotationTaskListResponse(BaseModel):
    items: list[AnnotationTaskItem] = Field(default_factory=list)


class CreateAnnotationTaskRequest(BaseModel):
    capability_name: str = Field(min_length=1, max_length=128, description="能力标识")
    task_name: str = Field(min_length=1, max_length=255, description="任务名称")
    sample_total: int = Field(ge=1, description="待标注样本总数")


class AnnotationSampleItem(BaseModel):
    sample_id: str = Field(min_length=1, description="样本标识")
    status: str = Field(description="样本状态")
    annotation: dict[str, Any] | None = Field(default=None, description="样本标注结果")
    updated_at: str | None = Field(default=None, description="最近更新时间")


class SubmitAnnotationTaskRequest(BaseModel):
    annotations: list[dict[str, Any]] = Field(default_factory=list, description="标注结果列表")


class UpdateAnnotationSamplesRequest(BaseModel):
    annotations: list[dict[str, Any]] = Field(default_factory=list, description="待保存的样本标注列表")
    mark_submitted: bool = Field(default=False, description="是否将本次批量更新视为提交动作")


class TrainingTaskItem(BaseModel):
    task_id: int = Field(description="训练任务 ID")
    capability_name: str = Field(description="能力标识")
    task_type: str = Field(description="任务类型")
    task_name: str = Field(description="任务名称")
    dataset_path: str = Field(description="数据集路径")
    status: str = Field(description="任务状态")
    framework: str = Field(description="训练框架")
    backend_type: str = Field(description="执行后端")
    annotation_task_id: int | None = Field(default=None, description="来源标注任务 ID")
    retry_count: int = Field(description="重试次数")
    log_path: str | None = Field(default=None, description="日志文件路径")
    workspace_path: str | None = Field(default=None, description="训练工作区路径")
    started_at: str | None = Field(default=None, description="开始时间")
    completed_at: str | None = Field(default=None, description="完成时间")
    latest_logs: list[str] = Field(default_factory=list, description="最近日志片段")
    execution_plan: dict[str, Any] | None = Field(default=None, description="训练执行计划")
    result_summary: dict[str, Any] | None = Field(default=None, description="训练结果摘要")
    training_input_path: str | None = Field(default=None, description="训练输入适配文件路径")
    template_bundle_path: str | None = Field(default=None, description="模板脚手架路径")
    export_dir: str | None = Field(default=None, description="训练导出目录")
    created_at: datetime | None = Field(default=None, description="创建时间")
    updated_at: datetime | None = Field(default=None, description="最近更新时间")


class TrainingTaskListResponse(BaseModel):
    items: list[TrainingTaskItem] = Field(default_factory=list)


class CreateTrainingTaskRequest(BaseModel):
    capability_name: str = Field(min_length=1, max_length=128, description="能力标识")
    task_name: str = Field(min_length=1, max_length=255, description="任务名称")
    framework: str = Field(default="pytorch", min_length=1, max_length=64, description="训练框架")
    backend_type: str = Field(default="cpu", min_length=1, max_length=64, description="执行后端")
    annotation_task_id: int | None = Field(default=None, description="来源标注任务 ID")
    train_params: dict[str, Any] = Field(default_factory=dict, description="训练参数")


class UpdateTrainingTaskStatusRequest(BaseModel):
    status: str = Field(min_length=1, max_length=64, description="目标状态")


class AppendTrainingTaskLogRequest(BaseModel):
    message: str = Field(min_length=1, max_length=10000, description="日志内容")


class RecordTrainingTaskResultRequest(BaseModel):
    result_summary: dict[str, Any] = Field(default_factory=dict, description="训练结果摘要")


class TrainingTaskLogSnapshot(BaseModel):
    task_id: int = Field(description="训练任务 ID")
    status: str = Field(description="训练任务状态")
    log_path: str | None = Field(default=None, description="日志文件路径")
    latest_logs: list[str] = Field(default_factory=list, description="最近日志片段")
    execution_plan: dict[str, Any] | None = Field(default=None, description="训练执行计划")
    result_summary: dict[str, Any] | None = Field(default=None, description="训练结果摘要")


class ModelArtifactItem(BaseModel):
    artifact_id: int = Field(description="模型产物 ID")
    capability_name: str = Field(description="能力标识")
    task_type: str = Field(description="任务类型")
    model_version: str = Field(description="模型版本")
    source_training_task_id: int = Field(description="来源训练任务 ID")
    artifact_path: str = Field(description="模型目录")
    manifest_path: str = Field(description="manifest 路径")
    backend_type: str = Field(description="执行后端")
    checksum: str = Field(description="校验值")
    status: str = Field(description="产物状态")
    manifest_preview: dict[str, Any] | None = Field(default=None, description="manifest 预览")
    delivery_metadata: dict[str, Any] | None = Field(default=None, description="面向 ai-test / ai-builder 的交付元数据")
    runtime_contract: dict[str, Any] | None = Field(default=None, description="运行时消费契约")
    created_at: datetime | None = Field(default=None, description="创建时间")
    updated_at: datetime | None = Field(default=None, description="最近更新时间")


class ModelArtifactListResponse(BaseModel):
    items: list[ModelArtifactItem] = Field(default_factory=list)


class RegisterModelArtifactRequest(BaseModel):
    capability_name: str = Field(min_length=1, max_length=128, description="能力标识")
    model_version: str = Field(min_length=1, max_length=128, description="模型版本")
    source_training_task_id: int = Field(description="来源训练任务 ID")
    backend_type: str | None = Field(default=None, min_length=1, max_length=64, description="执行后端")
