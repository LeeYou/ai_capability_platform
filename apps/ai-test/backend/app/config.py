from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
import os

from platform_shared.backend.config import resolve_child_path, resolve_database_path, resolve_host_root, resolve_url


DEFAULT_AI_TRAIN_API_BASE_URL = "http://127.0.0.1:26000"


@dataclass(frozen=True)
class Settings:
    host_root: Path
    data_root: Path
    datasets_root: Path
    models_root: Path
    logs_root: Path
    exports_root: Path
    database_path: Path
    model_catalog_snapshot_path: Path
    test_reports_root: Path
    test_jobs_root: Path
    ai_train_api_base_url: str
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
        default_name="ai_test.db",
    )

    return Settings(
        host_root=host_root,
        data_root=data_root,
        datasets_root=resolve_child_path(host_root, "datasets"),
        models_root=resolve_child_path(host_root, "models"),
        logs_root=resolve_child_path(host_root, "logs"),
        exports_root=resolve_child_path(host_root, "exports"),
        database_path=database_path,
        model_catalog_snapshot_path=resolve_child_path(data_root, "ai_test_model_catalog.json"),
        test_reports_root=resolve_child_path(data_root, "test_reports"),
        test_jobs_root=resolve_child_path(data_root, "test_jobs"),
        ai_train_api_base_url=resolve_url(
            os.getenv("AI_TRAIN_API_BASE_URL"),
            default_url=DEFAULT_AI_TRAIN_API_BASE_URL,
            env_name="AI_TRAIN_API_BASE_URL",
        ),
        company_name="北京爱知之星科技股份有限公司（Agile Star）",
        company_domain="agilestar.cn",
        service_name="ai-test",
        service_port=26001,
    )
