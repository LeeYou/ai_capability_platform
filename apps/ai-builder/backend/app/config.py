from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
import os

from platform_shared.backend.config import resolve_child_path, resolve_database_path, resolve_host_root, resolve_url


DEFAULT_AI_TRAIN_API_BASE_URL = "http://127.0.0.1:26000"
DEFAULT_AI_LICENSE_MGR_API_BASE_URL = "http://127.0.0.1:26002"


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
    build_tasks_root: Path
    build_logs_root: Path
    delivery_packages_root: Path
    build_catalog_snapshot_path: Path
    audit_log_path: Path
    ai_train_api_base_url: str
    ai_license_mgr_api_base_url: str
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
        default_name="ai_builder.db",
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
        build_tasks_root=resolve_child_path(data_root, "build_tasks"),
        build_logs_root=resolve_child_path(logs_root, "builder_tasks"),
        delivery_packages_root=resolve_child_path(resolve_child_path(host_root, "exports"), "delivery_packages"),
        build_catalog_snapshot_path=resolve_child_path(data_root, "ai_builder_catalog.json"),
        audit_log_path=resolve_child_path(logs_root, "ai_builder_audit.log"),
        ai_train_api_base_url=resolve_url(
            os.getenv("AI_TRAIN_API_BASE_URL"),
            default_url=DEFAULT_AI_TRAIN_API_BASE_URL,
            env_name="AI_TRAIN_API_BASE_URL",
        ),
        ai_license_mgr_api_base_url=resolve_url(
            os.getenv("AI_LICENSE_MGR_API_BASE_URL"),
            default_url=DEFAULT_AI_LICENSE_MGR_API_BASE_URL,
            env_name="AI_LICENSE_MGR_API_BASE_URL",
        ),
        company_name="北京爱知之星科技股份有限公司（Agile Star）",
        company_domain="agilestar.cn",
        service_name="ai-builder",
        service_port=26003,
    )
