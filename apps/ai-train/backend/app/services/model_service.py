from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import CapabilityRegistryModel, ModelArtifactModel, TrainingTaskModel
from app.services.task_contracts import normalize_task_type
from app.services.template_service import build_annotation_schema, build_template_bundle

from platform_shared.backend import validate_manifest_model

_MODEL_VERSION_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")


class ModelArtifactNotFoundError(ValueError):
    """模型产物不存在。"""


@dataclass(frozen=True)
class ModelArtifactSummary:
    artifact_id: int
    capability_name: str
    task_type: str
    model_version: str
    source_training_task_id: int
    artifact_path: str
    manifest_path: str
    backend_type: str
    checksum: str
    status: str
    manifest_preview: dict[str, object] | None
    delivery_metadata: dict[str, object] | None
    runtime_contract: dict[str, object] | None


def _validate_model_version(model_version: str) -> str:
    normalized_version = model_version.strip()
    if not normalized_version:
        raise ValueError("model_version 不能为空。")
    if not _MODEL_VERSION_PATTERN.match(normalized_version):
        raise ValueError("model_version 格式非法。")
    return normalized_version


def _artifact_dir(models_root: Path, capability_name: str, model_version: str) -> Path:
    path = (models_root / capability_name / model_version).resolve()
    if not (path == models_root or models_root in path.parents):
        raise ValueError("模型产物目录非法。")
    path.mkdir(parents=True, exist_ok=True)
    return path


def _to_summary(item: ModelArtifactModel) -> ModelArtifactSummary:
    manifest_preview = None
    delivery_metadata = None
    runtime_contract = None
    manifest_path = Path(item.manifest_path)
    if manifest_path.exists():
        loaded_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if isinstance(loaded_manifest, dict):
            manifest_preview = loaded_manifest
            raw_delivery_metadata = loaded_manifest.get("delivery_metadata")
            if isinstance(raw_delivery_metadata, dict):
                delivery_metadata = raw_delivery_metadata
            raw_runtime_contract = loaded_manifest.get("runtime_contract")
            if isinstance(raw_runtime_contract, dict):
                runtime_contract = raw_runtime_contract
    task_type = normalize_task_type(item.capability.task_type)
    return ModelArtifactSummary(
        artifact_id=item.id,
        capability_name=item.capability.capability_name,
        task_type=task_type,
        model_version=item.model_version,
        source_training_task_id=item.source_training_task_id,
        artifact_path=item.artifact_path,
        manifest_path=item.manifest_path,
        backend_type=item.backend_type,
        checksum=item.checksum,
        status=item.status,
        manifest_preview=manifest_preview,
        delivery_metadata=delivery_metadata,
        runtime_contract=runtime_contract,
    )


def _extract_labels(training_task: TrainingTaskModel) -> list[str]:
    annotation_task = training_task.annotation_task
    task_type = normalize_task_type(training_task.capability.task_type)
    if annotation_task is None or not annotation_task.result_path:
        return ["ok", "ng"]
    result_path = Path(annotation_task.result_path)
    if not result_path.exists():
        return ["ok", "ng"]
    payload = json.loads(result_path.read_text(encoding="utf-8"))
    annotations = payload.get("annotations", [])
    if not isinstance(annotations, list):
        return ["ok", "ng"]
    labels = []
    for item in annotations:
        if not isinstance(item, dict):
            continue
        if task_type == "classification":
            if isinstance(item.get("label"), str) and item["label"].strip():
                labels.append(item["label"].strip())
        elif task_type == "detection":
            objects = item.get("objects")
            if isinstance(objects, list):
                for current in objects:
                    if isinstance(current, dict) and isinstance(current.get("label"), str) and current["label"].strip():
                        labels.append(current["label"].strip())
        elif task_type == "structured_extraction":
            fields = item.get("fields")
            if isinstance(fields, dict):
                labels.extend(str(key).strip() for key in fields if str(key).strip())
    unique_labels = sorted(set(labels))
    return unique_labels or ["ok", "ng"]


