from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
import os

from platform_shared.backend.config import resolve_child_path, resolve_database_path, resolve_host_root


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
    host_root = resolve_host_root(os.getenv("AI_CAP_HOST_ROOT"))
    data_root = resolve_child_path(host_root, "data")
    database_path = resolve_database_path(
        host_root,
        data_root,
        os.getenv("AI_CAP_DATABASE_PATH"),
        default_name="ai_sdk.db",
    )

    logs_root = resolve_child_path(host_root, "logs")
    return Settings(
        host_root=host_root,
        data_root=data_root,
        logs_root=logs_root,
        exports_root=resolve_child_path(host_root, "exports"),
        libs_root=resolve_child_path(host_root, "libs"),
        models_root=resolve_child_path(host_root, "models"),
        license_root=resolve_child_path(host_root, "license"),
        database_path=database_path,
        sdk_packages_root=resolve_child_path(data_root, "sdk_packages"),
        sdk_logs_root=resolve_child_path(logs_root, "sdk_packages"),
        audit_log_path=resolve_child_path(logs_root, "ai_sdk_audit.log"),
        company_name="北京爱知之星科技股份有限公司（Agile Star）",
        company_domain="agilestar.cn",
        service_name="ai-sdk",
        service_port=26005,
    )
