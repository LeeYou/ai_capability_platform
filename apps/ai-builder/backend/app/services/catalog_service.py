from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen


class BuilderCatalogSyncError(ValueError):
    """构建目录同步失败。"""


def _write_snapshot(snapshot_path: Path, payload: dict[str, object]) -> None:
    snapshot_path.parent.mkdir(parents=True, exist_ok=True)
    snapshot_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def read_builder_catalog_snapshot(snapshot_path: Path) -> dict[str, object]:
    if not snapshot_path.exists():
        return {
            "capabilities": [],
            "models": [],
            "license_issues": [],
            "license_policies": [],
            "synced_at": None,
        }
    return json.loads(snapshot_path.read_text(encoding="utf-8"))


def write_builder_catalog_snapshot(
    snapshot_path: Path,
    *,
    capabilities: list[dict[str, object]],
    models: list[dict[str, object]],
    license_issues: list[dict[str, object]],
    license_policies: list[dict[str, object]],
) -> dict[str, object]:
    payload = {
        "capabilities": capabilities,
        "models": models,
        "license_issues": license_issues,
        "license_policies": license_policies,
        "synced_at": datetime.now(timezone.utc).isoformat(),
    }
    _write_snapshot(snapshot_path, payload)
    return payload


def _fetch_json(url: str) -> dict[str, object]:
    with urlopen(url, timeout=10) as response:
        return json.loads(response.read().decode("utf-8"))


def sync_remote_builder_catalog(
    snapshot_path: Path,
    ai_train_api_base_url: str,
    ai_license_mgr_api_base_url: str,
) -> dict[str, object]:
    try:
        capabilities_payload = _fetch_json(f"{ai_train_api_base_url}/api/v1/capabilities")
        models_payload = _fetch_json(f"{ai_train_api_base_url}/api/v1/models")
        license_issues_payload = _fetch_json(f"{ai_license_mgr_api_base_url}/api/v1/license-issues")
        license_policies_payload = _fetch_json(f"{ai_license_mgr_api_base_url}/api/v1/license-policies")
    except (TimeoutError, URLError, ValueError, json.JSONDecodeError) as exc:
        raise BuilderCatalogSyncError("同步 ai-builder 构建目录失败。") from exc

    return write_builder_catalog_snapshot(
        snapshot_path,
        capabilities=capabilities_payload.get("items", []),
        models=models_payload.get("items", []),
        license_issues=license_issues_payload.get("items", []),
        license_policies=license_policies_payload.get("items", []),
    )


def get_builder_catalog(
    snapshot_path: Path,
    ai_train_api_base_url: str,
    ai_license_mgr_api_base_url: str,
) -> dict[str, object]:
    try:
        return sync_remote_builder_catalog(snapshot_path, ai_train_api_base_url, ai_license_mgr_api_base_url)
    except BuilderCatalogSyncError:
        payload = read_builder_catalog_snapshot(snapshot_path)
        if any(payload.get(key) for key in ("capabilities", "models", "license_issues", "license_policies")):
            return payload
        raise
