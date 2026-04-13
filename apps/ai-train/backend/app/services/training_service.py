from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import AnnotationTaskModel, CapabilityRegistryModel, TrainingTaskModel
from app.services.registry_service import normalize_capability_name
from app.services.task_contracts import (
    build_adapter_summary,
    build_template_bundle,
    build_training_input,
    normalize_task_type,
)

ALLOWED_TRAINING_STATUSES = {"pending", "running", "completed", "failed"}
MAX_TRAINING_LOG_BYTES = 1_048_576


class TrainingTaskNotFoundError(ValueError):
    """训练任务不存在。"""


@dataclass(frozen=True)
class TrainingTaskSummary:
    task_id: int
    capability_name: str
    task_type: str
    task_name: str
    dataset_path: str
    status: str
    framework: str
    backend_type: str
    annotation_task_id: int | None
    retry_count: int
    log_path: str | None
    workspace_path: str | None
    started_at: str | None
    completed_at: str | None
    latest_logs: list[str]
    execution_plan: dict[str, object] | None
    result_summary: dict[str, object] | None
    training_input_path: str | None
    template_bundle_path: str | None
    export_dir: str | None
    created_at: str | None
    updated_at: str | None


def _result_summary_path(training_jobs_root: Path, task_id: int) -> Path:
    return _workspace_dir(training_jobs_root, task_id) / "result_summary.json"


def _execution_plan_path(training_jobs_root: Path, task_id: int) -> Path:
    return _workspace_dir(training_jobs_root, task_id) / "execution_plan.json"


def _training_input_path(training_jobs_root: Path, task_id: int) -> Path:
    return _workspace_dir(training_jobs_root, task_id) / "training_input.json"


def _template_bundle_path(training_jobs_root: Path, task_id: int) -> Path:
    return _workspace_dir(training_jobs_root, task_id) / "template_bundle.json"


def _model_export_spec_path(training_jobs_root: Path, task_id: int) -> Path:
    return _workspace_dir(training_jobs_root, task_id) / "model_export_spec.json"


def _train_runner_path(training_jobs_root: Path, task_id: int) -> Path:
    return _workspace_dir(training_jobs_root, task_id) / "train_runner.py"


def _export_dir(training_jobs_root: Path, task_id: int) -> Path:
    path = _workspace_dir(training_jobs_root, task_id) / "exported_model"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _read_json_if_exists(path: Path) -> dict[str, object] | None:
    if not path.exists():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else None


def _read_latest_logs(task: TrainingTaskModel, tail_lines: int) -> list[str]:
    if not task.log_path:
        return []
    log_path = Path(task.log_path)
    if not log_path.exists():
        return []
    lines = [line.rstrip("\n") for line in log_path.read_text(encoding="utf-8").splitlines()]
    return lines[-tail_lines:]


def _to_summary(
    task: TrainingTaskModel,
    *,
    training_jobs_root: Path | None = None,
    tail_lines: int = 20,
) -> TrainingTaskSummary:
    execution_plan = None
    result_summary = None
    training_input_path = None
    template_bundle_path = None
    export_dir = None
    task_type = normalize_task_type(task.capability.task_type)
    if training_jobs_root is not None:
        execution_plan = _read_json_if_exists(_execution_plan_path(training_jobs_root, task.id))
        result_summary = _read_json_if_exists(_result_summary_path(training_jobs_root, task.id))
        training_input_candidate = _training_input_path(training_jobs_root, task.id)
        template_bundle_candidate = _template_bundle_path(training_jobs_root, task.id)
        export_candidate = _workspace_dir(training_jobs_root, task.id) / "exported_model"
        training_input_path = str(training_input_candidate.resolve()) if training_input_candidate.exists() else None
        template_bundle_path = str(template_bundle_candidate.resolve()) if template_bundle_candidate.exists() else None
        export_dir = str(export_candidate.resolve()) if export_candidate.exists() else None
    return TrainingTaskSummary(
        task_id=task.id,
        capability_name=task.capability.capability_name,
        task_type=task_type,
        task_name=task.task_name,
        dataset_path=task.dataset_binding.dataset_path,
        status=task.status,
        framework=task.framework,
        backend_type=task.backend_type,
        annotation_task_id=task.annotation_task_id,
        retry_count=task.retry_count,
        log_path=task.log_path,
        workspace_path=task.workspace_path,
        started_at=task.started_at.isoformat() if task.started_at else None,
        completed_at=task.completed_at.isoformat() if task.completed_at else None,
        latest_logs=_read_latest_logs(task, tail_lines),
        execution_plan=execution_plan,
        result_summary=result_summary,
        training_input_path=training_input_path,
        template_bundle_path=template_bundle_path,
        export_dir=export_dir,
        created_at=task.created_at.isoformat() if task.created_at else None,
        updated_at=task.updated_at.isoformat() if task.updated_at else None,
    )


