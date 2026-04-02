from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from pathlib import PurePosixPath


@dataclass(frozen=True)
class DatasetBinding:
    capability_name: str
    display_name: str
    dataset_path: str
    dataset_status: str
    source: str


def _to_display_name(capability_name: str) -> str:
    words = capability_name.replace("-", "_").split("_")
    return " ".join(part.capitalize() for part in words if part)


def scan_dataset_bindings(datasets_root: Path) -> list[DatasetBinding]:
    if not datasets_root.exists() or not datasets_root.is_dir():
        return []

    bindings: list[DatasetBinding] = []
    for entry in sorted(datasets_root.iterdir(), key=lambda item: item.name):
        if not entry.is_dir():
            continue
        bindings.append(
            DatasetBinding(
                capability_name=entry.name,
                display_name=_to_display_name(entry.name),
                dataset_path=str(entry.resolve()),
                dataset_status="ready",
                source="datasets_root",
            )
        )
    return bindings


def normalize_dataset_path(datasets_root: Path, dataset_path: str) -> Path:
    normalized_input = dataset_path.strip()
    if not normalized_input:
        raise ValueError("dataset_path 不能为空。")

    raw_path = PurePosixPath(normalized_input.replace("\\", "/"))
    if raw_path.is_absolute():
        raise ValueError("dataset_path 仅支持相对路径。")
    if any(part in {"", ".", ".."} for part in raw_path.parts):
        raise ValueError("dataset_path 包含非法路径片段。")

    candidate = datasets_root.joinpath(*raw_path.parts)
    candidate = candidate.resolve()
    if not (candidate == datasets_root or datasets_root in candidate.parents):
        raise ValueError("dataset_path 必须位于 datasets 根目录内。")
    return candidate
