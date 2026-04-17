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
    datasets_root: Path
    models_root: Path
    logs_root: Path
    database_path: Path
    annotation_tasks_root: Path
    training_logs_root: Path
    training_jobs_root: Path
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
        default_name="ai_train.db",
    )

    return Settings(
        host_root=host_root,
        data_root=data_root,
        datasets_root=resolve_child_path(host_root, "datasets"),
        models_root=resolve_child_path(host_root, "models"),
        logs_root=resolve_child_path(host_root, "logs"),
        database_path=database_path,
        annotation_tasks_root=resolve_child_path(data_root, "annotation_tasks"),
        training_logs_root=resolve_child_path(resolve_child_path(host_root, "logs"), "training_tasks"),
        training_jobs_root=resolve_child_path(data_root, "training_jobs"),
        company_name="北京爱知之星科技股份有限公司（Agile Star）",
        company_domain="agilestar.cn",
        service_name="ai-train",
        service_port=26000,
    )
