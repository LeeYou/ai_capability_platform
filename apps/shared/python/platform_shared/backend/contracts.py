from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any


ALLOWED_EXECUTION_MODES = {"real", "simulated"}
ALLOWED_REPORT_TEMPLATE_TYPES = {"research", "delivery"}


def _require_non_empty_string(payload: Mapping[str, Any], field_name: str) -> str:
    value = payload.get(field_name)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} 必须为非空字符串。")
    return value.strip()


def _require_existing_path(payload: Mapping[str, Any], field_name: str) -> str:
    path_text = _require_non_empty_string(payload, field_name)
    path = Path(path_text)
    if not path.exists():
        raise ValueError(f"{field_name} 指向的路径不存在。")
    return str(path.resolve())


def _normalize_exported_files(payload: Mapping[str, Any]) -> list[str]:
    exported_files = payload.get("exported_files")
    if not isinstance(exported_files, list) or not exported_files:
        raise ValueError("exported_files 必须为非空数组。")
    normalized: list[str] = []
    for index, item in enumerate(exported_files):
        if not isinstance(item, str) or not item.strip():
            raise ValueError(f"exported_files[{index}] 必须为非空字符串。")
        normalized.append(item.strip())
    return normalized


def validate_test_report_summary(
    payload: Mapping[str, Any],
    *,
    expected_task_id: int,
    expected_capability_name: str,
    expected_model_version: str,
) -> dict[str, object]:
    task_id = payload.get("task_id", expected_task_id)
    if task_id != expected_task_id:
        raise ValueError("task_id 与当前测试任务不匹配。")

    capability_name = _require_non_empty_string(payload, "capability_name")
    if capability_name != expected_capability_name:
        raise ValueError("capability_name 与当前测试任务不匹配。")

    model_version = _require_non_empty_string(payload, "model_version")
    if model_version != expected_model_version:
        raise ValueError("model_version 与当前测试任务不匹配。")

    task_type = _require_non_empty_string(payload, "task_type")
    execution_backend = _require_non_empty_string(payload, "execution_backend")

    execution_mode = payload.get("execution_mode")
    if not isinstance(execution_mode, str) or execution_mode not in ALLOWED_EXECUTION_MODES:
        raise ValueError("execution_mode 非法。")

    total_cases = _require_non_negative_int(payload, "total_cases")
    passed_cases = _require_non_negative_int(payload, "passed_cases")
    failed_cases = _require_non_negative_int(payload, "failed_cases")
    if passed_cases + failed_cases > total_cases:
        raise ValueError("passed_cases 与 failed_cases 超出 total_cases。")

    available_template_types = payload.get("available_template_types")
    if not isinstance(available_template_types, list) or not available_template_types:
        raise ValueError("available_template_types 必须为非空数组。")
    normalized_template_types: list[str] = []
    for index, item in enumerate(available_template_types):
        if not isinstance(item, str) or item not in ALLOWED_REPORT_TEMPLATE_TYPES:
            raise ValueError(f"available_template_types[{index}] 非法。")
        normalized_template_types.append(item)

    results = payload.get("results")
    if not isinstance(results, list):
        raise ValueError("results 必须为数组。")

    evidence_chain = payload.get("evidence_chain")
    if evidence_chain is not None and not isinstance(evidence_chain, Mapping):
        raise ValueError("evidence_chain 必须为对象。")

    normalized: dict[str, object] = {
        "task_id": expected_task_id,
        "task_type": task_type,
        "capability_name": capability_name,
        "model_version": model_version,
        "execution_backend": execution_backend,
        "execution_mode": execution_mode,
        "total_cases": total_cases,
        "passed_cases": passed_cases,
        "failed_cases": failed_cases,
        "available_template_types": normalized_template_types,
        "results": results,
    }

    execution_risk = payload.get("execution_risk")
    if execution_risk is not None:
        if not isinstance(execution_risk, str) or not execution_risk.strip():
            raise ValueError("execution_risk 必须为非空字符串。")
        normalized["execution_risk"] = execution_risk.strip()

    if evidence_chain is not None:
        normalized["evidence_chain"] = dict(evidence_chain)

    report_templates = payload.get("report_templates")
    if report_templates is not None:
        if not isinstance(report_templates, Mapping):
            raise ValueError("report_templates 必须为对象。")
        normalized["report_templates"] = dict(report_templates)

    return normalized


