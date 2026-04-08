from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
import json
import os
import platform


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


def _resolve_json_map(raw_value: str | None) -> dict[str, str]:
    if raw_value is None or not raw_value.strip():
        return {}
    payload = json.loads(raw_value)
    if not isinstance(payload, dict):
        raise ValueError("AI_CAP_HARDWARE_FEATURES 必须是 JSON 对象。")
    normalized: dict[str, str] = {}
    for key, value in payload.items():
        key_text = str(key).strip()
        value_text = str(value).strip()
        if key_text and value_text:
            normalized[key_text] = value_text
    return normalized


@dataclass(frozen=True)
class Settings:
    host_root: Path
    data_root: Path
    logs_root: Path
    configs_root: Path
    models_root: Path
    libs_root: Path
    license_root: Path
    exports_root: Path
    database_path: Path
    runtime_snapshot_path: Path
    runtime_log_path: Path
    audit_log_path: Path
    image_resource_root: Path
    company_name: str
    company_domain: str
    service_name: str
    service_port: int
    pool_size: int
    gpu_available: bool
    hardware_features: dict[str, str]
    operating_system: str
    operating_system_version: str
    system_architecture: str
    application_name: str


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
        database_path = data_root / "ai_prod.db"

    logs_root = _resolve_child_path(host_root, "logs")
    image_resource_root = (Path(__file__).resolve().parent / "resources").resolve()
    detected_operating_system = platform.system().strip().lower()
    if detected_operating_system == "darwin":
        detected_operating_system = "ios"
    detected_operating_system = os.getenv("AI_CAP_OPERATING_SYSTEM", detected_operating_system or "linux").strip().lower()
    detected_operating_system_version = os.getenv("AI_CAP_OPERATING_SYSTEM_VERSION", platform.release().strip()).strip()
    detected_system_architecture = os.getenv("AI_CAP_SYSTEM_ARCHITECTURE", platform.machine().strip()).strip().lower()
    return Settings(
        host_root=host_root,
        data_root=data_root,
        logs_root=logs_root,
        configs_root=_resolve_child_path(host_root, "configs"),
        models_root=_resolve_child_path(host_root, "models"),
        libs_root=_resolve_child_path(host_root, "libs"),
        license_root=_resolve_child_path(host_root, "license"),
        exports_root=_resolve_child_path(host_root, "exports"),
        database_path=database_path,
        runtime_snapshot_path=_resolve_child_path(data_root, "ai_prod_runtime_snapshot.json"),
        runtime_log_path=_resolve_child_path(logs_root, "ai_prod_runtime.log"),
        audit_log_path=_resolve_child_path(logs_root, "ai_prod_audit.log"),
        image_resource_root=image_resource_root,
        company_name="北京爱知之星科技股份有限公司（Agile Star）",
        company_domain="agilestar.cn",
        service_name="ai-prod",
        service_port=26004,
        pool_size=max(1, int(os.getenv("AI_PROD_POOL_SIZE", "2"))),
        gpu_available=os.getenv("AI_CAP_GPU_AVAILABLE", "1") != "0",
        hardware_features=_resolve_json_map(os.getenv("AI_CAP_HARDWARE_FEATURES")),
        operating_system=detected_operating_system or "linux",
        operating_system_version=detected_operating_system_version,
        system_architecture=detected_system_architecture,
        application_name=os.getenv("AI_CAP_APPLICATION_NAME", "ai-prod").strip() or "ai-prod",
    )
