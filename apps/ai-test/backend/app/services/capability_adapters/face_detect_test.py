"""face_detect 能力测试推理适配器 — YOLOv8n / ONNX 人脸检测。

使用 ONNX Runtime 或 ultralytics 加载已训练模型进行真实推理，
输出符合 detection 任务类型 schema 的结果。
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any


class FaceDetectTestAdapter:
    """YOLOv8n 人脸检测测试推理适配器。"""

    def __init__(self) -> None:
        self._model = None
        self._loaded_path: str | None = None

    def infer(
        self,
        *,
        capability_name: str,
        model_version: str,
        model_artifact_path: str,
        input_path: str,
        task_type: str,
    ) -> dict[str, Any]:
        started = time.perf_counter()

        model = self._load_model(model_artifact_path)
        results = model(input_path, verbose=False)

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

        raw_output: dict[str, Any] = {
            "objects": objects,
            "object_count": len(objects),
            "task_type": task_type,
        }

        return {
            "actual_output": json.dumps({"objects": objects}, ensure_ascii=False),
            "score": round(best_score, 4),
            "raw_output": raw_output,
            "duration_ms": duration_ms,
            "provider": "ultralytics",
            "task_type": task_type,
        }

    def _load_model(self, model_artifact_path: str) -> Any:
        """加载或复用 YOLO 模型。"""
        if self._model is not None and self._loaded_path == model_artifact_path:
            return self._model

        artifact_dir = Path(model_artifact_path)
        # 优先 ONNX，其次 best.pt
        onnx_path = artifact_dir / "face_detect.onnx"
        pt_path = artifact_dir / "best.pt"

        try:
            from ultralytics import YOLO
        except ImportError as exc:
            raise RuntimeError("ultralytics 未安装，无法执行 face_detect 推理") from exc

        if onnx_path.exists():
            self._model = YOLO(str(onnx_path))
        elif pt_path.exists():
            self._model = YOLO(str(pt_path))
        else:
            # 回退到 yolov8n.pt（预训练）
            self._model = YOLO("yolov8n.pt")

        self._loaded_path = model_artifact_path
        return self._model