def _log_path(training_logs_root: Path, task_id: int) -> Path:
    training_logs_root.mkdir(parents=True, exist_ok=True)
    return training_logs_root / f"training_task_{task_id}.log"


def _workspace_dir(training_jobs_root: Path, task_id: int) -> Path:
    training_jobs_root.mkdir(parents=True, exist_ok=True)
    path = (training_jobs_root / str(task_id)).resolve()
    if not (path == training_jobs_root or training_jobs_root in path.parents):
        raise ValueError("训练工作区目录非法。")
    path.mkdir(parents=True, exist_ok=True)
    return path


def _validate_status_transition(current_status: str, target_status: str) -> None:
    if target_status not in ALLOWED_TRAINING_STATUSES:
        raise ValueError("训练任务状态非法。")
    if current_status == target_status:
        return

    allowed_transitions = {
        "pending": {"running", "failed"},
        "running": {"completed", "failed"},
        "failed": {"running"},
        "completed": set(),
    }
    if target_status not in allowed_transitions[current_status]:
        raise ValueError(f"不支持从 {current_status} 变更为 {target_status}。")


def create_training_task(
    session: Session,
    training_logs_root: Path,
    capability_name: str,
    task_name: str,
    framework: str,
    backend_type: str,
    annotation_task_id: int | None,
    train_params: dict[str, object],
) -> TrainingTaskSummary:
    normalized_name = normalize_capability_name(capability_name)
    normalized_task_name = task_name.strip()
    normalized_framework = framework.strip()
    normalized_backend_type = backend_type.strip()
    if not normalized_task_name:
        raise ValueError("task_name 不能为空。")
    if not normalized_framework:
        raise ValueError("framework 不能为空。")
    if not normalized_backend_type:
        raise ValueError("backend_type 不能为空。")

    capability = session.scalar(
        select(CapabilityRegistryModel).where(CapabilityRegistryModel.capability_name == normalized_name)
    )
    if capability is None:
        raise ValueError("能力尚未注册，无法创建训练任务。")
    if capability.dataset_binding is None:
        raise ValueError("能力尚未绑定数据集，无法创建训练任务。")

    annotation_task: AnnotationTaskModel | None = None
    if annotation_task_id is not None:
        annotation_task = session.get(AnnotationTaskModel, annotation_task_id)
        if annotation_task is None or annotation_task.capability_id != capability.id:
            raise ValueError("标注任务不存在或不属于当前能力。")
        if annotation_task.status != "completed":
            raise ValueError("仅支持使用已完成的标注任务发起训练。")

    task = TrainingTaskModel(
        capability_id=capability.id,
        dataset_binding_id=capability.dataset_binding.id,
        annotation_task_id=annotation_task_id,
        task_name=normalized_task_name,
        status="pending",
        framework=normalized_framework,
        backend_type=normalized_backend_type,
        train_params_json=json.dumps(train_params, ensure_ascii=False, sort_keys=True) if train_params else None,
        retry_count=0,
    )
    session.add(task)
    session.commit()
    session.refresh(task)

    log_path = _log_path(training_logs_root, task.id)
    log_path.write_text(
        f"{datetime.now(timezone.utc).isoformat()} [pending] 训练任务已创建\n",
        encoding="utf-8",
    )
    task.log_path = str(log_path.resolve())
    session.commit()
    session.refresh(task)
    return _to_summary(task)


