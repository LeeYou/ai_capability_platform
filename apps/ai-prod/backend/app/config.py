from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
import os
import platform

from platform_shared.backend.config import resolve_child_path, resolve_database_path, resolve_host_root, resolve_json_map


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
    host_root = resolve_host_root(os.getenv("AI_CAP_HOST_ROOT"))
    data_root = resolve_child_path(host_root, "data")
    database_path = resolve_database_path(
        host_root,
        data_root,
        os.getenv("AI_CAP_DATABASE_PATH"),
        default_name="ai_prod.db",
    )

    logs_root = resolve_child_path(host_root, "logs")
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
        configs_root=resolve_child_path(host_root, "configs"),
        models_root=resolve_child_path(host_root, "models"),
        libs_root=resolve_child_path(host_root, "libs"),
        license_root=resolve_child_path(host_root, "license"),
        exports_root=resolve_child_path(host_root, "exports"),
        database_path=database_path,
        runtime_snapshot_path=resolve_child_path(data_root, "ai_prod_runtime_snapshot.json"),
        runtime_log_path=resolve_child_path(logs_root, "ai_prod_runtime.log"),
        audit_log_path=resolve_child_path(logs_root, "ai_prod_audit.log"),
        image_resource_root=image_resource_root,
        company_name="北京爱知之星科技股份有限公司（Agile Star）",
        company_domain="agilestar.cn",
        service_name="ai-prod",
        service_port=26004,
        pool_size=max(1, int(os.getenv("AI_PROD_POOL_SIZE", "2"))),
        gpu_available=os.getenv("AI_CAP_GPU_AVAILABLE", "1") != "0",
        hardware_features=resolve_json_map(os.getenv("AI_CAP_HARDWARE_FEATURES"), env_name="AI_CAP_HARDWARE_FEATURES"),
        operating_system=detected_operating_system or "linux",
        operating_system_version=detected_operating_system_version,
        system_architecture=detected_system_architecture,
        application_name=os.getenv("AI_CAP_APPLICATION_NAME", "ai-prod").strip() or "ai-prod",
    )
