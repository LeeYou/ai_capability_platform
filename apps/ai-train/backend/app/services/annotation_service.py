from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import AnnotationTaskModel, CapabilityRegistryModel
from app.services.registry_service import normalize_capability_name

MAX_ANNOTATION_RESULT_BYTES = 1_048_576


class AnnotationTaskNotFoundError(ValueError):
    """标注任务不存在。"""


@dataclass(frozen=True)
class AnnotationTaskSummary:
    task_id: int
    capability_name: str
    task_name: str
    dataset_path: str
    status: str
    sample_total: int
    labeled_count: int
    result_path: str | None


def _annotation_result_path(annotation_tasks_root: Path, task_id: int) -> Path:
    annotation_tasks_root.mkdir(parents=True, exist_ok=True)
    return annotation_tasks_root / f"annotation_task_{task_id}.json"


def _validate_annotations_payload(
    task: AnnotationTaskModel,
    annotations: list[dict[str, object]],
) -> int:
    for index, item in enumerate(annotations):
        if not isinstance(item, dict) or not item:
            raise ValueError(f"annotations[{index}] 必须为非空对象。")
        if any(not isinstance(key, str) or not key.strip() for key in item):
            raise ValueError(f"annotations[{index}] 包含非法字段名。")

    labeled_count = len(annotations)
    if labeled_count > task.sample_total:
        raise ValueError("标注结果数量不能超过样本总数。")

    payload_size = len(json.dumps(annotations, ensure_ascii=False).encode("utf-8"))
    if payload_size > MAX_ANNOTATION_RESULT_BYTES:
        raise ValueError("标注结果内容过大，超过单任务存储限制。")

    return labeled_count


def _to_summary(task: AnnotationTaskModel) -> AnnotationTaskSummary:
    return AnnotationTaskSummary(
        task_id=task.id,
        capability_name=task.capability.capability_name,
        task_name=task.task_name,
        dataset_path=task.dataset_binding.dataset_path,
        status=task.status,
        sample_total=task.sample_total,
        labeled_count=task.labeled_count,
        result_path=task.result_path,
    )


def create_annotation_task(
    session: Session,
    capability_name: str,
    task_name: str,
    sample_total: int,
) -> AnnotationTaskSummary:
    normalized_name = normalize_capability_name(capability_name)
    normalized_task_name = task_name.strip()
    if not normalized_task_name:
        raise ValueError("task_name 不能为空。")
    if sample_total <= 0:
        raise ValueError("sample_total 必须大于 0。")

    capability = session.scalar(
        select(CapabilityRegistryModel).where(CapabilityRegistryModel.capability_name == normalized_name)
    )
    if capability is None:
        raise ValueError("能力尚未注册，无法创建标注任务。")
    if capability.dataset_binding is None:
        raise ValueError("能力尚未绑定数据集，无法创建标注任务。")

    task = AnnotationTaskModel(
        capability_id=capability.id,
        dataset_binding_id=capability.dataset_binding.id,
        task_name=normalized_task_name,
        status="pending",
        sample_total=sample_total,
        labeled_count=0,
    )
    session.add(task)
    session.commit()
    session.refresh(task)
    return _to_summary(task)


def list_annotation_tasks(session: Session) -> list[AnnotationTaskSummary]:
    tasks = session.scalars(select(AnnotationTaskModel).order_by(AnnotationTaskModel.id.asc())).all()
    return [_to_summary(task) for task in tasks]


def get_annotation_task(session: Session, task_id: int) -> AnnotationTaskSummary:
    task = session.get(AnnotationTaskModel, task_id)
    if task is None:
        raise AnnotationTaskNotFoundError("标注任务不存在。")
    return _to_summary(task)


def submit_annotation_task_result(
    session: Session,
    annotation_tasks_root: Path,
    task_id: int,
    annotations: list[dict[str, object]],
) -> AnnotationTaskSummary:
    task = session.get(AnnotationTaskModel, task_id)
    if task is None:
        raise AnnotationTaskNotFoundError("标注任务不存在。")
    labeled_count = _validate_annotations_payload(task, annotations)

    result_path = _annotation_result_path(annotation_tasks_root, task.id)
    payload = {
        "task_id": task.id,
        "capability_name": task.capability.capability_name,
        "task_name": task.task_name,
        "dataset_path": task.dataset_binding.dataset_path,
        "sample_total": task.sample_total,
        "labeled_count": labeled_count,
        "annotations": annotations,
    }
    result_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    task.result_path = str(result_path.resolve())
    task.labeled_count = labeled_count
    task.status = "completed" if labeled_count >= task.sample_total else "annotating"
    session.commit()
    session.refresh(task)
    return _to_summary(task)