def create_model_artifact(
    session: Session,
    models_root: Path,
    capability_name: str,
    model_version: str,
    source_training_task_id: int,
    backend_type: str | None = None,
) -> ModelArtifactSummary:
    normalized_name = normalize_capability_name(capability_name)
    normalized_version = _validate_model_version(model_version)

    capability = session.scalar(
        select(CapabilityRegistryModel).where(CapabilityRegistryModel.capability_name == normalized_name)
    )
    if capability is None:
        raise ValueError("能力尚未注册，无法登记模型产物。")

    training_task = session.get(TrainingTaskModel, source_training_task_id)
    if training_task is None or training_task.capability_id != capability.id:
        raise ValueError("来源训练任务不存在或不属于当前能力。")
    if training_task.status != "completed":
        raise ValueError("仅支持从已完成的训练任务登记模型产物。")

    existing = session.scalar(
        select(ModelArtifactModel).where(
            ModelArtifactModel.capability_id == capability.id,
            ModelArtifactModel.model_version == normalized_version,
        )
    )
    if existing is not None:
        raise ValueError("当前能力下该模型版本已存在。")

    artifact_dir = _artifact_dir(models_root.resolve(), normalized_name, normalized_version)
    normalized_backend_type = backend_type.strip() if backend_type else training_task.backend_type
    task_type = normalize_task_type(capability.task_type)
    manifest_path = artifact_dir / "manifest.json"
    preprocessing_path = artifact_dir / "preprocess.json"
    labels_path = artifact_dir / "labels.json"
    validation_dir = artifact_dir / "validation"
    validation_dir.mkdir(parents=True, exist_ok=True)
    validation_checklist_path = validation_dir / "acceptance_checklist.json"
    delivery_metadata_path = artifact_dir / "delivery_metadata.json"
    runtime_contract_path = artifact_dir / "runtime_contract.json"
    export_dir = Path(training_task.workspace_path) / "exported_model" if training_task.workspace_path else None
    exported_files = sorted([path.name for path in export_dir.iterdir() if path.is_file()]) if export_dir and export_dir.exists() else []
    labels = _extract_labels(training_task)
    preprocessing = {
        "input_type": capability.input_type or "image",
        "resize": {"width": 640, "height": 640},
        "normalize": {
            "mean": [0.485, 0.456, 0.406],
            "std": [0.229, 0.224, 0.225],
        },
    }
    thresholds = {
        "score_threshold": 0.5,
        "nms_threshold": 0.45,
    }
    train_params = json.loads(training_task.train_params_json) if training_task.train_params_json else {}
    validation_checklist = {
        "capability_name": normalized_name,
        "model_version": normalized_version,
        "required_cases": ["acceptance_check", "pressure_smoke"],
        "report_templates": ["research", "delivery"],
    }
    delivery_metadata = {
        "ai_test": {
            "recommended_task_type": "acceptance",
            "report_templates": ["research", "delivery"],
            "acceptance_checklist_path": str(validation_checklist_path.resolve()),
            "task_type": task_type,
        },
        "ai_builder": {
            "delivery_package_section": "models",
            "manifest_schema_path": "apps/shared/schemas/manifest_model.json",
            "mount_template_required": True,
            "template_bundle": build_template_bundle(normalized_name, task_type),
        },
        "training_summary": {
            "framework": training_task.framework,
            "backend_type": normalized_backend_type,
            "train_params": train_params,
        },
    }
    runtime_contract = {
        "schema_version": "1.0",
        "task_type": task_type,
        "annotation_schema": build_annotation_schema(task_type),
        "template_bundle": build_template_bundle(normalized_name, task_type),
        "model_files": exported_files or ["weights.bin"],
        "runtime_inputs": {
            "input_type": capability.input_type or "image",
            "preprocess_path": str(preprocessing_path.resolve()),
            "labels_path": str(labels_path.resolve()),
        },
    }
    preprocessing_path.write_text(json.dumps(preprocessing, ensure_ascii=False, indent=2), encoding="utf-8")
    labels_path.write_text(json.dumps({"labels": labels}, ensure_ascii=False, indent=2), encoding="utf-8")
    validation_checklist_path.write_text(
        json.dumps(validation_checklist, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    delivery_metadata_path.write_text(json.dumps(delivery_metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    runtime_contract_path.write_text(json.dumps(runtime_contract, ensure_ascii=False, indent=2), encoding="utf-8")
    manifest = {
        "capability_name": normalized_name,
        "task_type": task_type,
        "model_version": normalized_version,
        "source_train_task_id": training_task.id,
        "task_name": training_task.task_name,
        "backend_type": normalized_backend_type,
        "artifact_path": str(artifact_dir.resolve()),
        "status": "ready",
        "preprocessing": preprocessing,
        "thresholds": thresholds,
        "labels": labels,
        "validation": {
            "artifacts": [
                str(preprocessing_path.relative_to(artifact_dir)),
                str(labels_path.relative_to(artifact_dir)),
                str(validation_checklist_path.relative_to(artifact_dir)),
                str(delivery_metadata_path.relative_to(artifact_dir)),
                str(runtime_contract_path.relative_to(artifact_dir)),
            ]
        },
        "runtime_contract": runtime_contract,
        "delivery_metadata": delivery_metadata,
    }
    manifest_text = json.dumps(manifest, ensure_ascii=False, indent=2)
    checksum = hashlib.sha256(manifest_text.encode("utf-8")).hexdigest()
    manifest["checksum"] = checksum
    validate_manifest_model(manifest)
    manifest_text = json.dumps(manifest, ensure_ascii=False, indent=2)
    manifest_path.write_text(manifest_text, encoding="utf-8")

    model_artifact = ModelArtifactModel(
        capability_id=capability.id,
        source_training_task_id=training_task.id,
        model_version=normalized_version,
        artifact_path=str(artifact_dir.resolve()),
        manifest_path=str(manifest_path.resolve()),
        backend_type=normalized_backend_type,
        checksum=checksum,
        status="ready",
    )
    session.add(model_artifact)
    session.commit()
    session.refresh(model_artifact)
    return _to_summary(model_artifact)


def list_model_artifacts(session: Session) -> list[ModelArtifactSummary]:
    items = session.scalars(select(ModelArtifactModel).order_by(ModelArtifactModel.id.asc())).all()
    return [_to_summary(item) for item in items]


def get_model_artifact(session: Session, artifact_id: int) -> ModelArtifactSummary:
    item = session.get(ModelArtifactModel, artifact_id)
    if item is None:
        raise ModelArtifactNotFoundError("模型产物不存在。")
    return _to_summary(item)
