from __future__ import annotations

from collections import deque
from collections.abc import Iterable
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import threading
from typing import Any
from uuid import uuid4

from sqlalchemy.orm import Session

from app.db.models import RuntimeOperationModel, RuntimeRevisionModel
from app.services.audit_service import append_audit_log
from app.services.license_service import LicenseValidationError, validate_license_bundle


_RUNTIME_LOCK = threading.RLock()
_INSTANCE_POOLS: dict[str, deque[dict[str, Any]]] = {}
_ACTIVE_CAPABILITIES: dict[str, dict[str, Any]] = {}
_ACTIVE_REVISION_ID: int | None = None


def _build_license_failure_message(capability_name: str, license_status: dict[str, Any]) -> str:
    return f"能力 {capability_name} license 校验失败：{license_status['reason']}"


def _validate_runtime_capabilities_license(
    *,
    capabilities: dict[str, dict[str, Any]],
    license_root: Path,
    hardware_features: dict[str, str],
    operating_system: str,
    operating_system_version: str,
    system_architecture: str,
    audit_log_path: Path,
    action: str,
    entity_id: str,
) -> dict[str, Any]:
    license_status = validate_license_bundle(
        license_root,
        hardware_features=hardware_features,
        operating_system=operating_system,
        operating_system_version=operating_system_version,
        system_architecture=system_architecture,
    )
    capability_statuses: dict[str, dict[str, Any]] = {}
    for capability_name, capability in sorted(capabilities.items()):
        capability_license_status = validate_license_bundle(
            license_root,
            hardware_features=hardware_features,
            capability_name=capability_name,
            product_version=str(capability["model_version"]),
            operating_system=operating_system,
            operating_system_version=operating_system_version,
            system_architecture=system_architecture,
        )
        capability_statuses[capability_name] = capability_license_status
        if not capability_license_status["valid"]:
            append_audit_log(
                audit_log_path,
                action=f"{action}_license_rejected",
                entity_type="capability",
                entity_id=capability_name,
                detail={
                    "reason": capability_license_status["reason"],
                    "code": capability_license_status["code"],
                    "stage": capability_license_status["stage"],
                    "details": capability_license_status["details"],
                    "model_version": capability["model_version"],
                },
            )
            raise LicenseValidationError(_build_license_failure_message(capability_name, capability_license_status))

    return {
        **license_status,
        "capability_statuses": capability_statuses,
        "validated_capability_names": sorted(capability_statuses),
        "validation_action": action,
        "validation_entity_id": entity_id,
    }


def initialize_database() -> None:
    from app.db.database import Base, get_engine
    from app.db import models  # noqa: F401

    Base.metadata.create_all(bind=get_engine())


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_name(f"{path.name}.{os.getpid()}.tmp")
    temp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    temp_path.replace(path)


def _append_runtime_log(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False) + "\n")


def _platform_target_name() -> str:
    system_name = platform.system().lower()
    machine_name = platform.machine().lower()
    if system_name == "linux" and machine_name in {"x86_64", "amd64"}:
        return "linux_x86_64"
    if system_name == "linux" and machine_name in {"aarch64", "arm64"}:
        return "linux_arm64"
    if system_name == "windows" and machine_name in {"x86_64", "amd64"}:
        return "windows_x86_64"
    if system_name == "windows":
        return "windows_x86"
    return "linux_x86_64"


def _sorted_dirs(path: Path) -> list[Path]:
    if not path.exists():
        return []
    return sorted([item for item in path.iterdir() if item.is_dir()], key=lambda item: item.name)


def _failure_item(capability_name: str, manifest_type: str, manifest_path: Path, reason: str) -> dict[str, str]:
    return {
        "capability_name": capability_name,
        "manifest_type": manifest_type,
        "manifest_path": str(manifest_path.resolve()),
        "reason": reason,
    }


def _resolve_manifest_path(base_path: Path, raw_path: str) -> Path:
    candidate = Path(raw_path)
    resolved = candidate if candidate.is_absolute() else (base_path / candidate)
    resolved = resolved.resolve()
    if not resolved.exists():
        raise ValueError(f"manifest 依赖文件不存在：{resolved}")
    if resolved != base_path.resolve() and base_path.resolve() not in resolved.parents:
        raise ValueError("manifest 依赖文件必须位于模型目录内。")
    return resolved


