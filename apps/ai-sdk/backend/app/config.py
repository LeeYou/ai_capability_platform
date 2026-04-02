from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
import os


DEFAULT_HOST_ROOT = Path("/data/ai_capability_platform")


def _resolve_host_root(raw_value: str | None) -> Path:
    if raw_value is None or not raw_value.strip():
        return DEFAULT_HOST_ROOT

    host_root = Path(raw_value).expanduser()
    if not host_root.is_absolute():
        raise ValueError("AI_CAP_HOST_ROOT 必须使用绝对路径。")
    return host_root.resolve()


def _resolve_child_path(parent: Path, child_name: str) -> Path:
    candidate = (parent / child_name).resolve()
    if not (candidate == parent or parent in candidate.parents):
        raise ValueError(f"非法子目录路径：{child_name}")
    return candidate


@dataclass(frozen=True)
class Settings:
    host_root: Path
    data_root: Path
    logs_root: Path
    exports_root: Path
    libs_root: Path
    models_root: Path
    license_root: Path
    database_path: Path
    sdk_packages_root: Path
    sdk_logs_root: Path
    audit_log_path: Path
    company_name: str
    company_domain: str
    service_name: str
    service_port: int


def reset_settings_cache() -> None:
    get_settings.cache_clear()


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    host_root = _resolve_host_root(os.getenv("AI_CAP_HOST_ROOT"))
    data_root = _resolve_child_path(host_root, "data")
    database_override = os.getenv("AI_CAP_DATABASE_PATH")
    if database_override:
        database_path = Path(database_override).expanduser()
        if not database_path.is_absolute():
            raise ValueError("AI_CAP_DATABASE_PATH 必须使用绝对路径。")
        database_path = database_path.resolve()
        if not (database_path == host_root or host_root in database_path.parents):
            raise ValueError("AI_CAP_DATABASE_PATH 必须位于宿主机根目录内。")
    else:
        database_path = data_root / "ai_sdk.db"

    logs_root = _resolve_child_path(host_root, "logs")
    return Settings(
        host_root=host_root,
        data_root=data_root,
        logs_root=logs_root,
        exports_root=_resolve_child_path(host_root, "exports"),
        libs_root=_resolve_child_path(host_root, "libs"),
        models_root=_resolve_child_path(host_root, "models"),
        license_root=_resolve_child_path(host_root, "license"),
        database_path=database_path,
        sdk_packages_root=_resolve_child_path(data_root, "sdk_packages"),
        sdk_logs_root=_resolve_child_path(logs_root, "sdk_packages"),
        audit_log_path=_resolve_child_path(logs_root, "ai_sdk_audit.log"),
        company_name="北京爱知之星科技股份有限公司（Agile Star）",
        company_domain="agilestar.cn",
        service_name="ai-sdk",
        service_port=26005,
    )
