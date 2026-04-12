"""能力训练适配器注册中心。

为平台注册的各 AI 能力提供真实训练入口。当 capability_name 匹配已注册
的适配器时，execute_training_task 将调用适配器执行真实训练；否则回退到
模拟训练。
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Protocol


class TrainingAdapter(Protocol):
    """训练适配器协议。"""

    def execute(
        self,
        *,
        capability_name: str,
        task_type: str,
        workspace_dir: Path,
        dataset_path: str,
        export_dir: Path,
        train_params: dict[str, Any],
        log_callback: Callable[[str], None],
    ) -> dict[str, Any]:
        """执行真实训练并返回 result_summary。"""
        ...


_ADAPTER_REGISTRY: dict[str, TrainingAdapter] = {}


def register_training_adapter(capability_name: str, adapter: TrainingAdapter) -> None:
    _ADAPTER_REGISTRY[capability_name] = adapter


def get_training_adapter(capability_name: str) -> TrainingAdapter | None:
    return _ADAPTER_REGISTRY.get(capability_name)


def _auto_register() -> None:
    """自动注册已实现的能力适配器。"""
    try:
        from app.services.capability_adapters.face_detect_train import FaceDetectTrainAdapter
        register_training_adapter("face_detect", FaceDetectTrainAdapter())
    except ImportError:
        pass
    try:
        from app.services.capability_adapters.face_attribute_train import FaceAttributeTrainAdapter
        register_training_adapter("face_attribute", FaceAttributeTrainAdapter())
    except ImportError:
        pass


_auto_register()
