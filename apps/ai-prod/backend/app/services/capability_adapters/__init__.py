"""能力生产推理适配器注册中心。

为平台注册的各 AI 能力提供真实推理入口，用于生产环境推理。
当 capability_name 匹配已注册的适配器时，runtime_service.infer 将调用
适配器执行真实推理；否则回退到模拟推理。
"""
from __future__ import annotations

from typing import Any, Protocol


class InferenceAdapter(Protocol):
    """生产推理适配器协议。"""

    def infer(
        self,
        *,
        capability_name: str,
        model_version: str,
        model_root: str,
        input_type: str,
        payload: str,
        device: str,
        options: dict[str, Any],
    ) -> dict[str, Any]:
        """执行真实推理并返回推理结果。

        返回值必须包含:
        - summary: str       推理摘要
        - result: dict       推理结果详情
        - score: float       置信度得分
        """
        ...


_ADAPTER_REGISTRY: dict[str, InferenceAdapter] = {}


def register_inference_adapter(capability_name: str, adapter: InferenceAdapter) -> None:
    _ADAPTER_REGISTRY[capability_name] = adapter


def get_inference_adapter(capability_name: str) -> InferenceAdapter | None:
    return _ADAPTER_REGISTRY.get(capability_name)


def _auto_register() -> None:
    """自动注册已实现的能力推理适配器。"""
    try:
        from app.services.capability_adapters.face_detect_infer import FaceDetectInferAdapter
        register_inference_adapter("face_detect", FaceDetectInferAdapter())
    except ImportError:
        pass
    try:
        from app.services.capability_adapters.face_attribute_infer import FaceAttributeInferAdapter
        register_inference_adapter("face_attribute", FaceAttributeInferAdapter())
    except ImportError:
        pass


_auto_register()
