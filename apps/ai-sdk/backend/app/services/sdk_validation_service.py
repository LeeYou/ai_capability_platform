from __future__ import annotations

from pathlib import Path

from platform_shared.backend import validate_license_tool_release_bundle


def validate_sdk_target_bundle(target_root: Path) -> dict[str, object]:
    base_dir = Path(target_root).resolve()
    required_paths = (
        "lib",
        "include",
        "models",
        "licenses",
        "docs",
        "examples",
        "manifest/manifest.json",
        "checksums.txt",
        "validation/verify_sdk_package.py",
        "tools/license_tool",
    )
    missing = [rel for rel in required_paths if not (base_dir / rel).exists()]
    if missing:
        raise ValueError(f"SDK 目标包缺少必需路径：{missing}")

    validate_license_tool_release_bundle(base_dir / "tools" / "license_tool")

    return {
        "sdk_root": str(base_dir),
        "license_tool_bundle": str((base_dir / "tools" / "license_tool").resolve()),
    }
