from __future__ import annotations

import json
from pathlib import Path
from urllib.error import URLError

from platform_shared.backend.snapshot import build_snapshot_payload, fetch_json, read_json_snapshot, write_json_snapshot


class ModelCatalogSyncError(ValueError):
    """模型目录同步失败。"""


def read_model_catalog_snapshot(snapshot_path: Path) -> dict[str, object]:
    return read_json_snapshot(snapshot_path, default_payload={"models": [], "capabilities": [], "synced_at": None})


def write_model_catalog_snapshot(
    snapshot_path: Path,
    models: list[dict[str, object]],
    capabilities: list[dict[str, object]],
) -> dict[str, object]:
    payload = build_snapshot_payload(models=models, capabilities=capabilities)
    write_json_snapshot(snapshot_path, payload)
    return payload


def sync_remote_model_catalog(snapshot_path: Path, ai_train_api_base_url: str) -> dict[str, object]:
    try:
        models_payload = fetch_json(f"{ai_train_api_base_url}/api/v1/models")
        capabilities_payload = fetch_json(f"{ai_train_api_base_url}/api/v1/capabilities")
    except (TimeoutError, URLError, ValueError, json.JSONDecodeError) as exc:
        raise ModelCatalogSyncError("同步 ai-train 模型目录失败。") from exc

    return write_model_catalog_snapshot(
        snapshot_path=snapshot_path,
        models=models_payload.get("items", []),
        capabilities=capabilities_payload.get("items", []),
    )


def get_model_catalog(snapshot_path: Path, ai_train_api_base_url: str) -> dict[str, object]:
    try:
        return sync_remote_model_catalog(snapshot_path, ai_train_api_base_url)
    except ModelCatalogSyncError:
        payload = read_model_catalog_snapshot(snapshot_path)
        if payload.get("models") or payload.get("capabilities"):
            return payload
        raise
