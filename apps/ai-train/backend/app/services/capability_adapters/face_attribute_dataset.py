"""多任务人脸属性数据集。

从 Demo015/src/data/face_multitask_dataset.py 移植，适配平台训练流程。
支持从 CSV 文件加载人脸裁剪图像及多任务标签。
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import torch
from PIL import Image
from torch.utils.data import Dataset
from torchvision import transforms


class FaceMultiTaskDataset(Dataset):
    """多任务人脸属性数据集。

    CSV 列格式：image_path, glasses, mask, hat, integrity, side_face, expression, head_pose, age
    缺失标签用 -1 或 NaN 表示，训练时通过 mask 机制忽略。
    """

    def __init__(
        self,
        csv_path: str | Path,
        task_config: dict[str, Any],
        image_size: int = 224,
        augment: bool = False,
    ) -> None:
        self.df = pd.read_csv(csv_path)
        self.task_config = task_config
        self.task_names = list(task_config.keys())

        if augment:
            self.transform = transforms.Compose([
                transforms.Resize((image_size, image_size)),
                transforms.RandomHorizontalFlip(),
                transforms.ColorJitter(brightness=0.2, contrast=0.2, saturation=0.2),
                transforms.ToTensor(),
                transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
            ])
        else:
            self.transform = transforms.Compose([
                transforms.Resize((image_size, image_size)),
                transforms.ToTensor(),
                transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
            ])

    def __len__(self) -> int:
        return len(self.df)

    def __getitem__(self, idx: int) -> tuple[torch.Tensor, dict[str, torch.Tensor], dict[str, torch.Tensor]]:
        row = self.df.iloc[idx]
        image_path = str(row["image_path"])
        image = Image.open(image_path).convert("RGB")
        image_tensor = self.transform(image)

        labels: dict[str, torch.Tensor] = {}
        masks: dict[str, torch.Tensor] = {}

        for task_name in self.task_names:
            if task_name not in self.df.columns:
                labels[task_name] = torch.tensor(0, dtype=torch.long)
                masks[task_name] = torch.tensor(0.0, dtype=torch.float32)
                continue

            value = row[task_name]
            if pd.isna(value) or int(value) == -1:
                labels[task_name] = torch.tensor(0, dtype=torch.long)
                masks[task_name] = torch.tensor(0.0, dtype=torch.float32)
            else:
                task_type = self.task_config[task_name]["type"]
                if task_type == "regression":
                    labels[task_name] = torch.tensor(float(value), dtype=torch.float32)
                else:
                    labels[task_name] = torch.tensor(int(value), dtype=torch.long)
                masks[task_name] = torch.tensor(1.0, dtype=torch.float32)

        return image_tensor, labels, masks
