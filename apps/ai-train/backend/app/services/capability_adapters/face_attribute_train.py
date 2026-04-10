"""face_attribute 能力训练适配器 — MobileNetV3-Large 多任务人脸属性训练。

调用内嵌的 MobileNetV3LargeMultiTask 模型执行真实训练，训练完成后导出 ONNX 模型。
数据集需要预先生成 CSV 格式并放置在 datasets/face_attribute/ 下。
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Callable

import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import DataLoader

from app.services.capability_adapters.face_attribute_model import (
    DEFAULT_TASK_CONFIG,
    MobileNetV3LargeMultiTask,
)
from app.services.capability_adapters.face_attribute_dataset import FaceMultiTaskDataset


# ── 默认损失权重 ──

DEFAULT_LOSS_WEIGHTS: dict[str, float] = {
    "glasses": 1.0,
    "mask": 1.0,
    "hat": 1.0,
    "integrity": 1.0,
    "side_face": 1.0,
    "expression": 1.0,
    "head_pose": 1.0,
    "age": 0.01,
}


class FaceAttributeTrainAdapter:
    """MobileNetV3-Large 多任务人脸属性训练适配器。"""

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
        log_callback("[face_attribute] 开始 MobileNetV3-Large 多任务训练...")

        # ── 参数解析 ──
        epochs = int(train_params.get("epochs", 30))
        batch_size = int(train_params.get("batch_size", 32))
        lr = float(train_params.get("learning_rate", 1e-3))
        image_size = int(train_params.get("image_size", 224))
        device_str = str(train_params.get("device", "auto"))
        train_csv = str(train_params.get("train_csv", ""))
        val_csv = str(train_params.get("val_csv", ""))

        # 任务配置
        task_config = train_params.get("task_config", None) or DEFAULT_TASK_CONFIG
        loss_weights = train_params.get("loss_weights", None) or DEFAULT_LOSS_WEIGHTS

        # ── 确定设备 ──
        if device_str == "auto":
            device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        else:
            device = torch.device(device_str)
        log_callback(f"[face_attribute] 训练设备: {device}")

        # ── 查找数据集 CSV ──
        dataset_root = Path(dataset_path)
        if not train_csv or not Path(train_csv).exists():
            candidates = [dataset_root / "train.csv", dataset_root / "train_labels.csv"]
            for c in candidates:
                if c.exists():
                    train_csv = str(c)
                    break
        if not val_csv or not Path(val_csv).exists():
            candidates = [dataset_root / "val.csv", dataset_root / "val_labels.csv"]
            for c in candidates:
                if c.exists():
                    val_csv = str(c)
                    break

        if not train_csv or not Path(train_csv).exists():
            raise RuntimeError(f"未找到训练 CSV 文件，请在 {dataset_root} 下放置 train.csv")
        log_callback(f"[face_attribute] 训练集: {train_csv}")
        if val_csv and Path(val_csv).exists():
            log_callback(f"[face_attribute] 验证集: {val_csv}")

        # ── 构建数据集和模型 ──
        train_dataset = FaceMultiTaskDataset(train_csv, task_config, image_size=image_size, augment=True)
        train_loader = DataLoader(train_dataset, batch_size=batch_size, shuffle=True, num_workers=0, drop_last=True)

        val_loader = None
        if val_csv and Path(val_csv).exists():
            val_dataset = FaceMultiTaskDataset(val_csv, task_config, image_size=image_size, augment=False)
            val_loader = DataLoader(val_dataset, batch_size=batch_size, shuffle=False, num_workers=0)

        log_callback(f"[face_attribute] 训练样本数: {len(train_dataset)}")

        model = MobileNetV3LargeMultiTask(task_config).to(device)
        optimizer = torch.optim.Adam(model.parameters(), lr=lr)
        scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=epochs)

        ce_loss_fn = nn.CrossEntropyLoss(reduction="none")
        mse_loss_fn = nn.MSELoss(reduction="none")

        # ── 训练循环 ──
        start_time = time.time()
        best_val_loss = float("inf")
        history: list[dict[str, Any]] = []

        for epoch in range(1, epochs + 1):
            model.train()
            epoch_losses: dict[str, list[float]] = {name: [] for name in task_config}
            total_loss_values: list[float] = []

            for images, labels_batch, masks_batch in train_loader:
                images = images.to(device)
                outputs = model(images)
                total_loss = torch.tensor(0.0, device=device)

                for task_name in task_config:
                    pred = outputs[task_name]
                    label = labels_batch[task_name].to(device)
                    mask = masks_batch[task_name].to(device)
                    weight = loss_weights.get(task_name, 1.0)

                    if task_config[task_name]["type"] == "regression":
                        loss_per_sample = mse_loss_fn(pred.squeeze(-1), label.float())
                    else:
                        loss_per_sample = ce_loss_fn(pred, label)

                    masked_loss = (loss_per_sample * mask).sum() / (mask.sum() + 1e-8)
                    total_loss = total_loss + masked_loss * weight
                    epoch_losses[task_name].append(masked_loss.item())

                optimizer.zero_grad()
                total_loss.backward()
                optimizer.step()
                total_loss_values.append(total_loss.item())

            scheduler.step()

            # 记录 epoch 指标
            epoch_avg_loss = float(np.mean(total_loss_values))
            task_avg = {name: float(np.mean(vals)) if vals else 0.0 for name, vals in epoch_losses.items()}
            epoch_record = {"epoch": epoch, "total_loss": round(epoch_avg_loss, 4), "task_losses": task_avg}

            # ── 验证 ──
            val_loss = None
            if val_loader is not None:
                val_loss = self._validate(model, val_loader, task_config, loss_weights, device)
                epoch_record["val_loss"] = round(val_loss, 4)

            history.append(epoch_record)
            log_callback(f"[face_attribute] Epoch {epoch}/{epochs} - loss: {epoch_avg_loss:.4f}"
                         + (f" - val_loss: {val_loss:.4f}" if val_loss is not None else ""))

            # 保存最佳模型
            current_target = val_loss if val_loss is not None else epoch_avg_loss
            if current_target < best_val_loss:
                best_val_loss = current_target
                export_dir.mkdir(parents=True, exist_ok=True)
                torch.save(model.state_dict(), export_dir / "best.pth")

        train_duration = time.time() - start_time
        log_callback(f"[face_attribute] 训练完成，用时 {train_duration:.1f}s")

        # ── 保存最终模型 ──
        export_dir.mkdir(parents=True, exist_ok=True)
        torch.save(model.state_dict(), export_dir / "last.pth")

        # ── 导出 ONNX ──
        self._export_onnx(model, export_dir, image_size, device, log_callback)

        # ── 写入 metrics.json ──
        final_metrics = {
            "best_val_loss": round(best_val_loss, 4),
            "final_train_loss": round(history[-1]["total_loss"], 4) if history else 0.0,
            "train_duration_seconds": round(train_duration, 1),
            "epochs_trained": epochs,
            "history": history,
        }
        (export_dir / "metrics.json").write_text(
            json.dumps(final_metrics, ensure_ascii=False, indent=2), encoding="utf-8"
        )

        # ── 写入预处理配置 ──
        preprocess = {
            "input_type": "image",
            "resize": {"width": image_size, "height": image_size},
            "normalize": {"mean": [0.485, 0.456, 0.406], "std": [0.229, 0.224, 0.225]},
        }
        (export_dir / "preprocess.json").write_text(
            json.dumps(preprocess, ensure_ascii=False, indent=2), encoding="utf-8"
        )

        # ── 写入标签文件 ──
        labels_data: dict[str, Any] = {"labels": list(task_config.keys()), "task_config": task_config}
        (export_dir / "labels.json").write_text(
            json.dumps(labels_data, ensure_ascii=False, indent=2), encoding="utf-8"
        )

        log_callback("[face_attribute] 训练流程全部完成")
        return {
            "status": "completed",
            "capability_name": capability_name,
            "task_type": task_type,
            "framework": "pytorch",
            "model_type": "mobilenetv3_large_multitask",
            "metrics": {
                "best_val_loss": round(best_val_loss, 4),
                "final_train_loss": round(history[-1]["total_loss"], 4) if history else 0.0,
                "train_duration_seconds": round(train_duration, 1),
            },
            "exported_files": sorted([p.name for p in export_dir.iterdir() if p.is_file()]),
            "train_duration_seconds": round(train_duration, 1),
        }

    @staticmethod
    def _validate(
        model: nn.Module,
        val_loader: DataLoader,
        task_config: dict[str, Any],
        loss_weights: dict[str, float],
        device: torch.device,
    ) -> float:
        model.eval()
        ce_loss_fn = nn.CrossEntropyLoss(reduction="none")
        mse_loss_fn = nn.MSELoss(reduction="none")
        total_losses: list[float] = []

        with torch.no_grad():
            for images, labels_batch, masks_batch in val_loader:
                images = images.to(device)
                outputs = model(images)
                batch_loss = torch.tensor(0.0, device=device)

                for task_name in task_config:
                    pred = outputs[task_name]
                    label = labels_batch[task_name].to(device)
                    mask = masks_batch[task_name].to(device)
                    weight = loss_weights.get(task_name, 1.0)

                    if task_config[task_name]["type"] == "regression":
                        loss_per_sample = mse_loss_fn(pred.squeeze(-1), label.float())
                    else:
                        loss_per_sample = ce_loss_fn(pred, label)

                    masked_loss = (loss_per_sample * mask).sum() / (mask.sum() + 1e-8)
                    batch_loss = batch_loss + masked_loss * weight

                total_losses.append(batch_loss.item())

        model.train()
        return float(np.mean(total_losses)) if total_losses else 0.0

    @staticmethod
    def _export_onnx(
        model: nn.Module,
        export_dir: Path,
        image_size: int,
        device: torch.device,
        log_callback: Callable[[str], None],
    ) -> None:
        try:
            model.eval()
            dummy_input = torch.randn(1, 3, image_size, image_size, device=device)
            onnx_path = export_dir / "face_attribute.onnx"
            output_names = list(model.heads.keys())

            torch.onnx.export(
                model,
                dummy_input,
                str(onnx_path),
                input_names=["input"],
                output_names=output_names,
                dynamic_axes={"input": {0: "batch_size"}},
                opset_version=13,
            )
            log_callback(f"[face_attribute] ONNX 模型已导出: {onnx_path}")
        except Exception as exc:
            log_callback(f"[face_attribute] ONNX 导出失败: {exc}")
