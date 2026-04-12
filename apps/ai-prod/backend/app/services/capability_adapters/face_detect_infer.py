"""face_detect 能力生产推理适配器 — YOLOv8n 人脸检测。

在生产推理阶段使用 ultralytics YOLO 或 ONNX Runtime 执行真实人脸检测。
支持图像文件路径和 base64 编码的图像输入。
"""
from __future__ import annotations

import base64
import io
import json
import time
from pathlib import Path
from typing import Any


class FaceDetectInferAdapter:
    """YOLOv8n 人脸检测生产推理适配器。"""

    def __init__(self) -> None:
        self._model = None
        self._loaded_path: str | None = None

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
        model = self._load_model(model_root)

        # 解析输入
        image_input = self._resolve_input(input_type, payload)

        # 执行推理
        conf_threshold = float(options.get("conf_threshold", 0.5))
        results = model(image_input, verbose=False, conf=conf_threshold)

        objects: list[dict[str, Any]] = []
        if results and len(results) > 0:
            result = results[0]
            boxes = result.boxes
            if boxes is not None:
                for i in range(len(boxes)):
                    xyxy = boxes.xyxy[i].tolist()
                    conf = float(boxes.conf[i])
                    objects.append({
                        "label": "face",
                        "bbox": [int(xyxy[0]), int(xyxy[1]), int(xyxy[2]), int(xyxy[3])],
                        "score": round(conf, 4),
                    })

        duration_ms = max(1, int((time.perf_counter() - started) * 1000))
        best_score = max((obj["score"] for obj in objects), default=0.0)

        return {
            "summary": f"检测到 {len(objects)} 个人脸",
            "score": round(best_score, 4),
            "result": {
                "objects": objects,
                "object_count": len(objects),
                "duration_ms": duration_ms,
                "device": device,
                "model_version": model_version,
            },
        }

    def _load_model(self, model_root: str) -> Any:
        """加载或复用 YOLO 模型。"""
        if self._model is not None and self._loaded_path == model_root:
            return self._model

        model_dir = Path(model_root)
        onnx_path = model_dir / "face_detect.onnx"
        pt_path = model_dir / "best.pt"

        try:
            from ultralytics import YOLO
        except ImportError as exc:
            raise RuntimeError("ultralytics 未安装") from exc

        if onnx_path.exists():
            self._model = YOLO(str(onnx_path))
        elif pt_path.exists():
            self._model = YOLO(str(pt_path))
        else:
            raise RuntimeError(f"未找到模型文件: {model_dir}")

        self._loaded_path = model_root
        return self._model

    @staticmethod
    def _resolve_input(input_type: str, payload: str) -> Any:
        """将输入解析为模型可接受的格式。"""
        if input_type == "image" and Path(payload).exists():
            return payload

        # 尝试 base64 解码
        try:
            image_bytes = base64.b64decode(payload)
            from PIL import Image
            return Image.open(io.BytesIO(image_bytes)).convert("RGB")
        except Exception:
            pass

        # 假设 payload 是文件路径
        if Path(payload).exists():
            return payload

        raise ValueError(f"无法解析输入: input_type={input_type}")
