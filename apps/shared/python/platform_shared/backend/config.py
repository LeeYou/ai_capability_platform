from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import urlparse

DEFAULT_HOST_ROOT = Path("/data/ai_capability_platform")


def resolve_host_root(raw_value: str | None) -> Path:
    if raw_value is None or not raw_value.strip():
        return DEFAULT_HOST_ROOT

    host_root = Path(raw_value).expanduser()
    if not host_root.is_absolute():
        raise ValueError("AI_CAP_HOST_ROOT 必须使用绝对路径。")
    return host_root.resolve()


def resolve_child_path(parent: Path, child_name: str) -> Path:
    candidate = (parent / child_name).resolve()
    if not (candidate == parent or parent in candidate.parents):
        raise ValueError(f"非法子目录路径：{child_name}")
    return candidate


def resolve_database_path(host_root: Path, data_root: Path, raw_value: str | None, *, default_name: str) -> Path:
    if raw_value and raw_value.strip():
        database_path = Path(raw_value).expanduser()
        if not database_path.is_absolute():
            raise ValueError("AI_CAP_DATABASE_PATH 必须使用绝对路径。")
        database_path = database_path.resolve()
        if not (database_path == host_root or host_root in database_path.parents):
            raise ValueError("AI_CAP_DATABASE_PATH 必须位于宿主机根目录内。")
        return database_path
    return data_root / default_name


def resolve_url(raw_value: str | None, *, default_url: str, env_name: str) -> str:
    base_url = raw_value.strip() if raw_value and raw_value.strip() else default_url
    parsed = urlparse(base_url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError(f"{env_name} 必须是合法的 http/https 地址。")
    return base_url.rstrip("/")


def resolve_json_map(raw_value: str | None, *, env_name: str) -> dict[str, str]:
    if raw_value is None or not raw_value.strip():
        return {}
    payload = json.loads(raw_value)
    if not isinstance(payload, dict):
        raise ValueError(f"{env_name} 必须是 JSON 对象。")
    normalized: dict[str, str] = {}
    for key, value in payload.items():
        key_text = str(key).strip()
        value_text = str(value).strip()
        if key_text and value_text:
            normalized[key_text] = value_text
    return normalized
