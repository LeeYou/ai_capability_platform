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


def _resolve_child_path(host_root: Path, child_name: str) -> Path:
    candidate = (host_root / child_name).resolve()
    if not (candidate == host_root or host_root in candidate.parents):
        raise ValueError(f"非法子目录路径：{child_name}")
    return candidate


@dataclass(frozen=True)
class Settings:
    host_root: Path
    data_root: Path
    datasets_root: Path
    models_root: Path
    logs_root: Path
    database_path: Path
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
        database_path = data_root / "ai_train.db"

    return Settings(
        host_root=host_root,
        data_root=data_root,
        datasets_root=_resolve_child_path(host_root, "datasets"),
        models_root=_resolve_child_path(host_root, "models"),
        logs_root=_resolve_child_path(host_root, "logs"),
        database_path=database_path,
        company_name="北京爱知之星科技股份有限公司（Agile Star）",
        company_domain="agilestar.cn",
        service_name="ai-train",
        service_port=26000,
    )
