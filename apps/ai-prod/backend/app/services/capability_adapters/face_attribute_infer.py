"""face_attribute 能力生产推理适配器 — MobileNetV3-Large ONNX 多任务推理。

在生产推理阶段使用 ONNX Runtime 加载多任务模型执行真实人脸属性分析。
支持图像文件路径和 base64 编码的人脸裁剪图像输入。
"""
from __future__ import annotations

import base64
import io
import json
import time
from pathlib import Path
from typing import Any

import numpy as np


# ── 默认任务配置 ──
DEFAULT_TASK_CONFIG: dict[str, Any] = {
    "glasses": {"type": "binary", "num_classes": 2},
    "mask": {"type": "binary", "num_classes": 2},
    "hat": {"type": "binary", "num_classes": 2},
    "integrity": {"type": "binary", "num_classes": 2},
    "side_face": {"type": "binary", "num_classes": 2},
    "expression": {"type": "multiclass", "num_classes": 4},
    "head_pose": {"type": "multiclass", "num_classes": 5},
    "age": {"type": "regression"},
}

EXPRESSION_LABELS = ["neutral", "smile", "sad", "angry"]
HEAD_POSE_LABELS = ["front", "left", "right", "up", "down"]


class FaceAttributeInferAdapter:
    """MobileNetV3-Large 多任务人脸属性生产推理适配器。"""

    def __init__(self) -> None:
        self._session = None
        self._loaded_path: str | None = None
        self._output_names: list[str] = []
        self._task_config: dict[str, Any] = {}

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
        started = time.perf_counter()

        session, output_names = self._load_model(model_root)
        input_tensor = self._preprocess(input_type, payload)

        outputs = session.run(output_names, {"input": input_tensor})
        result_map = dict(zip(output_names, outputs))
        attributes = self._parse_outputs(result_map)

        duration_ms = max(1, int((time.perf_counter() - started) * 1000))

        summary_parts = []
        for attr_name, attr_value in attributes.items():
            if isinstance(attr_value, dict):
                summary_parts.append(f"{attr_name}={attr_value.get('label', attr_value.get('value', ''))}")
        summary = "; ".join(summary_parts) if summary_parts else "属性分析完成"

        return {
            "summary": summary,
            "score": self._compute_overall_score(attributes),
            "result": {
                "attributes": attributes,
                "duration_ms": duration_ms,
                "device": device,
                "model_version": model_version,
            },
        }

    def _load_model(self, model_root: str) -> tuple[Any, list[str]]:
        """加载或复用 ONNX Runtime Session。"""
        if self._session is not None and self._loaded_path == model_root:
            return self._session, self._output_names

        model_dir = Path(model_root)
        onnx_path = model_dir / "face_attribute.onnx"
        if not onnx_path.exists():
            raise RuntimeError(f"未找到 ONNX 模型: {onnx_path}")

        try:
            import onnxruntime as ort
        except ImportError as exc:
            raise RuntimeError("onnxruntime 未安装") from exc

        providers = ort.get_available_providers()
        preferred = ["CUDAExecutionProvider", "CPUExecutionProvider"]
        selected = [p for p in preferred if p in providers] or ["CPUExecutionProvider"]

        self._session = ort.InferenceSession(str(onnx_path), providers=selected)
        self._output_names = [o.name for o in self._session.get_outputs()]
        self._loaded_path = model_root

        # 加载任务配置
        labels_path = model_dir / "labels.json"
        if labels_path.exists():
            labels_data = json.loads(labels_path.read_text(encoding="utf-8"))
            self._task_config = labels_data.get("task_config", DEFAULT_TASK_CONFIG)
        else:
            self._task_config = DEFAULT_TASK_CONFIG

        return self._session, self._output_names

    def _preprocess(self, input_type: str, payload: str) -> np.ndarray:
        """预处理人脸图像为模型输入张量。"""
        from PIL import Image

        if input_type == "image" and Path(payload).exists():
            image = Image.open(payload).convert("RGB")
        else:
            try:
                image_bytes = base64.b64decode(payload)
                image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
            except Exception:
                if Path(payload).exists():
                    image = Image.open(payload).convert("RGB")
                else:
                    raise ValueError(f"无法解析输入: input_type={input_type}")

        image = image.resize((224, 224))
        img_array = np.array(image, dtype=np.float32) / 255.0
        mean = np.array([0.485, 0.456, 0.406], dtype=np.float32)
        std = np.array([0.229, 0.224, 0.225], dtype=np.float32)
        img_array = (img_array - mean) / std
        img_array = img_array.transpose(2, 0, 1)  # HWC → CHW
        return np.expand_dims(img_array, axis=0).astype(np.float32)

    def _parse_outputs(self, result_map: dict[str, np.ndarray]) -> dict[str, Any]:
        """将模型原始输出解析为结构化属性结果。"""
        attributes: dict[str, Any] = {}
        task_config = self._task_config or DEFAULT_TASK_CONFIG

        for task_name, output in result_map.items():
            if task_name not in task_config:
                continue
            config = task_config[task_name]
            values = output[0] if output.ndim > 1 else output

            if config["type"] == "binary":
                pred_class = int(np.argmax(values))
                confidence = float(np.max(self._softmax(values)))
                attributes[task_name] = {
                    "label": "yes" if pred_class == 1 else "no",
                    "class": pred_class,
                    "confidence": round(confidence, 4),
                }
            elif config["type"] == "multiclass":
                pred_class = int(np.argmax(values))
                confidence = float(np.max(self._softmax(values)))
                if task_name == "expression":
                    label = EXPRESSION_LABELS[pred_class] if pred_class < len(EXPRESSION_LABELS) else str(pred_class)
                elif task_name == "head_pose":
                    label = HEAD_POSE_LABELS[pred_class] if pred_class < len(HEAD_POSE_LABELS) else str(pred_class)
                else:
                    label = str(pred_class)
                attributes[task_name] = {
                    "label": label,
                    "class": pred_class,
                    "confidence": round(confidence, 4),
                }
            elif config["type"] == "regression":
                value = float(values[0]) if values.ndim > 0 else float(values)
                attributes[task_name] = {"value": round(value, 1)}

        return attributes

    @staticmethod
    def _softmax(x: np.ndarray) -> np.ndarray:
        exp_x = np.exp(x - np.max(x))
        return exp_x / (exp_x.sum() + 1e-8)

    @staticmethod
    def _compute_overall_score(attributes: dict[str, Any]) -> float:
        confidences = []
        for attr in attributes.values():
            if isinstance(attr, dict) and "confidence" in attr:
                confidences.append(attr["confidence"])
        return round(float(np.mean(confidences)), 4) if confidences else 0.5
