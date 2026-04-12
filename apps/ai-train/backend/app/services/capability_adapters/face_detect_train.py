"""face_detect 能力训练适配器 — YOLOv8n 人脸检测训练。

调用 ultralytics YOLO API 执行真实训练，训练完成后导出 ONNX 模型。
数据集需要预先转换为 YOLO 格式并放置在 datasets/face_detect/ 下。
"""
from __future__ import annotations

import json
import shutil
import time
from pathlib import Path
from typing import Any, Callable


class FaceDetectTrainAdapter:
    """YOLOv8n 人脸检测训练适配器。"""

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
        log_callback("[face_detect] 开始 YOLOv8n 人脸检测训练...")

        # ── 参数解析 ──
        epochs = int(train_params.get("epochs", 50))
        batch_size = int(train_params.get("batch_size", 16))
        imgsz = int(train_params.get("imgsz", 640))
        device = str(train_params.get("device", "0"))
        pretrained_weights = str(train_params.get("pretrained_weights", "yolov8n.pt"))
        data_yaml = str(train_params.get("data_yaml", ""))

        # ── 查找数据集配置 ──
        dataset_root = Path(dataset_path)
        if data_yaml and Path(data_yaml).exists():
            data_config_path = Path(data_yaml)
        else:
            # 在数据集目录或 workspace 中寻找 dataset.yaml / face_dataset.yaml
            candidates = [
                dataset_root / "dataset.yaml",
                dataset_root / "face_dataset.yaml",
                dataset_root / "data.yaml",
            ]
            data_config_path = None
            for candidate in candidates:
                if candidate.exists():
                    data_config_path = candidate
                    break
            if data_config_path is None:
                # 自动生成一个默认的 dataset.yaml
                data_config_path = workspace_dir / "face_dataset.yaml"
                self._generate_data_yaml(data_config_path, dataset_root)
                log_callback(f"[face_detect] 未找到 dataset.yaml，已自动生成: {data_config_path}")

        log_callback(f"[face_detect] 数据集配置: {data_config_path}")
        log_callback(f"[face_detect] 训练参数: epochs={epochs}, batch={batch_size}, imgsz={imgsz}, device={device}")

        # ── 执行训练 ──
        try:
            from ultralytics import YOLO
        except ImportError as exc:
            log_callback("[face_detect] 错误: 未安装 ultralytics，请执行 pip install ultralytics")
            raise RuntimeError("ultralytics 未安装") from exc

        project_dir = workspace_dir / "runs"
        project_dir.mkdir(parents=True, exist_ok=True)

        model = YOLO(pretrained_weights)
        start_time = time.time()

        log_callback("[face_detect] 启动 YOLO 训练...")
        results = model.train(
            data=str(data_config_path),
            epochs=epochs,
            batch=batch_size,
            imgsz=imgsz,
            device=device,
            project=str(project_dir),
            name="face_detect",
            exist_ok=True,
            verbose=True,
        )

        train_duration = time.time() - start_time
        log_callback(f"[face_detect] 训练完成，用时 {train_duration:.1f}s")

        # ── 提取训练指标 ──
        metrics = {}
        if results is not None:
            results_dict = results.results_dict if hasattr(results, "results_dict") else {}
            metrics = {
                "mAP50": float(results_dict.get("metrics/mAP50(B)", 0.0)),
                "mAP50-95": float(results_dict.get("metrics/mAP50-95(B)", 0.0)),
                "precision": float(results_dict.get("metrics/precision(B)", 0.0)),
                "recall": float(results_dict.get("metrics/recall(B)", 0.0)),
                "train_duration_seconds": round(train_duration, 1),
            }
        log_callback(f"[face_detect] 训练指标: {json.dumps(metrics, ensure_ascii=False)}")

        # ── 导出 ONNX 模型 ──
        export_dir.mkdir(parents=True, exist_ok=True)
        best_pt = project_dir / "face_detect" / "weights" / "best.pt"
        if best_pt.exists():
            log_callback("[face_detect] 导出 ONNX 模型...")
            best_model = YOLO(str(best_pt))
            onnx_path = best_model.export(format="onnx", imgsz=imgsz)
            if onnx_path and Path(onnx_path).exists():
                shutil.copy2(onnx_path, export_dir / "face_detect.onnx")
                log_callback(f"[face_detect] ONNX 模型已导出: {export_dir / 'face_detect.onnx'}")

            # 同时复制 PyTorch 权重
            shutil.copy2(best_pt, export_dir / "best.pt")
            last_pt = project_dir / "face_detect" / "weights" / "last.pt"
            if last_pt.exists():
                shutil.copy2(last_pt, export_dir / "last.pt")
        else:
            log_callback("[face_detect] 警告: 未找到 best.pt，跳过模型导出")

        # ── 写入 metrics.json ──
        metrics_path = export_dir / "metrics.json"
        metrics_path.write_text(json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8")

        # ── 写入预处理配置 ──
        preprocess = {
            "input_type": "image",
            "resize": {"width": imgsz, "height": imgsz},
            "normalize": {"mean": [0.0, 0.0, 0.0], "std": [1.0, 1.0, 1.0]},
        }
        (export_dir / "preprocess.json").write_text(
            json.dumps(preprocess, ensure_ascii=False, indent=2), encoding="utf-8"
        )

        # ── 写入标签文件 ──
        labels = {"labels": ["face"]}
        (export_dir / "labels.json").write_text(
            json.dumps(labels, ensure_ascii=False, indent=2), encoding="utf-8"
        )

        log_callback("[face_detect] 训练流程全部完成")
        return {
            "status": "completed",
            "capability_name": capability_name,
            "task_type": task_type,
            "framework": "ultralytics",
            "model_type": "yolov8n",
            "metrics": metrics,
            "exported_files": sorted([p.name for p in export_dir.iterdir() if p.is_file()]),
            "train_duration_seconds": round(train_duration, 1),
        }

    @staticmethod
    def _generate_data_yaml(output_path: Path, dataset_root: Path) -> None:
        """自动生成 YOLO 格式的 dataset.yaml。"""
        content = (
            f"path: {dataset_root.resolve()}\n"
            f"train: images/train\n"
            f"val: images/val\n"
            f"\n"
            f"names:\n"
            f"  0: face\n"
        )
        output_path.write_text(content, encoding="utf-8")