def _validate_exported_files_exist(export_dir: Path, exported_files: list[str]) -> None:
    for file_name in exported_files:
        candidate = (export_dir / file_name).resolve()
        if not (candidate == export_dir or export_dir in candidate.parents):
            raise ValueError("exported_files 包含非法路径。")
        if not candidate.exists() or not candidate.is_file():
            raise ValueError(f"exported_files 中声明的文件不存在：{file_name}")


def _require_non_negative_int(payload: Mapping[str, Any], field_name: str) -> int:
    value = payload.get(field_name)
    if not isinstance(value, int) or value < 0:
        raise ValueError(f"{field_name} 必须为非负整数。")
    return value


def validate_training_result_summary(
    payload: Mapping[str, Any],
    *,
    expected_task_id: int,
    expected_capability_name: str,
    expected_task_type: str,
    expected_execution_mode: str,
) -> dict[str, object]:
    if expected_execution_mode not in ALLOWED_EXECUTION_MODES:
        raise ValueError("expected_execution_mode 非法。")

    task_id = payload.get("task_id", expected_task_id)
    if task_id != expected_task_id:
        raise ValueError("task_id 与当前训练任务不匹配。")

    capability_name = _require_non_empty_string(payload, "capability_name")
    if capability_name != expected_capability_name:
        raise ValueError("capability_name 与当前训练任务不匹配。")

    task_type = _require_non_empty_string(payload, "task_type")
    if task_type != expected_task_type:
        raise ValueError("task_type 与当前训练任务不匹配。")

    execution_mode = payload.get("execution_mode", expected_execution_mode)
    if not isinstance(execution_mode, str) or execution_mode not in ALLOWED_EXECUTION_MODES:
        raise ValueError("execution_mode 非法。")
    if execution_mode != expected_execution_mode:
        raise ValueError("execution_mode 与当前执行路径不匹配。")

    export_dir_path = Path(_require_existing_path(payload, "export_dir"))
    exported_files = _normalize_exported_files(payload)
    _validate_exported_files_exist(export_dir_path, exported_files)

    normalized: dict[str, object] = {
        "task_id": expected_task_id,
        "capability_name": capability_name,
        "task_type": task_type,
        "execution_mode": execution_mode,
        "training_input_path": _require_existing_path(payload, "training_input_path"),
        "template_bundle_path": _require_existing_path(payload, "template_bundle_path"),
        "export_dir": str(export_dir_path),
        "exported_files": exported_files,
    }

    status = payload.get("status")
    if status is not None:
        if not isinstance(status, str) or not status.strip():
            raise ValueError("status 必须为非空字符串。")
        normalized["status"] = status.strip()

    for field_name in ("framework", "model_type", "task_name", "backend_type", "recorded_at"):
        field_value = payload.get(field_name)
        if field_value is not None:
            if not isinstance(field_value, str) or not field_value.strip():
                raise ValueError(f"{field_name} 必须为非空字符串。")
            normalized[field_name] = field_value.strip()

    for numeric_field in ("best_metric", "epochs", "sample_count", "train_duration_seconds"):
        numeric_value = payload.get(numeric_field)
        if numeric_value is not None:
            if not isinstance(numeric_value, (int, float)):
                raise ValueError(f"{numeric_field} 必须为数字。")
            normalized[numeric_field] = numeric_value

    metrics = payload.get("metrics")
    if metrics is not None:
        if not isinstance(metrics, Mapping):
            raise ValueError("metrics 必须为对象。")
        normalized["metrics"] = dict(metrics)

    for object_field in ("history",):
        object_value = payload.get(object_field)
        if object_value is not None:
            normalized[object_field] = object_value

    return normalized
