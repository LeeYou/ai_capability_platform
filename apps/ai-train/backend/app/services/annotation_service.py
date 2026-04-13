from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import AnnotationTaskModel, CapabilityRegistryModel
from app.services.registry_service import normalize_capability_name
from app.services.task_contracts import build_annotation_schema, normalize_task_type, validate_annotation_payload

MAX_ANNOTATION_RESULT_BYTES = 1_048_576


class AnnotationTaskNotFoundError(ValueError):
    """标注任务不存在。"""


@dataclass(frozen=True)
class AnnotationTaskSummary:
    task_id: int
    capability_name: str
    task_type: str
    task_name: str
    dataset_path: str
    status: str
    sample_total: int
    labeled_count: int
    result_path: str | None
    sample_items: list[dict[str, object]]
    annotation_schema: dict[str, object]
    created_at: str | None
    updated_at: str | None


def _default_sample_items(task: AnnotationTaskModel) -> list[dict[str, object]]:
    return [
        {
            "sample_id": f"sample_{index}",
            "status": "pending",
            "annotation": None,
            "updated_at": None,
        }
        for index in range(1, task.sample_total + 1)
    ]


def _build_payload(task: AnnotationTaskModel, sample_items: list[dict[str, object]]) -> dict[str, object]:
    annotations = [item["annotation"] for item in sample_items if isinstance(item.get("annotation"), dict)]
    labeled_count = len(annotations)
    task_type = normalize_task_type(task.capability.task_type)
    return {
        "schema_version": "1.0",
        "task_id": task.id,
        "capability_name": task.capability.capability_name,
        "task_type": task_type,
        "task_name": task.task_name,
        "dataset_path": task.dataset_binding.dataset_path,
        "sample_total": task.sample_total,
        "labeled_count": labeled_count,
        "annotations": annotations,
        "sample_items": sample_items,
        "annotation_schema": build_annotation_schema(task_type),
    }


def _load_payload(annotation_tasks_root: Path, task: AnnotationTaskModel) -> dict[str, object]:
    result_path = _annotation_result_path(annotation_tasks_root, task.id)
    if not result_path.exists():
        return _build_payload(task, _default_sample_items(task))
    payload = json.loads(result_path.read_text(encoding="utf-8"))
    sample_items = payload.get("sample_items")
    if not isinstance(sample_items, list):
        sample_items = _default_sample_items(task)
    return _build_payload(task, [item for item in sample_items if isinstance(item, dict)])


def _annotation_result_path(annotation_tasks_root: Path, task_id: int) -> Path:
    annotation_tasks_root.mkdir(parents=True, exist_ok=True)
    return annotation_tasks_root / f"annotation_task_{task_id}.json"


def _validate_annotations_payload(
    task: AnnotationTaskModel,
    annotations: list[dict[str, object]],
) -> list[dict[str, object]]:
    task_type = normalize_task_type(task.capability.task_type)
    normalized_annotations: list[dict[str, object]] = []
    for index, item in enumerate(annotations):
        if not isinstance(item, dict) or not item:
            raise ValueError(f"annotations[{index}] 必须为非空对象。")
        if any(not isinstance(key, str) or not key.strip() for key in item):
            raise ValueError(f"annotations[{index}] 包含非法字段名。")
        normalized_annotations.append(validate_annotation_payload(task_type, item, index))

    labeled_count = len(normalized_annotations)
    if labeled_count > task.sample_total:
        raise ValueError("标注结果数量不能超过样本总数。")

    payload_size = len(json.dumps(normalized_annotations, ensure_ascii=False).encode("utf-8"))
    if payload_size > MAX_ANNOTATION_RESULT_BYTES:
        raise ValueError("标注结果内容过大，超过单任务存储限制。")

    return normalized_annotations