def list_training_tasks(session: Session) -> list[TrainingTaskSummary]:
    tasks = session.scalars(select(TrainingTaskModel).order_by(TrainingTaskModel.id.asc())).all()
    return [_to_summary(task) for task in tasks]


def get_training_task(session: Session, task_id: int) -> TrainingTaskSummary:
    task = session.get(TrainingTaskModel, task_id)
    if task is None:
        raise TrainingTaskNotFoundError("训练任务不存在。")
    return _to_summary(task)


def get_training_task_detail(
    session: Session,
    training_jobs_root: Path,
    task_id: int,
) -> TrainingTaskSummary:
    task = session.get(TrainingTaskModel, task_id)
    if task is None:
        raise TrainingTaskNotFoundError("训练任务不存在。")
    return _to_summary(task, training_jobs_root=training_jobs_root)


def update_training_task_status(session: Session, task_id: int, status: str) -> TrainingTaskSummary:
    task = session.get(TrainingTaskModel, task_id)
    if task is None:
        raise TrainingTaskNotFoundError("训练任务不存在。")

    normalized_status = status.strip()
    _validate_status_transition(task.status, normalized_status)
    if task.status != normalized_status:
        if task.status == "failed" and normalized_status == "running":
            task.retry_count += 1
            task.completed_at = None
        if normalized_status == "running" and task.started_at is None:
            task.started_at = datetime.now(timezone.utc).replace(tzinfo=None)
        if normalized_status in {"completed", "failed"}:
            task.completed_at = datetime.now(timezone.utc).replace(tzinfo=None)
        task.status = normalized_status
        session.commit()
        session.refresh(task)

    return _to_summary(task)


def append_training_task_log(
    session: Session,
    training_logs_root: Path,
    task_id: int,
    message: str,
) -> TrainingTaskSummary:
    task = session.get(TrainingTaskModel, task_id)
    if task is None:
        raise TrainingTaskNotFoundError("训练任务不存在。")

    normalized_message = message.strip()
    if not normalized_message:
        raise ValueError("message 不能为空。")

    log_path = Path(task.log_path) if task.log_path else _log_path(training_logs_root, task.id)
    existing_size = log_path.stat().st_size if log_path.exists() else 0
    message_bytes = len(normalized_message.encode("utf-8"))
    if existing_size + message_bytes > MAX_TRAINING_LOG_BYTES:
        raise ValueError("训练日志内容过大，超过单任务存储限制。")

    with log_path.open("a", encoding="utf-8") as file_obj:
        file_obj.write(f"{datetime.now(timezone.utc).isoformat()} [{task.status}] {normalized_message}\n")

    task.log_path = str(log_path.resolve())
    session.commit()
    session.refresh(task)
    return _to_summary(task)