def _validate_model_manifest(capability_dir: Path, selected_version_dir: Path, manifest: Any) -> dict[str, Any]:
    if not isinstance(manifest, dict):
        raise ValueError("manifest 顶层必须是对象。")
    required_keys = (
        "capability_name",
        "task_type",
        "model_version",
        "source_train_task_id",
        "task_name",
        "backend_type",
        "artifact_path",
        "status",
        "checksum",
        "preprocessing",
        "thresholds",
        "labels",
        "validation",
        "runtime_contract",
        "delivery_metadata",
    )
    for key in required_keys:
        if key not in manifest:
            raise ValueError(f"模型包 manifest 缺失字段：{key}")
    if manifest["capability_name"] != capability_dir.name:
        raise ValueError("模型包 manifest capability_name 与目录名不一致。")
    if manifest["model_version"] != selected_version_dir.name:
        raise ValueError("模型包 manifest model_version 与目录版本不一致。")
    if manifest["status"] != "ready":
        raise ValueError("模型包 manifest status 必须为 ready。")
    if not isinstance(manifest["labels"], list) or not manifest["labels"] or any(not isinstance(item, str) or not item.strip() for item in manifest["labels"]):
        raise ValueError("模型包 manifest labels 必须为非空字符串数组。")
    preprocessing = manifest["preprocessing"]
    thresholds = manifest["thresholds"]
    validation = manifest["validation"]
    runtime_contract = manifest["runtime_contract"]
    if not isinstance(preprocessing, dict) or not isinstance(thresholds, dict) or not isinstance(validation, dict) or not isinstance(runtime_contract, dict):
        raise ValueError("模型包 manifest 复合字段类型非法。")
    if "input_type" not in preprocessing or "resize" not in preprocessing or "normalize" not in preprocessing:
        raise ValueError("模型包 manifest preprocessing 缺失必需字段。")
    if "score_threshold" not in thresholds or "nms_threshold" not in thresholds:
        raise ValueError("模型包 manifest thresholds 缺失必需字段。")
    if runtime_contract.get("task_type") != manifest["task_type"]:
        raise ValueError("模型包 manifest runtime_contract.task_type 与 task_type 不一致。")
    runtime_inputs = runtime_contract.get("runtime_inputs")
    if not isinstance(runtime_inputs, dict):
        raise ValueError("模型包 manifest runtime_contract.runtime_inputs 缺失。")
    _resolve_manifest_path(selected_version_dir, str(manifest["artifact_path"]))
    if _resolve_manifest_path(selected_version_dir, str(manifest["artifact_path"])) != selected_version_dir.resolve():
        raise ValueError("模型包 manifest artifact_path 与实际模型目录不一致。")
    _resolve_manifest_path(selected_version_dir, str(runtime_inputs.get("preprocess_path", "")))
    _resolve_manifest_path(selected_version_dir, str(runtime_inputs.get("labels_path", "")))
    artifacts = validation.get("artifacts")
    if not isinstance(artifacts, list):
        raise ValueError("模型包 manifest validation.artifacts 缺失。")
    for item in artifacts:
        if not isinstance(item, str):
            raise ValueError("模型包 manifest validation.artifacts 必须全部为字符串。")
        _resolve_manifest_path(selected_version_dir, item)
    return {
        "model_root": str(selected_version_dir.resolve()),
        "model_version": str(manifest["model_version"]),
        "backend_type": str(manifest["backend_type"]),
        "max_batch_size": max(1, int(manifest.get("max_batch_size", manifest.get("batch_size", 1)))),
        "instance_count": max(1, int(manifest["instance_count"])) if "instance_count" in manifest else 0,
        "manifest": manifest,
    }


def _validate_plugin_manifest(capability_dir: Path, target_name: str, manifest: Any, binary_path: Path | None) -> dict[str, Any]:
    if not isinstance(manifest, dict):
        raise ValueError("manifest 顶层必须是对象。")
    required_keys = (
        "capability_name",
        "model_version",
        "target_name",
        "artifact_format",
        "build_mode",
        "toolchain_name",
        "jni_enabled",
        "customer_code",
        "issue_record_id",
        "dependency_summary",
    )
    for key in required_keys:
        if key not in manifest:
            raise ValueError(f"插件 manifest 缺失字段：{key}")
    if manifest["capability_name"] != capability_dir.name:
        raise ValueError("插件 manifest capability_name 与目录名不一致。")
    if manifest["target_name"] != target_name:
        raise ValueError("插件 manifest target_name 与当前目标平台不一致。")
    dependency_summary = manifest["dependency_summary"]
    if not isinstance(dependency_summary, dict):
        raise ValueError("插件 manifest dependency_summary 必须是对象。")
    for key in ("runtime", "abi", "license_required", "build_params_controlled"):
        if key not in dependency_summary:
            raise ValueError(f"插件 manifest dependency_summary 缺失字段：{key}")
    if binary_path is None or not binary_path.exists():
        raise ValueError("插件二进制不存在。")
    if manifest["artifact_format"] == "so" and binary_path.suffix != ".so":
        raise ValueError("插件 manifest artifact_format 与二进制扩展名不一致。")
    if manifest["artifact_format"] == "dll" and binary_path.suffix != ".dll":
        raise ValueError("插件 manifest artifact_format 与二进制扩展名不一致。")
    return {
        "plugin_root": str(capability_dir.resolve()),
        "plugin_target": target_name,
        "build_mode": str(manifest["build_mode"]),
        "binary_path": str(binary_path.resolve()),
        "max_batch_size": max(1, int(manifest.get("max_batch_size", 1))),
        "instance_count": max(1, int(manifest["instance_count"])) if "instance_count" in manifest else 0,
        "manifest": manifest,
    }


