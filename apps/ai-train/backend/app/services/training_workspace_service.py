from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path

from app.db.models import TrainingTaskModel
from app.services.task_contracts import (
    build_adapter_summary,
    build_template_bundle,
    build_training_input,
    normalize_task_type,
)


@dataclass(frozen=True)
class TrainingWorkspaceArtifacts:
    task_type: str
    capability_name: str
    execution_mode: str
    train_params: dict[str, object]
    training_input: dict[str, object]
    template_bundle: dict[str, object]
    execution_plan: dict[str, object]


def build_training_workspace_artifacts(
    *,
    task: TrainingTaskModel,
    workspace_dir: Path,
    config_path: Path,
    script_path: Path,
    execution_plan_path: Path,
    training_input_path: Path,
    template_bundle_path: Path,
    model_export_spec_path: Path,
    train_runner_path: Path,
    export_dir: Path,
    execution_mode: str,
) -> TrainingWorkspaceArtifacts:
    train_params = json.loads(task.train_params_json) if task.train_params_json else {}
    task_type = normalize_task_type(task.capability.task_type)
    capability_name = task.capability.capability_name
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
        capability_name=capability_name,
        task_type=task_type,
        annotations=annotations,
        dataset_path=task.dataset_binding.dataset_path,
    )
    template_bundle = build_template_bundle(capability_name, task_type)
    adapter_summary = build_adapter_summary(training_input)
    config_payload = {
        "task_id": task.id,
        "capability_name": capability_name,
        "task_type": task_type,
        "task_name": task.task_name,
        "dataset_path": task.dataset_binding.dataset_path,
        "annotation_task_id": task.annotation_task_id,
        "execution_mode": execution_mode,
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
        "execution_mode": execution_mode,
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
            "AI_TRAIN_CAPABILITY": capability_name,
            "AI_TRAIN_BACKEND_TYPE": task.backend_type,
            "AI_TRAIN_TASK_TYPE": task_type,
        },
        "command": [
            "/bin/bash",
            str(script_path.resolve()),
        ],
    }
    execution_plan_path.write_text(json.dumps(execution_plan, ensure_ascii=False, indent=2), encoding="utf-8")
    return TrainingWorkspaceArtifacts(
        task_type=task_type,
        capability_name=capability_name,
        execution_mode=execution_mode,
        train_params=train_params,
        training_input=training_input,
        template_bundle=template_bundle,
        execution_plan=execution_plan,
    )