def prepare_training_workspace(
    session: Session,
    training_jobs_root: Path,
    task_id: int,
) -> TrainingTaskSummary:
    task = session.get(TrainingTaskModel, task_id)
    if task is None:
        raise TrainingTaskNotFoundError("训练任务不存在。")

    workspace_dir = _workspace_dir(training_jobs_root, task.id)
    config_path = workspace_dir / "train_config.json"
    script_path = workspace_dir / "run_training.sh"
    execution_plan_path = workspace_dir / "execution_plan.json"
    training_input_path = _training_input_path(training_jobs_root, task.id)
    template_bundle_path = _template_bundle_path(training_jobs_root, task.id)
    model_export_spec_path = _model_export_spec_path(training_jobs_root, task.id)
    train_runner_path = _train_runner_path(training_jobs_root, task.id)
    export_dir = _export_dir(training_jobs_root, task.id)
    train_params = json.loads(task.train_params_json) if task.train_params_json else {}
    task_type = normalize_task_type(task.capability.task_type)
    template_bundle = build_template_bundle(task.capability.capability_name, task_type)
    annotation_payload: dict[str, object] = {}
    if task.annotation_task is not None and task.annotation_task.result_path:
        annotation_result_path = Path(task.annotation_task.result_path)
        if annotation_result_path.exists():
            loaded_payload = json.loads(annotation_result_path.read_text(encoding="utf-8"))
            if isinstance(loaded_payload, dict):
                annotation_payload = loaded_payload
    raw_annotations = annotation_payload.get("annotations", [])
    annotations = [item for item in raw_annotations if isinstance(item, dict)] if isinstance(raw_annotations, list) else []
    training_input = build_training_input(
        capability_name=task.capability.capability_name,
        task_type=task_type,
        annotations=annotations,
        dataset_path=task.dataset_binding.dataset_path,
    )
    adapter_summary = build_adapter_summary(training_input)
    config_payload = {
        "task_id": task.id,
        "capability_name": task.capability.capability_name,
        "task_type": task_type,
        "task_name": task.task_name,
        "dataset_path": task.dataset_binding.dataset_path,
        "annotation_task_id": task.annotation_task_id,
        "framework": task.framework,
        "backend_type": task.backend_type,
        "train_params": train_params,
        "log_path": task.log_path,
        "training_input_path": str(training_input_path.resolve()),
        "template_bundle_path": str(template_bundle_path.resolve()),
        "export_dir": str(export_dir.resolve()),
    }
    config_path.write_text(json.dumps(config_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    training_input_path.write_text(json.dumps(training_input, ensure_ascii=False, indent=2), encoding="utf-8")
    template_bundle_path.write_text(json.dumps(template_bundle, ensure_ascii=False, indent=2), encoding="utf-8")
    model_export_spec_path.write_text(
        json.dumps(
            {
                "task_id": task.id,
                "task_type": task_type,
                "export_dir": str(export_dir.resolve()),
                "expected_files": ["weights.bin", "metrics.json", "training_manifest.json"],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    train_runner_path.write_text(
        "\n".join(
            [
                "#!/usr/bin/env python3",
                "import json",
                "from pathlib import Path",
                "",
                "config = json.loads(Path('train_config.json').read_text(encoding='utf-8'))",
                "training_input = json.loads(Path('training_input.json').read_text(encoding='utf-8'))",
                "export_spec = json.loads(Path('model_export_spec.json').read_text(encoding='utf-8'))",
                "export_dir = Path(export_spec['export_dir'])",
                "export_dir.mkdir(parents=True, exist_ok=True)",
                "(export_dir / 'weights.bin').write_text('simulated-weights', encoding='utf-8')",
                "(export_dir / 'metrics.json').write_text(json.dumps({'sample_count': training_input.get('sample_count', 0)}, ensure_ascii=False, indent=2), encoding='utf-8')",
                "(export_dir / 'training_manifest.json').write_text(json.dumps({'task_id': config['task_id'], 'task_type': config['task_type']}, ensure_ascii=False, indent=2), encoding='utf-8')",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    train_runner_path.chmod(0o755)
    script_path.write_text(
        "\n".join(
            [
                "#!/usr/bin/env bash",
                "set -euo pipefail",
                'echo "[ai-train] 准备执行训练任务"',
                f'echo "[ai-train] 配置文件: {config_path.resolve()}"',
                f'cd "{workspace_dir.resolve()}"',
                f'"{train_runner_path.resolve()}"',
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    script_path.chmod(0o755)
    execution_plan = {
        "container_image": "agilestar/ai-train:cuda11.8",
        "entrypoint": str(script_path.resolve()),
        "workspace_dir": str(workspace_dir.resolve()),
        "task_type": task_type,
        "resource_profile": "gpu" if task.backend_type.lower() == "gpu" else "cpu",
        "mounts": {
            "dataset": task.dataset_binding.dataset_path,
            "workspace": str(workspace_dir.resolve()),
            "logs": task.log_path,
        },
        "artifacts": {
            "training_input_path": str(training_input_path.resolve()),
            "template_bundle_path": str(template_bundle_path.resolve()),
            "model_export_spec_path": str(model_export_spec_path.resolve()),
            "export_dir": str(export_dir.resolve()),
        },
        "adapter_summary": adapter_summary,
        "environment": {
            "AI_TRAIN_TASK_ID": str(task.id),
            "AI_TRAIN_CAPABILITY": task.capability.capability_name,
            "AI_TRAIN_BACKEND_TYPE": task.backend_type,
            "AI_TRAIN_TASK_TYPE": task_type,
        },
        "command": [
            "/bin/bash",
            str(script_path.resolve()),
        ],
    }
    execution_plan_path.write_text(json.dumps(execution_plan, ensure_ascii=False, indent=2), encoding="utf-8")

    task.workspace_path = str(workspace_dir.resolve())
    session.commit()
    session.refresh(task)
    return _to_summary(task, training_jobs_root=training_jobs_root)


def execute_training_task(
    session: Session,
    training_jobs_root: Path,
    training_logs_root: Path,
    task_id: int,
) -> TrainingTaskSummary:
    task = session.get(TrainingTaskModel, task_id)
    if task is None:
        raise TrainingTaskNotFoundError("训练任务不存在。")
    if task.status == "running":
        raise ValueError("训练任务正在执行中。")
    if task.status == "completed":
        raise ValueError("训练任务已完成，无需重复执行。")

    prepare_training_workspace(session, training_jobs_root, task_id)
    update_training_task_status(session, task_id, "running")

    training_input_path = _training_input_path(training_jobs_root, task_id)
    template_bundle_path = _template_bundle_path(training_jobs_root, task_id)
    export_dir = _export_dir(training_jobs_root, task_id)
    workspace_dir = _workspace_dir(training_jobs_root, task_id)
    train_params = json.loads(task.train_params_json) if task.train_params_json else {}
    training_input = json.loads(training_input_path.read_text(encoding="utf-8"))
    template_bundle = json.loads(template_bundle_path.read_text(encoding="utf-8"))
    sample_count = int(training_input.get("sample_count", 0))
    task_type = normalize_task_type(task.capability.task_type)
    capability_name = task.capability.capability_name

    append_training_task_log(
        session=session,
        training_logs_root=training_logs_root,
        task_id=task_id,
        message=f"训练输入适配完成，样本数={sample_count}，任务类型={task_type}",
    )

    # ── 尝试分发到真实训练适配器 ──
    from app.services.capability_adapters import get_training_adapter

    adapter = get_training_adapter(capability_name)
    if adapter is not None:
        append_training_task_log(
            session=session,
            training_logs_root=training_logs_root,
            task_id=task_id,
            message=f"检测到真实训练适配器: {capability_name}，启动真实训练...",
        )

        def _log_callback(msg: str) -> None:
            append_training_task_log(
                session=session,
                training_logs_root=training_logs_root,
                task_id=task_id,
                message=msg,
            )

        try:
            result_summary = adapter.execute(
                capability_name=capability_name,
                task_type=task_type,
                workspace_dir=workspace_dir,
                dataset_path=task.dataset_binding.dataset_path,
                export_dir=export_dir,
                train_params=train_params,
                log_callback=_log_callback,
            )
            result_summary.setdefault("task_id", task_id)
            result_summary.setdefault("training_input_path", str(training_input_path.resolve()))
            result_summary.setdefault("template_bundle_path", str(template_bundle_path.resolve()))
            result_summary.setdefault("export_dir", str(export_dir.resolve()))
        except Exception as exc:
            append_training_task_log(
                session=session,
                training_logs_root=training_logs_root,
                task_id=task_id,
                message=f"真实训练执行失败: {exc}",
            )
            update_training_task_status(session, task_id, "failed")
            raise ValueError(f"训练执行失败: {exc}") from exc

        record_training_task_result(session, training_jobs_root, task_id, result_summary)
        update_training_task_status(session, task_id, "completed")
        append_training_task_log(
            session=session,
            training_logs_root=training_logs_root,
            task_id=task_id,
            message=f"真实训练执行完成: {capability_name}",
        )
        return get_training_task_detail(session, training_jobs_root, task_id)

    # ── 回退：模拟训练（无真实适配器时） ──
    epochs = train_params.get("epochs", 1)
    if not isinstance(epochs, int) or epochs <= 0:
        epochs = 1
    epochs = min(epochs, 20)

    for epoch in range(1, epochs + 1):
        loss = max(0.01, 1.0 / (epoch + 1))
        append_training_task_log(
            session=session,
            training_logs_root=training_logs_root,
            task_id=task_id,
            message=f"epoch={epoch} loss={loss:.4f}",
        )

    best_metric = round(min(0.99, 0.75 + sample_count * 0.02 + epochs * 0.01), 4)
    exported_files = ["weights.bin", "metrics.json", "training_manifest.json"]
    (export_dir / "weights.bin").write_text("simulated-weights", encoding="utf-8")
    (export_dir / "metrics.json").write_text(
        json.dumps(
            {
                "best_metric": best_metric,
                "epochs": epochs,
                "sample_count": sample_count,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    (export_dir / "training_manifest.json").write_text(
        json.dumps(
            {
                "task_id": task_id,
                "capability_name": capability_name,
                "task_type": task_type,
                "template_bundle": template_bundle,
                "exported_files": exported_files,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    result_summary = {
        "task_id": task_id,
        "capability_name": capability_name,
        "task_type": task_type,
        "best_metric": best_metric,
        "epochs": epochs,
        "sample_count": sample_count,
        "training_input_path": str(training_input_path.resolve()),
        "template_bundle_path": str(template_bundle_path.resolve()),
        "export_dir": str(export_dir.resolve()),
        "exported_files": exported_files,
    }
    record_training_task_result(session, training_jobs_root, task_id, result_summary)
    update_training_task_status(session, task_id, "completed")
    append_training_task_log(
        session=session,
        training_logs_root=training_logs_root,
        task_id=task_id,
        message=f"训练执行完成，best_metric={best_metric:.4f}，导出文件={','.join(exported_files)}",
    )
    return get_training_task_detail(session, training_jobs_root, task_id)


def record_training_task_result(
    session: Session,
    training_jobs_root: Path,
    task_id: int,
    result_summary: dict[str, object],
) -> TrainingTaskSummary:
    task = session.get(TrainingTaskModel, task_id)
    if task is None:
        raise TrainingTaskNotFoundError("训练任务不存在。")
    if not result_summary:
        raise ValueError("result_summary 不能为空。")

    summary_path = _result_summary_path(training_jobs_root, task.id)
    payload = dict(result_summary)
    payload.setdefault("task_id", task.id)
    payload.setdefault("capability_name", task.capability.capability_name)
    payload.setdefault("task_name", task.task_name)
    payload.setdefault("backend_type", task.backend_type)
    payload.setdefault("recorded_at", datetime.now(timezone.utc).isoformat())
    summary_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return _to_summary(task, training_jobs_root=training_jobs_root)


def get_training_task_log_snapshot(
    session: Session,
    training_jobs_root: Path,
    task_id: int,
    *,
    tail_lines: int = 50,
) -> TrainingTaskSummary:
    task = session.get(TrainingTaskModel, task_id)
    if task is None:
        raise TrainingTaskNotFoundError("训练任务不存在。")
    return _to_summary(task, training_jobs_root=training_jobs_root, tail_lines=tail_lines)