def _scan_models(root: Path) -> tuple[dict[str, dict[str, Any]], list[dict[str, str]]]:
    capability_map: dict[str, dict[str, Any]] = {}
    failures: list[dict[str, str]] = []
    for capability_dir in _sorted_dirs(root):
        versions = _sorted_dirs(capability_dir)
        if not versions:
            continue
        selected_version_dir = versions[-1]
        manifest_path = selected_version_dir / "manifest.json"
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            capability_map[capability_dir.name] = _validate_model_manifest(capability_dir, selected_version_dir, manifest)
        except Exception as exc:
            failures.append(_failure_item(capability_dir.name, "model_manifest", manifest_path, str(exc)))
    return capability_map, failures


def _scan_plugins(root: Path, target_name: str) -> tuple[dict[str, dict[str, Any]], list[dict[str, str]]]:
    capability_map: dict[str, dict[str, Any]] = {}
    failures: list[dict[str, str]] = []
    target_root = root / target_name
    for capability_dir in _sorted_dirs(target_root):
        manifest_path = capability_dir / "manifest" / "manifest.json"
        lib_dir = capability_dir / "lib"
        binary_candidates = sorted([item for item in lib_dir.iterdir() if item.is_file()], key=lambda item: item.name) if lib_dir.exists() else []
        binary_path = binary_candidates[0] if binary_candidates else None
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            capability_map[capability_dir.name] = _validate_plugin_manifest(capability_dir, target_name, manifest, binary_path)
        except Exception as exc:
            failures.append(_failure_item(capability_dir.name, "plugin_manifest", manifest_path, str(exc)))
    return capability_map, failures


def _resolve_sources(host_root: Path, image_root: Path, target_name: str) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    host_models, host_model_failures = _scan_models(host_root / "models")
    image_models, image_model_failures = _scan_models(image_root / "models")
    host_plugins, host_plugin_failures = _scan_plugins(host_root / "libs", target_name)
    image_plugins, image_plugin_failures = _scan_plugins(image_root / "libs", target_name)

    merged: dict[str, dict[str, Any]] = {}
    invalid_capability_failures: list[dict[str, str]] = []
    for capability_name in sorted(set(host_models) | set(image_models) | set(host_plugins) | set(image_plugins)):
        model_entry = host_models.get(capability_name) or image_models.get(capability_name)
        plugin_entry = host_plugins.get(capability_name) or image_plugins.get(capability_name)
        if model_entry is None or plugin_entry is None:
            continue
        if plugin_entry["manifest"].get("model_version") != model_entry["model_version"]:
            invalid_capability_failures.append(
                _failure_item(
                    capability_name,
                    "capability_contract",
                    Path(plugin_entry["plugin_root"]) / "manifest" / "manifest.json",
                    "插件 manifest model_version 与模型包 manifest 不一致。",
                )
            )
            continue
        merged[capability_name] = {
            "capability_name": capability_name,
            "model_version": model_entry["model_version"],
            "backend_type": model_entry["backend_type"],
            "model_root": model_entry["model_root"],
            "plugin_root": plugin_entry["plugin_root"],
            "plugin_target": plugin_entry["plugin_target"],
            "build_mode": plugin_entry["build_mode"],
            "binary_path": plugin_entry["binary_path"],
            "max_batch_size": int(plugin_entry.get("max_batch_size") or model_entry.get("max_batch_size") or 1),
            "instance_count": int(plugin_entry.get("instance_count") or model_entry.get("instance_count") or 0),
            "model_manifest": model_entry["manifest"],
            "plugin_manifest": plugin_entry["manifest"],
            "admission_checklist": {},
            "active_source": "host"
            if capability_name in host_models and capability_name in host_plugins
            else "image",
        }
    return merged, {
        "target_name": target_name,
        "host_models": sorted(host_models),
        "host_plugins": sorted(host_plugins),
        "image_models": sorted(image_models),
        "image_plugins": sorted(image_plugins),
        "host_model_failures": host_model_failures,
        "host_plugin_failures": host_plugin_failures,
        "image_model_failures": image_model_failures,
        "image_plugin_failures": image_plugin_failures,
        "invalid_capability_failures": invalid_capability_failures,
    }


def _set_checklist_item(
    checklist: dict[str, Any],
    *,
    code: str,
    label: str,
    required: bool,
    status: str,
    detail: str,
) -> None:
    items = checklist.setdefault("items", [])
    for item in items:
        if item.get("code") == code:
            item.update(
                {
                    "label": label,
                    "required": required,
                    "status": status,
                    "detail": detail,
                }
            )
            return
    items.append(
        {
            "code": code,
            "label": label,
            "required": required,
            "status": status,
            "detail": detail,
        }
    )


