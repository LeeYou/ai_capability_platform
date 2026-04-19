from __future__ import annotations

import json
from pathlib import Path
from urllib.error import URLError

from platform_shared.backend.snapshot import build_snapshot_payload, fetch_json, read_json_snapshot, write_json_snapshot


class BuilderCatalogSyncError(ValueError):
    """构建目录同步失败。"""


def read_builder_catalog_snapshot(snapshot_path: Path) -> dict[str, object]:
    return read_json_snapshot(snapshot_path, default_payload={"capabilities": [], "models": [], "license_issues": [], "license_policies": [], "synced_at": None})


def write_builder_catalog_snapshot(
    snapshot_path: Path,
    *,
    capabilities: list[dict[str, object]],
    models: list[dict[str, object]],
    license_issues: list[dict[str, object]],
    license_policies: list[dict[str, object]],
) -> dict[str, object]:
    payload = build_snapshot_payload(capabilities=capabilities, models=models, license_issues=license_issues, license_policies=license_policies)
    write_json_snapshot(snapshot_path, payload)
    return payload


def sync_remote_builder_catalog(
    snapshot_path: Path,
    ai_train_api_base_url: str,
    ai_license_mgr_api_base_url: str,
) -> dict[str, object]:
    try:
        capabilities_payload = fetch_json(f"{ai_train_api_base_url}/api/v1/capabilities")
        models_payload = fetch_json(f"{ai_train_api_base_url}/api/v1/models")
        license_issues_payload = fetch_json(f"{ai_license_mgr_api_base_url}/api/v1/license-issues")
        license_policies_payload = fetch_json(f"{ai_license_mgr_api_base_url}/api/v1/license-policies")
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
