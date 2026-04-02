from __future__ import annotations

from collections import deque
from collections.abc import Iterable
from datetime import UTC, datetime
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


def _scan_models(root: Path) -> dict[str, dict[str, Any]]:
    capability_map: dict[str, dict[str, Any]] = {}
    for capability_dir in _sorted_dirs(root):
        versions = _sorted_dirs(capability_dir)
        if not versions:
            continue
        selected_version_dir = versions[-1]
        manifest_path = selected_version_dir / "manifest.json"
        if manifest_path.exists():
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        else:
            manifest = {
                "capability_name": capability_dir.name,
                "model_version": selected_version_dir.name,
                "backend_type": "onnxruntime",
            }
        capability_map[capability_dir.name] = {
            "model_root": str(selected_version_dir.resolve()),
            "model_version": str(manifest.get("model_version", selected_version_dir.name)),
            "backend_type": str(manifest.get("backend_type", "onnxruntime")),
            "manifest": manifest,
        }
    return capability_map


def _scan_plugins(root: Path, target_name: str) -> dict[str, dict[str, Any]]:
    capability_map: dict[str, dict[str, Any]] = {}
    target_root = root / target_name
    for capability_dir in _sorted_dirs(target_root):
        manifest_path = capability_dir / "manifest" / "manifest.json"
        if manifest_path.exists():
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        else:
            manifest = {
                "capability_name": capability_dir.name,
                "target_name": target_name,
                "build_mode": "template",
                "dependency_summary": {},
            }
        lib_dir = capability_dir / "lib"
        binary_candidates = sorted([item for item in lib_dir.iterdir() if item.is_file()], key=lambda item: item.name) if lib_dir.exists() else []
        capability_map[capability_dir.name] = {
            "plugin_root": str(capability_dir.resolve()),
            "plugin_target": target_name,
            "build_mode": str(manifest.get("build_mode", "template")),
            "binary_path": str(binary_candidates[0].resolve()) if binary_candidates else "",
            "manifest": manifest,
        }
    return capability_map


def _resolve_sources(host_root: Path, image_root: Path, target_name: str) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    host_models = _scan_models(host_root / "models")
    image_models = _scan_models(image_root / "models")
    host_plugins = _scan_plugins(host_root / "libs", target_name)
    image_plugins = _scan_plugins(image_root / "libs", target_name)

    merged: dict[str, dict[str, Any]] = {}
    for capability_name in sorted(set(host_models) | set(image_models) | set(host_plugins) | set(image_plugins)):
        model_entry = host_models.get(capability_name) or image_models.get(capability_name)
        plugin_entry = host_plugins.get(capability_name) or image_plugins.get(capability_name)
        if model_entry is None or plugin_entry is None:
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
            "model_manifest": model_entry["manifest"],
            "plugin_manifest": plugin_entry["manifest"],
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
    }


def _ensure_instance_pool(capabilities: dict[str, dict[str, Any]], *, pool_size: int, gpu_available: bool) -> None:
    _INSTANCE_POOLS.clear()
    for capability_name in capabilities:
        pool = deque()
        for index in range(pool_size):
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
        "device_mode": "gpu/cpu" if payload.get("gpu_available", False) else "cpu",
        "pool_size": len(_INSTANCE_POOLS.get(capability_name, [])),
        "revision_id": _ACTIVE_REVISION_ID,
    }


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
) -> dict[str, Any]:
    with _RUNTIME_LOCK:
        target_name = _platform_target_name()
        capabilities, source_summary = _resolve_sources(host_root, image_resource_root, target_name)
        license_status = validate_license_bundle(license_root, hardware_features=hardware_features)
        revision = RuntimeRevisionModel(
            revision_token=str(uuid4()),
            action="bootstrap",
            status="active",
            source_summary_json=json.dumps(source_summary, ensure_ascii=False, sort_keys=True),
            capabilities_json=json.dumps(sorted(capabilities), ensure_ascii=False, sort_keys=True),
            license_valid=bool(license_status["valid"]),
            detail_json=json.dumps({"license_status": license_status}, ensure_ascii=False, sort_keys=True),
            rollback_of_revision_id=None,
        )
        session.add(revision)
        session.commit()
        session.refresh(revision)
        _apply_revision(capabilities, revision.id, pool_size=pool_size, gpu_available=gpu_available)
        snapshot_payload = {
            "snapshot_version": 1,
            "updated_at_utc": datetime.now(UTC).isoformat(),
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
) -> dict[str, Any]:
    status = validate_license_bundle(license_root, hardware_features=hardware_features)
    status["runtime_revision_id"] = _ACTIVE_REVISION_ID
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
        )
        if not license_status["valid"]:
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
) -> dict[str, Any]:
    with _RUNTIME_LOCK:
        if action == "reload":
            target_name = _platform_target_name()
            capabilities, source_summary = _resolve_sources(host_root, image_resource_root, target_name)
            license_status = validate_license_bundle(license_root, hardware_features=hardware_features)
            revision = RuntimeRevisionModel(
                revision_token=str(uuid4()),
                action="reload",
                status="active",
                source_summary_json=json.dumps(source_summary, ensure_ascii=False, sort_keys=True),
                capabilities_json=json.dumps(sorted(capabilities), ensure_ascii=False, sort_keys=True),
                license_valid=bool(license_status["valid"]),
                detail_json=json.dumps({"license_status": license_status}, ensure_ascii=False, sort_keys=True),
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
            target_name = _platform_target_name()
            capabilities, source_summary = _resolve_sources(host_root, image_resource_root, target_name)
            selected = {name: capabilities[name] for name in capability_names if name in capabilities}
            license_status = validate_license_bundle(license_root, hardware_features=hardware_features)
            revision = RuntimeRevisionModel(
                revision_token=str(uuid4()),
                action="rollback",
                status="active",
                source_summary_json=json.dumps(source_summary, ensure_ascii=False, sort_keys=True),
                capabilities_json=json.dumps(sorted(selected), ensure_ascii=False, sort_keys=True),
                license_valid=bool(license_status["valid"]),
                detail_json=json.dumps(
                    {"license_status": license_status, "rollback_to": target_revision_id},
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
            "updated_at_utc": datetime.now(UTC).isoformat(),
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