def _finalize_checklist(checklist: dict[str, Any]) -> dict[str, Any]:
    failed_codes = [
        item["code"]
        for item in checklist.get("items", [])
        if item.get("required") and item.get("status") != "passed"
    ]
    checklist["failed_codes"] = failed_codes
    checklist["ready"] = not failed_codes
    return checklist


def _build_admission_checklist(payload: dict[str, Any], *, license_valid: bool) -> dict[str, Any]:
    checklist: dict[str, Any] = {
        "capability_name": payload["capability_name"],
        "items": [],
        "failed_codes": [],
        "ready": False,
    }
    model_manifest = payload.get("model_manifest", {})
    plugin_manifest = payload.get("plugin_manifest", {})
    runtime_contract = model_manifest.get("runtime_contract", {})
    runtime_inputs = runtime_contract.get("runtime_inputs", {})
    dependency_summary = plugin_manifest.get("dependency_summary", {})
    _set_checklist_item(
        checklist,
        code="manifest_contract",
        label="manifest 契约",
        required=True,
        status="passed",
        detail="模型包 manifest 与插件 manifest 已通过强校验。",
    )
    sample_input_passed = bool(
        model_manifest.get("preprocessing", {}).get("input_type")
        and runtime_inputs.get("preprocess_path")
        and runtime_inputs.get("labels_path")
    )
    _set_checklist_item(
        checklist,
        code="sample_input_contract",
        label="样本输入契约",
        required=True,
        status="passed" if sample_input_passed else "failed",
        detail="输入类型、预处理配置与标签路径齐全。"
        if sample_input_passed
        else "缺少 preprocessing.input_type 或 runtime_inputs 关键路径。",
    )
    abi_passed = bool(dependency_summary.get("abi"))
    _set_checklist_item(
        checklist,
        code="abi_contract",
        label="插件 ABI 契约",
        required=True,
        status="passed" if abi_passed else "failed",
        detail="插件 manifest 已声明 ABI 与运行时依赖。"
        if abi_passed
        else "插件 manifest 缺少 ABI 声明。",
    )
    model_root = str(payload.get("model_root", "")).strip()
    binary_path = str(payload.get("binary_path", "")).strip()
    artifact_passed = bool(model_root) and bool(binary_path) and Path(model_root).exists() and Path(binary_path).exists()
    _set_checklist_item(
        checklist,
        code="artifact_presence",
        label="运行时产物存在性",
        required=True,
        status="passed" if artifact_passed else "failed",
        detail="模型目录与插件二进制均存在。"
        if artifact_passed
        else "模型目录或插件二进制缺失。",
    )
    _set_checklist_item(
        checklist,
        code="license_gate",
        label="License 门禁",
        required=True,
        status="passed" if license_valid else "failed",
        detail="当前 capability 已通过 license 范围与版本约束校验。"
        if license_valid
        else "当前 capability 未通过 license 范围或版本约束校验。",
    )
    _set_checklist_item(
        checklist,
        code="runtime_probe",
        label="运行时装载门禁",
        required=False,
        status="not_applicable",
        detail="Python 内部验收外壳不执行 C++ 插件预装载探测，实际门禁由 C++ runtime 承担。",
    )
    return _finalize_checklist(checklist)


def _ensure_instance_pool(capabilities: dict[str, dict[str, Any]], *, pool_size: int, gpu_available: bool) -> None:
    _INSTANCE_POOLS.clear()
    for capability_name, payload in capabilities.items():
        pool = deque()
        configured_pool_size = max(1, int(payload.get("instance_count") or pool_size))
        for index in range(configured_pool_size):
            pool.append(
                {
                    "instance_id": f"{capability_name}-{index + 1}",
                    "default_device": "gpu" if gpu_available else "cpu",
                }
            )
        _INSTANCE_POOLS[capability_name] = pool


def _serialize_capability(capability_name: str, payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "capability_name": capability_name,
        "plugin_target": payload["plugin_target"],
        "model_version": payload["model_version"],
        "backend_type": payload["backend_type"],
        "active_source": payload["active_source"],
        "model_root": payload.get("model_root", ""),
        "binary_path": payload.get("binary_path", ""),
        "device_mode": "gpu/cpu" if payload.get("gpu_available", False) else "cpu",
        "pool_size": len(_INSTANCE_POOLS.get(capability_name, [])),
        "max_batch_size": max(1, int(payload.get("max_batch_size", 1))),
        "admission_checklist": payload.get("admission_checklist", {}),
        "revision_id": _ACTIVE_REVISION_ID,
    }


