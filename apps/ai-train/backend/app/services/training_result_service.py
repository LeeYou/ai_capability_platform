from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path

from sqlalchemy.orm import Session

from app.db.models import TrainingTaskModel
from app.services.task_contracts import normalize_task_type
from platform_shared.backend.contracts import validate_training_result_summary


class TrainingResultError(ValueError):
    """训练结果处理失败。"""


def build_validated_training_result_summary(
    *,
    task: TrainingTaskModel,
    result_summary: dict[str, object],
    expected_execution_mode: str,
) -> dict[str, object]:
    if not result_summary:
        raise TrainingResultError("result_summary 不能为空。")

    try:
        payload = validate_training_result_summary(
            result_summary,
            expected_task_id=task.id,
            expected_capability_name=task.capability.capability_name,
            expected_task_type=normalize_task_type(task.capability.task_type),
            expected_execution_mode=expected_execution_mode,
        )
    except ValueError as exc:
        raise TrainingResultError(str(exc)) from exc

    payload.setdefault("task_name", task.task_name)
    payload.setdefault("backend_type", task.backend_type)
    payload.setdefault("recorded_at", datetime.now(timezone.utc).isoformat())
    return payload


def persist_training_result_summary(
    *,
    session: Session,
    task: TrainingTaskModel,
    summary_path: Path,
    payload: dict[str, object],
) -> dict[str, object]:
    summary_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    session.flush()
    return payload
