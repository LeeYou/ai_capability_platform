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
    license_root: Path
    logs_root: Path
    exports_root: Path
    database_path: Path
    key_pairs_root: Path
    issue_records_root: Path
    license_tools_root: Path
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
        default_name="ai_license_mgr.db",
    )

    license_root = resolve_child_path(host_root, "license")
    logs_root = resolve_child_path(host_root, "logs")
    return Settings(
        host_root=host_root,
        data_root=data_root,
        license_root=license_root,
        logs_root=logs_root,
        exports_root=resolve_child_path(host_root, "exports"),
        database_path=database_path,
        key_pairs_root=resolve_child_path(license_root, "keys"),
        issue_records_root=resolve_child_path(license_root, "issues"),
        license_tools_root=resolve_child_path(license_root, "tools"),
        audit_log_path=resolve_child_path(logs_root, "ai_license_mgr_audit.log"),
        company_name="北京爱知之星科技股份有限公司（Agile Star）",
        company_domain="agilestar.cn",
        service_name="ai-license-mgr",
        service_port=26002,
    )