def _to_summary(task: AnnotationTaskModel) -> AnnotationTaskSummary:
    task_type = normalize_task_type(task.capability.task_type)
    return AnnotationTaskSummary(
        task_id=task.id,
        capability_name=task.capability.capability_name,
        task_type=task_type,
        task_name=task.task_name,
        dataset_path=task.dataset_binding.dataset_path,
        status=task.status,
        sample_total=task.sample_total,
        labeled_count=task.labeled_count,
        result_path=task.result_path,
        sample_items=[],
        annotation_schema=build_annotation_schema(task_type),
        created_at=task.created_at.isoformat() if task.created_at else None,
        updated_at=task.updated_at.isoformat() if task.updated_at else None,
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


def get_annotation_task_detail(
    session: Session,
    annotation_tasks_root: Path,
    task_id: int,
) -> AnnotationTaskSummary:
    task = session.get(AnnotationTaskModel, task_id)
    if task is None:
        raise AnnotationTaskNotFoundError("标注任务不存在。")
    payload = _load_payload(annotation_tasks_root, task)
    summary = _to_summary(task)
    return AnnotationTaskSummary(
        task_id=summary.task_id,
        capability_name=summary.capability_name,
        task_type=summary.task_type,
        task_name=summary.task_name,
        dataset_path=summary.dataset_path,
        status=summary.status,
        sample_total=summary.sample_total,
        labeled_count=summary.labeled_count,
        result_path=summary.result_path,
        sample_items=[item for item in payload["sample_items"] if isinstance(item, dict)],
        annotation_schema=summary.annotation_schema,
        created_at=summary.created_at,
        updated_at=summary.updated_at,
    )


def update_annotation_task_samples(
    session: Session,
    annotation_tasks_root: Path,
    task_id: int,
    annotations: list[dict[str, object]],
    *,
    mark_submitted: bool,
) -> AnnotationTaskSummary:
    task = session.get(AnnotationTaskModel, task_id)
    if task is None:
        raise AnnotationTaskNotFoundError("标注任务不存在。")
    normalized_annotations = _validate_annotations_payload(task, annotations)
    payload = _load_payload(annotation_tasks_root, task)
    sample_items = [item for item in payload["sample_items"] if isinstance(item, dict)]
    item_map = {
        str(item.get("sample_id")): item
        for item in sample_items
        if isinstance(item.get("sample_id"), str) and str(item.get("sample_id"))
    }
    if len(item_map) < task.sample_total:
        for index in range(1, task.sample_total + 1):
            sample_id = f"sample_{index}"
            item_map.setdefault(
                sample_id,
                {
                    "sample_id": sample_id,
                    "status": "pending",
                    "annotation": None,
                    "updated_at": None,
                },
            )
    for index, item in enumerate(normalized_annotations):
        sample_id = str(item["sample_id"]).strip()
        if sample_id not in item_map:
            placeholder_key = next(
                (
                    key
                    for key, current in item_map.items()
                    if key.startswith("sample_")
                    and current.get("annotation") is None
                    and current.get("status") == "pending"
                ),
                None,
            )
            if placeholder_key is not None:
                target = item_map.pop(placeholder_key)
                target["sample_id"] = sample_id
                item_map[sample_id] = target
            elif len(item_map) < task.sample_total:
                item_map[sample_id] = {
                    "sample_id": sample_id,
                    "status": "pending",
                    "annotation": None,
                    "updated_at": None,
                }
            else:
                raise ValueError(f"annotations[{index}] 的 sample_id 超出当前任务样本范围。")
        target = item_map[sample_id]
        annotation_payload = {key: value for key, value in item.items() if key != "sample_id"}
        target["annotation"] = annotation_payload
        target["status"] = "submitted" if mark_submitted else "labeled"
        target["updated_at"] = datetime.now(timezone.utc).isoformat()

    ordered_items = sorted(item_map.values(), key=lambda current: str(current.get("sample_id")))
    next_payload = _build_payload(task, ordered_items)
    labeled_count = int(next_payload["labeled_count"])
    result_path = _annotation_result_path(annotation_tasks_root, task.id)
    result_path.write_text(json.dumps(next_payload, ensure_ascii=False, indent=2), encoding="utf-8")

    task.result_path = str(result_path.resolve())
    task.labeled_count = labeled_count
    if labeled_count == 0:
        task.status = "pending"
    elif mark_submitted and labeled_count >= task.sample_total:
        task.status = "completed"
    else:
        task.status = "annotating"
    session.commit()
    session.refresh(task)
    return get_annotation_task_detail(session, annotation_tasks_root, task.id)


def submit_annotation_task_result(
    session: Session,
    annotation_tasks_root: Path,
    task_id: int,
    annotations: list[dict[str, object]],
) -> AnnotationTaskSummary:
    return update_annotation_task_samples(
        session=session,
        annotation_tasks_root=annotation_tasks_root,
        task_id=task_id,
        annotations=annotations,
        mark_submitted=True,
    )


def delete_annotation_task(session: Session, task_id: int) -> None:
    task = session.get(AnnotationTaskModel, task_id)
    if task is None:
        raise AnnotationTaskNotFoundError("标注任务不存在。")
    session.delete(task)
    session.commit()
