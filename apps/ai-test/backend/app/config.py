from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from urllib.parse import urlparse
import os


DEFAULT_HOST_ROOT = Path("/data/ai_capability_platform")
DEFAULT_AI_TRAIN_API_BASE_URL = "http://127.0.0.1:26000"


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


def _resolve_ai_train_api_base_url(raw_value: str | None) -> str:
    base_url = raw_value.strip() if raw_value and raw_value.strip() else DEFAULT_AI_TRAIN_API_BASE_URL
    parsed = urlparse(base_url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("AI_TRAIN_API_BASE_URL 必须是合法的 http/https 地址。")
    return base_url.rstrip("/")


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
        database_path = data_root / "ai_test.db"

    return Settings(
        host_root=host_root,
        data_root=data_root,
        datasets_root=_resolve_child_path(host_root, "datasets"),
        models_root=_resolve_child_path(host_root, "models"),
        logs_root=_resolve_child_path(host_root, "logs"),
        exports_root=_resolve_child_path(host_root, "exports"),
        database_path=database_path,
        model_catalog_snapshot_path=_resolve_child_path(data_root, "ai_test_model_catalog.json"),
        test_reports_root=_resolve_child_path(data_root, "test_reports"),
        test_jobs_root=_resolve_child_path(data_root, "test_jobs"),
        ai_train_api_base_url=_resolve_ai_train_api_base_url(os.getenv("AI_TRAIN_API_BASE_URL")),
        company_name="北京爱知之星科技股份有限公司（Agile Star）",
        company_domain="agilestar.cn",
        service_name="ai-test",
        service_port=26001,
    )
