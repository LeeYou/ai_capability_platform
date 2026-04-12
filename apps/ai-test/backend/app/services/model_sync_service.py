from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen


class ModelCatalogSyncError(ValueError):
    """模型目录同步失败。"""


def _write_snapshot(snapshot_path: Path, payload: dict[str, object]) -> None:
    snapshot_path.parent.mkdir(parents=True, exist_ok=True)
    snapshot_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def read_model_catalog_snapshot(snapshot_path: Path) -> dict[str, object]:
    if not snapshot_path.exists():
        return {"models": [], "capabilities": [], "synced_at": None}
    return json.loads(snapshot_path.read_text(encoding="utf-8"))


def write_model_catalog_snapshot(
    snapshot_path: Path,
    models: list[dict[str, object]],
    capabilities: list[dict[str, object]],
) -> dict[str, object]:
    payload = {
        "models": models,
        "capabilities": capabilities,
        "synced_at": datetime.now(timezone.utc).isoformat(),
    }
    _write_snapshot(snapshot_path, payload)
    return payload


def _fetch_json(url: str) -> dict[str, object]:
    with urlopen(url, timeout=10) as response:
        return json.loads(response.read().decode("utf-8"))


def sync_remote_model_catalog(snapshot_path: Path, ai_train_api_base_url: str) -> dict[str, object]:
    try:
        models_payload = _fetch_json(f"{ai_train_api_base_url}/api/v1/models")
        capabilities_payload = _fetch_json(f"{ai_train_api_base_url}/api/v1/capabilities")
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