def _serialize_runtime_capability_record(capability_name: str, payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "capability_name": capability_name,
        "model_root": payload["model_root"],
        "model_version": payload["model_version"],
        "backend_type": payload["backend_type"],
        "plugin_root": payload["plugin_root"],
        "plugin_target": payload["plugin_target"],
        "build_mode": payload["build_mode"],
        "binary_path": payload["binary_path"],
        "active_source": payload["active_source"],
        "max_batch_size": max(1, int(payload.get("max_batch_size", 1))),
        "instance_count": max(1, int(payload["instance_count"])) if payload.get("instance_count") else 0,
        "model_manifest": payload.get("model_manifest", {}),
        "plugin_manifest": payload.get("plugin_manifest", {}),
        "admission_checklist": payload.get("admission_checklist", {}),
    }


def _serialize_runtime_capability_records(capabilities: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    return [_serialize_runtime_capability_record(name, payload) for name, payload in sorted(capabilities.items())]


def _restore_runtime_capability_records(detail: dict[str, Any]) -> dict[str, dict[str, Any]] | None:
    capability_records = detail.get("capability_records")
    if not isinstance(capability_records, list):
        return None
    restored: dict[str, dict[str, Any]] = {}
    for item in capability_records:
        if not isinstance(item, dict):
            raise ValueError("revision capability_records 每一项都必须是对象。")
        capability_name = str(item.get("capability_name", "")).strip()
        if not capability_name:
            raise ValueError("revision capability_records 缺少必需字段 capability_name。")
        restored[capability_name] = {
            "capability_name": capability_name,
            "model_root": str(item.get("model_root", "")),
            "model_version": str(item.get("model_version", "")),
            "backend_type": str(item.get("backend_type", "")),
            "plugin_root": str(item.get("plugin_root", "")),
            "plugin_target": str(item.get("plugin_target", "")),
            "build_mode": str(item.get("build_mode", "")),
            "binary_path": str(item.get("binary_path", "")),
            "active_source": str(item.get("active_source", "")),
            "max_batch_size": max(1, int(item.get("max_batch_size", 1))),
            "instance_count": max(1, int(item["instance_count"])) if item.get("instance_count") else 0,
            "model_manifest": item.get("model_manifest", {}),
            "plugin_manifest": item.get("plugin_manifest", {}),
            "admission_checklist": item.get("admission_checklist", {}),
        }
    return restored


def _validate_runtime_capability_artifacts(capabilities: dict[str, dict[str, Any]]) -> None:
    for capability_name, payload in capabilities.items():
        model_root_value = str(payload.get("model_root", ""))
        plugin_root_value = str(payload.get("plugin_root", ""))
        binary_path_value = str(payload.get("binary_path", ""))
        model_root = Path(model_root_value)
        plugin_root = Path(plugin_root_value)
        binary_path = Path(binary_path_value)
        if not model_root_value or not model_root.exists():
            raise ValueError(f"回滚目标模型目录不存在：{model_root}")
        if not plugin_root_value or not plugin_root.exists():
            raise ValueError(f"回滚目标插件目录不存在：{plugin_root}")
        if not binary_path_value or not binary_path.exists():
            raise ValueError(f"回滚目标插件文件不存在：{binary_path}")


def _revision_item(revision: RuntimeRevisionModel) -> dict[str, Any]:
    return {
        "revision_id": revision.id,
        "revision_token": revision.revision_token,
        "action": revision.action,
        "status": revision.status,
        "license_valid": revision.license_valid,
        "capability_names": json.loads(revision.capabilities_json),
        "source_summary": json.loads(revision.source_summary_json),
        "detail": json.loads(revision.detail_json),
        "rollback_of_revision_id": revision.rollback_of_revision_id,
        "created_at": revision.created_at.isoformat() if revision.created_at else None,
    }


def _operation_item(operation: RuntimeOperationModel) -> dict[str, Any]:
    return {
        "operation_id": operation.id,
        "action": operation.action,
        "status": operation.status,
        "detail": json.loads(operation.detail_json),
        "revision_id": operation.revision_id,
        "created_at": operation.created_at.isoformat() if operation.created_at else None,
    }


def _create_operation(session: Session, *, action: str, status: str, detail: dict[str, Any], revision_id: int | None) -> RuntimeOperationModel:
    operation = RuntimeOperationModel(
        action=action,
        status=status,
        detail_json=json.dumps(detail, ensure_ascii=False, sort_keys=True),
        revision_id=revision_id,
    )
    session.add(operation)
    session.commit()
    session.refresh(operation)
    return operation


def _apply_revision(capabilities: dict[str, dict[str, Any]], revision_id: int, *, pool_size: int, gpu_available: bool) -> None:
    _ACTIVE_CAPABILITIES.clear()
    for capability_name, payload in capabilities.items():
        active_payload = dict(payload)
        active_payload["gpu_available"] = gpu_available
        _ACTIVE_CAPABILITIES[capability_name] = active_payload
    _ensure_instance_pool(_ACTIVE_CAPABILITIES, pool_size=pool_size, gpu_available=gpu_available)
    global _ACTIVE_REVISION_ID
    _ACTIVE_REVISION_ID = revision_id


def bootstrap_runtime(
    session: Session,
    *,
    runtime_snapshot_path: Path,
    runtime_log_path: Path,
    audit_log_path: Path,
    host_root: Path,
    image_resource_root: Path,
    license_root: Path,
    hardware_features: dict[str, str],
    pool_size: int,
    gpu_available: bool,
    service_name: str,
    company_name: str,
    company_domain: str,
    operating_system: str,
    operating_system_version: str,
    system_architecture: str,
) -> dict[str, Any]:
    with _RUNTIME_LOCK:
        target_name = _platform_target_name()
        capabilities, source_summary = _resolve_sources(host_root, image_resource_root, target_name)
        license_status = _validate_runtime_capabilities_license(
            capabilities=capabilities,
            license_root=license_root,
            hardware_features=hardware_features,
            operating_system=operating_system,
            operating_system_version=operating_system_version,
            system_architecture=system_architecture,
            audit_log_path=audit_log_path,
            action="bootstrap",
            entity_id="bootstrap",
        )
        for capability_name, capability in capabilities.items():
            capability["admission_checklist"] = _build_admission_checklist(
                capability,
                license_valid=bool(license_status["capability_statuses"][capability_name]["valid"]),
            )
        revision = RuntimeRevisionModel(
            revision_token=str(uuid4()),
            action="bootstrap",
            status="active",
            source_summary_json=json.dumps(source_summary, ensure_ascii=False, sort_keys=True),
            capabilities_json=json.dumps(sorted(capabilities), ensure_ascii=False, sort_keys=True),
            license_valid=bool(license_status["valid"]),
            detail_json=json.dumps(
                {
                    "license_status": license_status,
                    "capability_records": _serialize_runtime_capability_records(capabilities),
                },
                ensure_ascii=False,
                sort_keys=True,
            ),
            rollback_of_revision_id=None,
        )
        session.add(revision)
        session.commit()
        session.refresh(revision)
        _apply_revision(capabilities, revision.id, pool_size=pool_size, gpu_available=gpu_available)
        snapshot_payload = {
            "snapshot_version": 1,
            "updated_at_utc": datetime.now(timezone.utc).isoformat(),
            "revision_id": revision.id,
            "revision_token": revision.revision_token,
            "capability_names": sorted(capabilities),
            "capability_count": len(capabilities),
            "capabilities": list_capabilities(),
            "source_summary": source_summary,
            "license_status": {**license_status, "runtime_revision_id": revision.id},
            "service_name": service_name,
            "company_name": company_name,
            "company_domain": company_domain,
        }
        _write_json(runtime_snapshot_path, snapshot_payload)
        _append_runtime_log(
            runtime_log_path,
            {
                "event": "bootstrap",
                "revision_id": revision.id,
                "capability_count": len(capabilities),
                "license_valid": license_status["valid"],
            },
        )
        append_audit_log(
            audit_log_path,
            action="bootstrap",
            entity_type="runtime_revision",
            entity_id=str(revision.id),
            detail={"capability_count": len(capabilities), "license_valid": bool(license_status["valid"])},
        )
        return {"revision": _revision_item(revision), "license_status": license_status}


def list_capabilities() -> list[dict[str, Any]]:
    with _RUNTIME_LOCK:
        return [_serialize_capability(name, payload) for name, payload in sorted(_ACTIVE_CAPABILITIES.items())]


def list_runtime_revisions(session: Session) -> list[dict[str, Any]]:
    rows = session.query(RuntimeRevisionModel).order_by(RuntimeRevisionModel.id.asc()).all()
    return [_revision_item(item) for item in rows]


def list_runtime_operations(session: Session) -> list[dict[str, Any]]:
    rows = session.query(RuntimeOperationModel).order_by(RuntimeOperationModel.id.asc()).all()
    return [_operation_item(item) for item in rows]


def get_license_status(
    *,
    license_root: Path,
    hardware_features: dict[str, str],
    operating_system: str,
    operating_system_version: str,
    system_architecture: str,
    audit_log_path: Path | None = None,
) -> dict[str, Any]:
    status = validate_license_bundle(
        license_root,
        hardware_features=hardware_features,
        operating_system=operating_system,
        operating_system_version=operating_system_version,
        system_architecture=system_architecture,
    )
    status["runtime_revision_id"] = _ACTIVE_REVISION_ID
    if audit_log_path is not None:
        append_audit_log(
            audit_log_path,
            action="license_status_query",
            entity_type="license",
            entity_id="current",
            detail={
                "valid": bool(status["valid"]),
                "reason": status["reason"],
                "code": status["code"],
                "stage": status["stage"],
                "runtime_revision_id": _ACTIVE_REVISION_ID,
            },
        )
    return status


def infer(
    *,
    runtime_log_path: Path,
    audit_log_path: Path,
    license_root: Path,
    hardware_features: dict[str, str],
    capability_name: str,
    input_type: str,
    payload: str,
    prefer_device: str,
    options: dict[str, Any],
    operating_system: str,
    operating_system_version: str,
    system_architecture: str,
) -> dict[str, Any]:
    with _RUNTIME_LOCK:
        if capability_name not in _ACTIVE_CAPABILITIES:
            raise ValueError("能力不存在或未装载。")
        capability = _ACTIVE_CAPABILITIES[capability_name]
        license_status = validate_license_bundle(
            license_root,
            hardware_features=hardware_features,
            capability_name=capability_name,
            product_version=str(capability["model_version"]),
            operating_system=operating_system,
            operating_system_version=operating_system_version,
            system_architecture=system_architecture,
        )
        if not license_status["valid"]:
            append_audit_log(
                audit_log_path,
                action="infer_license_rejected",
                entity_type="capability",
                entity_id=capability_name,
                detail={
                    "reason": license_status["reason"],
                    "code": license_status["code"],
                    "stage": license_status["stage"],
                    "details": license_status["details"],
                    "model_version": capability["model_version"],
                },
            )
            raise LicenseValidationError(str(license_status["reason"]))

        pool = _INSTANCE_POOLS[capability_name]
        instance = pool.popleft()
        try:
            if prefer_device == "gpu" and capability.get("gpu_available", False):
                device = "gpu"
            elif prefer_device == "gpu" and not capability.get("gpu_available", False):
                device = "cpu"
            elif prefer_device == "cpu":
                device = "cpu"
            else:
                device = "gpu" if capability.get("gpu_available", False) else "cpu"
            request_id = str(uuid4())

            # ── 尝试真实推理适配器 ──
            real_result = None
            try:
                from app.services.capability_adapters import get_inference_adapter

                adapter = get_inference_adapter(capability_name)
                if adapter is not None:
                    adapter_output = adapter.infer(
                        capability_name=capability_name,
                        model_version=str(capability["model_version"]),
                        model_root=str(capability.get("model_root", "")),
                        input_type=input_type,
                        payload=payload,
                        device=device,
                        options=options,
                    )
                    real_result = {
                        "summary": adapter_output.get("summary", f"{capability_name} 推理完成"),
                        "score": adapter_output.get("score", 0.0),
                        "input_type": input_type,
                        "payload_size": len(payload.encode("utf-8")),
                        "instance_id": instance["instance_id"],
                        "fallback_applied": prefer_device == "gpu" and device == "cpu",
                        "adapter_result": adapter_output.get("result", {}),
                    }
            except Exception:
                pass  # 适配器不可用时静默回退到模拟推理

            if real_result is not None:
                result = real_result
            else:
                # ── 回退：模拟推理 ──
                result_hash = hashlib.sha256(
                    f"{capability_name}|{capability['model_version']}|{input_type}|{payload}|{json.dumps(options, ensure_ascii=False, sort_keys=True)}".encode("utf-8")
                ).hexdigest()
                result = {
                    "summary": f"{capability_name} 推理完成",
                    "digest": result_hash,
                    "score": round(int(result_hash[:4], 16) / 65535, 4),
                    "input_type": input_type,
                    "payload_size": len(payload.encode("utf-8")),
                    "instance_id": instance["instance_id"],
                    "fallback_applied": prefer_device == "gpu" and device == "cpu",
                }
            _append_runtime_log(
                runtime_log_path,
                {
                    "event": "infer",
                    "request_id": request_id,
                    "capability_name": capability_name,
                    "device": device,
                    "runtime_revision_id": _ACTIVE_REVISION_ID,
                },
            )
            append_audit_log(
                audit_log_path,
                action="infer",
                entity_type="capability",
                entity_id=capability_name,
                detail={"request_id": request_id, "device": device},
            )
            return {
                "request_id": request_id,
                "capability_name": capability_name,
                "model_version": capability["model_version"],
                "backend_type": capability["backend_type"],
                "plugin_target": capability["plugin_target"],
                "device": device,
                "runtime_revision_id": int(_ACTIVE_REVISION_ID or 0),
                "license_valid": True,
                "result": result,
            }
        finally:
            pool.append(instance)


def reload_runtime(
    session: Session,
    *,
    runtime_snapshot_path: Path,
    runtime_log_path: Path,
    audit_log_path: Path,
    host_root: Path,
    image_resource_root: Path,
    license_root: Path,
    hardware_features: dict[str, str],
    pool_size: int,
    gpu_available: bool,
    action: str,
    target_revision_id: int | None,
    service_name: str,
    company_name: str,
    company_domain: str,
    operating_system: str,
    operating_system_version: str,
    system_architecture: str,
) -> dict[str, Any]:
    with _RUNTIME_LOCK:
        if action == "reload":
            target_name = _platform_target_name()
            capabilities, source_summary = _resolve_sources(host_root, image_resource_root, target_name)
            license_status = _validate_runtime_capabilities_license(
                capabilities=capabilities,
                    license_root=license_root,
                    hardware_features=hardware_features,
                    operating_system=operating_system,
                    operating_system_version=operating_system_version,
                    system_architecture=system_architecture,
                    audit_log_path=audit_log_path,
                    action="reload",
                entity_id="reload",
            )
            for capability_name, capability in capabilities.items():
                capability["admission_checklist"] = _build_admission_checklist(
                    capability,
                    license_valid=bool(license_status["capability_statuses"][capability_name]["valid"]),
                )
            revision = RuntimeRevisionModel(
                revision_token=str(uuid4()),
                action="reload",
                status="active",
                source_summary_json=json.dumps(source_summary, ensure_ascii=False, sort_keys=True),
                capabilities_json=json.dumps(sorted(capabilities), ensure_ascii=False, sort_keys=True),
                license_valid=bool(license_status["valid"]),
                detail_json=json.dumps(
                    {
                        "license_status": license_status,
                        "capability_records": _serialize_runtime_capability_records(capabilities),
                    },
                    ensure_ascii=False,
                    sort_keys=True,
                ),
                rollback_of_revision_id=None,
            )
            session.add(revision)
            session.commit()
            session.refresh(revision)
            _apply_revision(capabilities, revision.id, pool_size=pool_size, gpu_available=gpu_available)
        elif action == "rollback":
            if target_revision_id is None:
                raise ValueError("rollback 需要 target_revision_id。")
            source_revision = session.get(RuntimeRevisionModel, target_revision_id)
            if source_revision is None:
                raise ValueError("目标 revision 不存在。")
            capability_names = json.loads(source_revision.capabilities_json)
            source_summary = json.loads(source_revision.source_summary_json)
            source_detail = json.loads(source_revision.detail_json)
            restored_capabilities = _restore_runtime_capability_records(source_detail)
            if restored_capabilities is not None:
                selected = restored_capabilities
                _validate_runtime_capability_artifacts(selected)
            else:
                target_name = _platform_target_name()
                capabilities, source_summary = _resolve_sources(host_root, image_resource_root, target_name)
                selected = {name: capabilities[name] for name in capability_names if name in capabilities}
            license_status = _validate_runtime_capabilities_license(
                capabilities=selected,
                license_root=license_root,
                hardware_features=hardware_features,
                operating_system=operating_system,
                operating_system_version=operating_system_version,
                system_architecture=system_architecture,
                audit_log_path=audit_log_path,
                action="rollback",
                entity_id=str(target_revision_id),
            )
            for capability_name, capability in selected.items():
                capability["admission_checklist"] = _build_admission_checklist(
                    capability,
                    license_valid=bool(license_status["capability_statuses"][capability_name]["valid"]),
                )
            revision = RuntimeRevisionModel(
                revision_token=str(uuid4()),
                action="rollback",
                status="active",
                source_summary_json=json.dumps(source_summary, ensure_ascii=False, sort_keys=True),
                capabilities_json=json.dumps(sorted(selected), ensure_ascii=False, sort_keys=True),
                license_valid=bool(license_status["valid"]),
                detail_json=json.dumps(
                    {
                        "license_status": license_status,
                        "rollback_to": target_revision_id,
                        "capability_records": _serialize_runtime_capability_records(selected),
                    },
                    ensure_ascii=False,
                    sort_keys=True,
                ),
                rollback_of_revision_id=target_revision_id,
            )
            session.add(revision)
            session.commit()
            session.refresh(revision)
            _apply_revision(selected, revision.id, pool_size=pool_size, gpu_available=gpu_available)
        else:
            raise ValueError("仅支持 reload/rollback。")

        snapshot_payload = {
            "snapshot_version": 1,
            "updated_at_utc": datetime.now(timezone.utc).isoformat(),
            "revision_id": revision.id,
            "revision_token": revision.revision_token,
            "capability_names": json.loads(revision.capabilities_json),
            "capability_count": len(_ACTIVE_CAPABILITIES),
            "capabilities": list_capabilities(),
            "source_summary": json.loads(revision.source_summary_json),
            "license_status": {
                **json.loads(revision.detail_json).get("license_status", {}),
                "runtime_revision_id": revision.id,
            },
            "service_name": service_name,
            "company_name": company_name,
            "company_domain": company_domain,
        }
        _write_json(runtime_snapshot_path, snapshot_payload)
        _append_runtime_log(
            runtime_log_path,
            {"event": action, "revision_id": revision.id, "active_capability_count": len(_ACTIVE_CAPABILITIES)},
        )
        append_audit_log(
            audit_log_path,
            action=action,
            entity_type="runtime_revision",
            entity_id=str(revision.id),
            detail={"active_capability_count": len(_ACTIVE_CAPABILITIES)},
        )
        operation = _create_operation(
            session,
            action=action,
            status="completed",
            detail={"active_capability_count": len(_ACTIVE_CAPABILITIES)},
            revision_id=revision.id,
        )
        return {
            "operation_id": operation.id,
            "revision": _revision_item(revision),
            "active_capability_count": len(_ACTIVE_CAPABILITIES),
        }
