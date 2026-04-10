"""能力测试推理适配器注册中心。

为平台注册的各 AI 能力提供真实推理入口，用于测试验收。
当 capability_name 匹配已注册的适配器时，test_service 将调用适配器
执行真实推理；否则回退到模拟推理。
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Protocol


class TestInferenceAdapter(Protocol):
    """测试推理适配器协议。"""

    def infer(
        self,
        *,
        capability_name: str,
        model_version: str,
        model_artifact_path: str,
        input_path: str,
        task_type: str,
    ) -> dict[str, Any]:
        """执行真实推理并返回推理结果。

        返回值必须包含:
        - actual_output: str  推理输出（用于期望输出比对）
        - score: float        置信度得分
        - raw_output: dict    完整推理输出
        - duration_ms: int    耗时（毫秒）
        """
        ...


_ADAPTER_REGISTRY: dict[str, TestInferenceAdapter] = {}


def register_test_adapter(capability_name: str, adapter: TestInferenceAdapter) -> None:
    _ADAPTER_REGISTRY[capability_name] = adapter


def get_test_adapter(capability_name: str) -> TestInferenceAdapter | None:
    return _ADAPTER_REGISTRY.get(capability_name)


def _auto_register() -> None:
    """自动注册已实现的能力测试适配器。"""
    try:
        from app.services.capability_adapters.face_detect_test import FaceDetectTestAdapter
        register_test_adapter("face_detect", FaceDetectTestAdapter())
    except ImportError:
        pass
    try:
        from app.services.capability_adapters.face_attribute_test import FaceAttributeTestAdapter
        register_test_adapter("face_attribute", FaceAttributeTestAdapter())
    except ImportError:
        pass


_auto_register()
