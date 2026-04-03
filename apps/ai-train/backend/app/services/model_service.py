from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import CapabilityRegistryModel, ModelArtifactModel, TrainingTaskModel
from app.services.registry_service import normalize_capability_name

_MODEL_VERSION_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")


class ModelArtifactNotFoundError(ValueError):
    """模型产物不存在。"""


@dataclass(frozen=True)
class ModelArtifactSummary:
    artifact_id: int
    capability_name: str
    model_version: str
    source_training_task_id: int
    artifact_path: str
    manifest_path: str
    backend_type: str
    checksum: str
    status: str


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
    return ModelArtifactSummary(
        artifact_id=item.id,
        capability_name=item.capability.capability_name,
        model_version=item.model_version,
        source_training_task_id=item.source_training_task_id,
        artifact_path=item.artifact_path,
        manifest_path=item.manifest_path,
        backend_type=item.backend_type,
        checksum=item.checksum,
        status=item.status,
    )


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
    manifest_path = artifact_dir / "manifest.json"
    manifest = {
        "capability_name": normalized_name,
        "model_version": normalized_version,
        "source_train_task_id": training_task.id,
        "task_name": training_task.task_name,
        "backend_type": normalized_backend_type,
        "artifact_path": str(artifact_dir.resolve()),
        "status": "ready",
    }
    manifest_text = json.dumps(manifest, ensure_ascii=False, indent=2)
    checksum = hashlib.sha256(manifest_text.encode("utf-8")).hexdigest()
    manifest["checksum"] = checksum
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
