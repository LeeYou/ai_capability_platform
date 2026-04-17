from __future__ import annotations

from collections.abc import Callable
import json
from pathlib import Path

from app.db.models import TrainingTaskModel
from app.services.task_contracts import normalize_task_type


def execute_training_runtime(
    *,
    task: TrainingTaskModel,
    workspace_dir: Path,
    export_dir: Path,
    training_input_path: Path,
    template_bundle_path: Path,
    append_log: Callable[[str], None],
) -> dict[str, object]:
    train_params = json.loads(task.train_params_json) if task.train_params_json else {}
    training_input = json.loads(training_input_path.read_text(encoding="utf-8"))
    template_bundle = json.loads(template_bundle_path.read_text(encoding="utf-8"))
    sample_count = int(training_input.get("sample_count", 0))
    task_type = normalize_task_type(task.capability.task_type)
    capability_name = task.capability.capability_name

    append_log(f"训练输入适配完成，样本数={sample_count}，任务类型={task_type}")

    from app.services.capability_adapters import get_training_adapter

    adapter = get_training_adapter(capability_name)
    if adapter is not None:
        append_log(f"检测到真实训练适配器: {capability_name}，启动真实训练...")
        try:
            result_summary = adapter.execute(
                capability_name=capability_name,
                task_type=task_type,
                workspace_dir=workspace_dir,
                dataset_path=task.dataset_binding.dataset_path,
                export_dir=export_dir,
                train_params=train_params,
                log_callback=append_log,
            )
        except Exception as exc:
            append_log(f"真实训练执行失败: {exc}")
            raise ValueError(f"训练执行失败: {exc}") from exc

        result_summary.setdefault("execution_mode", "real")
        result_summary.setdefault("task_id", task.id)
        result_summary.setdefault("training_input_path", str(training_input_path.resolve()))
        result_summary.setdefault("template_bundle_path", str(template_bundle_path.resolve()))
        result_summary.setdefault("export_dir", str(export_dir.resolve()))
        append_log(f"真实训练执行完成: {capability_name}")
        return result_summary

    epochs = train_params.get("epochs", 1)
    if not isinstance(epochs, int) or epochs <= 0:
        epochs = 1
    epochs = min(epochs, 20)

    for epoch in range(1, epochs + 1):
        loss = max(0.01, 1.0 / (epoch + 1))
        append_log(f"epoch={epoch} loss={loss:.4f}")

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
                "task_id": task.id,
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
        "task_id": task.id,
        "capability_name": capability_name,
        "task_type": task_type,
        "execution_mode": "simulated",
        "best_metric": best_metric,
        "epochs": epochs,
        "sample_count": sample_count,
        "training_input_path": str(training_input_path.resolve()),
        "template_bundle_path": str(template_bundle_path.resolve()),
        "export_dir": str(export_dir.resolve()),
        "exported_files": exported_files,
    }
    append_log(f"训练执行完成，best_metric={best_metric:.4f}，导出文件={','.join(exported_files)}")
    return result_summary
