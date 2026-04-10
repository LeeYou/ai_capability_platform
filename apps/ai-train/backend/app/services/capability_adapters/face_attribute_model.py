"""MobileNetV3-Large 多任务人脸属性模型定义。

从 Demo015/src/models/multitask/ 移植，适配平台训练和推理。
支持二分类（glasses, mask, hat, integrity, side_face）、
多分类（expression, head_pose）和回归（age）任务。
"""
from __future__ import annotations

from typing import Any

import torch
import torch.nn as nn
from torchvision import models


class MobileNetV3LargeMultiTask(nn.Module):
    """MobileNetV3-Large 多任务人脸属性网络。"""

    def __init__(self, task_config: dict[str, Any]) -> None:
        super().__init__()
        backbone = models.mobilenet_v3_large(weights=models.MobileNet_V3_Large_Weights.DEFAULT)
        self.features = backbone.features
        self.pool = nn.AdaptiveAvgPool2d(1)
        in_features = 960  # MobileNetV3-Large 最后一层输出通道数

        self.heads = nn.ModuleDict()
        self.task_types: dict[str, str] = {}

        for task_name, task_def in task_config.items():
            task_type = task_def["type"]
            self.task_types[task_name] = task_type

            if task_type == "binary":
                self.heads[task_name] = nn.Linear(in_features, 2)
            elif task_type == "multiclass":
                num_classes = task_def["num_classes"]
                self.heads[task_name] = nn.Linear(in_features, num_classes)
            elif task_type == "regression":
                self.heads[task_name] = nn.Linear(in_features, 1)

    def forward(self, x: torch.Tensor) -> dict[str, torch.Tensor]:
        feat = self.features(x)
        feat = self.pool(feat).flatten(1)
        outputs: dict[str, torch.Tensor] = {}
        for task_name, head in self.heads.items():
            outputs[task_name] = head(feat)
        return outputs


# ── 默认任务配置（与 Demo015 configs/multitask/mobilenetv3_large_multitask.yaml 一致）──

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
