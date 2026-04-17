from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil

from sqlalchemy.orm import Session

from platform_shared.backend import validate_license_tool_release_bundle

from app.db.models import LicenseToolReleaseModel
from app.services.license_errors import LicenseToolReleaseNotFoundError
from app.services.audit_service import append_audit_log
from app.services.validation_contracts import DIAGNOSTICS_VERSION, build_validation_contract, build_validation_vectors


LICENSE_TOOL_NAME = "license_tool"
LICENSE_TOOL_VERSION = "1.0.0"
REPO_ROOT = Path(__file__).resolve().parents[5]
LICENSE_TOOL_SOURCE_FILES = {
    "CMakeLists.txt": REPO_ROOT / "apps/shared/license_tool_src/CMakeLists.txt",
    "src/license_tool.cpp": REPO_ROOT / "apps/shared/license_tool_src/src/license_tool.cpp",
    "src/license_common.cpp": REPO_ROOT / "apps/shared/license_tool_src/src/license_common.cpp",
    "src/license_common.h": REPO_ROOT / "apps/shared/license_tool_src/src/license_common.h",
}
LICENSE_TOOL_SUPPORTED_TARGETS = ["linux_x86_64", "linux_aarch64", "windows_x86", "windows_x86_64"]


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8192), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _build_license_tool_release_materials(license_tools_root: Path, *, version: str) -> tuple[Path, Path, Path]:
    release_root = (license_tools_root / f"{LICENSE_TOOL_NAME}_v{version}").resolve()
    if not (release_root == license_tools_root or license_tools_root in release_root.parents):
        raise ValueError("license_tool 发布目录非法。")
    if release_root.exists():
        shutil.rmtree(release_root)
    release_root.mkdir(parents=True, exist_ok=True)

    for relative_path, source_path in LICENSE_TOOL_SOURCE_FILES.items():
        destination = release_root / relative_path
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_path, destination)

    manifest_path = release_root / "manifest.json"
    readme_path = release_root / "README.md"
    error_codes_path = release_root / "ERROR_CODES.md"
    hardware_guide_path = release_root / "HARDWARE_FINGERPRINT.md"
    diagnostics_path = release_root / "LICENSE_DIAGNOSTICS.json"
    validation_vectors_path = release_root / "VALIDATION_VECTORS.json"
    _write_text(release_root / "VERSION", version + "\n")
    _write_text(diagnostics_path, json.dumps(build_validation_contract(), ensure_ascii=False, indent=2, sort_keys=True))
    _write_text(
        validation_vectors_path,
        json.dumps(build_validation_vectors(), ensure_ascii=False, indent=2, sort_keys=True),
    )
    _write_text(
        manifest_path,
        json.dumps(
            {
                "tool_name": LICENSE_TOOL_NAME,
                "version": version,
                "bundle_format": "source_bundle",
                "entrypoint": "src/license_tool.cpp",
                "build_system": "cmake",
                "diagnostics_version": DIAGNOSTICS_VERSION,
                "supported_targets": LICENSE_TOOL_SUPPORTED_TARGETS,
                "source_files": sorted(LICENSE_TOOL_SOURCE_FILES),
                "documents": [
                    "README.md",
                    "ERROR_CODES.md",
                    "HARDWARE_FINGERPRINT.md",
                    "LICENSE_DIAGNOSTICS.json",
                    "VALIDATION_VECTORS.json",
                ],
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        ),
    )

    _write_text(
        readme_path,
        "\n".join(
            [
                "# license_tool",
                "",
                f"- 工具名称：`{LICENSE_TOOL_NAME}`",
                f"- 版本：`{version}`",
                "- 交付形态：标准 C++ source bundle",
                "",
                "## 目录说明",
                "",
                "- `src/`：`license_tool` 与 `license_common` 参考实现源码",
                "- `CMakeLists.txt`：最小 CMake 构建入口",
                "- `ERROR_CODES.md`：退出码说明",
                "- `HARDWARE_FINGERPRINT.md`：硬件指纹采集说明",
                "",
                "## 构建方式",
                "",
                "```bash",
                "cmake -S . -B build",
                "cmake --build build --parallel",
                "```",
                "",
                "## 用法",
                "",
                "```bash",
                "./build/license_tool verify /path/to/license.bin",
                "./build/license_tool generate /path/to/license.bin customer_name capability_a,capability_b --operating-system linux --application-name ai-prod",
                "```",
                "",
                "## 版本兼容性",
                "",
                "- 当前 bundle 已对齐 ai-license-mgr 与 ai-prod 的 license 版本约束语义。",
                "- 授权载荷已支持 `operating_system` / `min_operating_system_version` / `system_architecture` / `application_name` 字段。",
                f"- 当前 bundle 诊断契约版本：`{DIAGNOSTICS_VERSION}`，稳定字段定义见 `LICENSE_DIAGNOSTICS.json`。",
                "- 金标准测试向量见 `VALIDATION_VECTORS.json`，供 runtime / SDK / license_tool 做一致性回归。",
                "- 交付时需配套 `license.bin`、`pubkey.pem` 与本文档一并提供。",
                "",
            ]
        ),
    )
    _write_text(
        error_codes_path,
        "\n".join(
            [
                "# ERROR_CODES",
                "",
                "| 退出码 | 含义 |",
                "| --- | --- |",
                "| 1 | 参数不足或 mode 非法 |",
                "| 2 | generate 参数错误或 bool 选项非法 |",
                "| 3 | 生成 license 文件失败 |",
                "| 4 | 解析 license 文件失败 |",
                "| 5 | 验证 license 失败 |",
                "| 6 | 未知 mode |",
                "",
                "## 稳定诊断 code",
                "",
                "| code | 含义 |",
                "| --- | --- |",
                "| license_valid | 校验通过 |",
                "| signature_invalid | 签名校验失败 |",
                "| time_window_not_started | 尚未生效 |",
                "| time_window_expired | 已过期 |",
                "| hardware_fingerprint_mismatch | 硬件指纹不匹配 |",
                "| capability_scope_denied | 能力范围不匹配 |",
                "| version_constraints_denied | 版本约束不匹配 |",
                "| operating_system_denied | 操作系统不匹配 |",
                "| operating_system_version_denied | 系统版本低于 license 最低要求 |",
                "| system_architecture_denied | 系统架构不匹配 |",
                "",
            ]
        ),
    )
    _write_text(
        hardware_guide_path,
        "\n".join(
            [
                "# HARDWARE_FINGERPRINT",
                "",
                "硬件指纹用于绑定部署机器，当前以多特征组合哈希实现。",
                "",
                "## 建议采集字段",
                "",
                "- cpu 型号",
                "- 磁盘序列号",
                "- mac 地址",
                "",
            ]
        ),
    )

    validate_license_tool_release_bundle(release_root)

    archive_path = (license_tools_root / f"{LICENSE_TOOL_NAME}_v{version}.tar.gz").resolve()
    if not (archive_path == license_tools_root or license_tools_root in archive_path.parents):
        raise ValueError("license_tool 归档路径非法。")
    if archive_path.exists():
        archive_path.unlink()
    shutil.make_archive(
        str(archive_path.with_suffix("")),
        "gztar",
        root_dir=str(release_root),
    )
    if not archive_path.is_file():
        raise ValueError("license_tool 归档生成失败。")
    return archive_path.resolve(), manifest_path.resolve(), readme_path.resolve()


def list_license_tool_releases(session: Session) -> list[dict[str, object]]:
    return [
        {
            "release_id": item.id,
            "tool_name": item.tool_name,
            "version": item.version,
            "status": item.status,
            "archive_path": item.archive_path,
            "manifest_path": item.manifest_path,
            "readme_path": item.readme_path,
            "checksum_sha256": item.checksum_sha256,
        }
        for item in session.query(LicenseToolReleaseModel).order_by(LicenseToolReleaseModel.id.asc()).all()
    ]


def get_license_tool_release(session: Session, release_id: int) -> dict[str, object]:
    release = session.get(LicenseToolReleaseModel, release_id)
    if release is None:
        raise LicenseToolReleaseNotFoundError("工具发布记录不存在。")
    return {
        "release_id": release.id,
        "tool_name": release.tool_name,
        "version": release.version,
        "status": release.status,
        "archive_path": release.archive_path,
        "manifest_path": release.manifest_path,
        "readme_path": release.readme_path,
        "checksum_sha256": release.checksum_sha256,
    }


def sync_default_license_tool_release(
    session: Session,
    license_tools_root: Path,
    audit_log_path: Path,
) -> dict[str, object]:
    archive_path, manifest_path, readme_path = _build_license_tool_release_materials(
        license_tools_root,
        version=LICENSE_TOOL_VERSION,
    )
    checksum_sha256 = _sha256_file(archive_path)
    release = (
        session.query(LicenseToolReleaseModel)
        .filter(
            LicenseToolReleaseModel.tool_name == LICENSE_TOOL_NAME,
            LicenseToolReleaseModel.version == LICENSE_TOOL_VERSION,
        )
        .first()
    )
    if release is None:
        release = LicenseToolReleaseModel(
            tool_name=LICENSE_TOOL_NAME,
            version=LICENSE_TOOL_VERSION,
            status="active",
            archive_path=str(archive_path),
            manifest_path=str(manifest_path),
            readme_path=str(readme_path),
            checksum_sha256=checksum_sha256,
        )
        session.add(release)
    else:
        release.status = "active"
        release.archive_path = str(archive_path)
        release.manifest_path = str(manifest_path)
        release.readme_path = str(readme_path)
        release.checksum_sha256 = checksum_sha256
    session.commit()
    session.refresh(release)
    append_audit_log(
        audit_log_path,
        action="sync",
        entity_type="license_tool_release",
        entity_id=str(release.id),
        detail={"tool_name": release.tool_name, "version": release.version},
    )
    return get_license_tool_release(session, int(release.id))


def export_license_tool_release(
    session: Session,
    exports_root: Path,
    audit_log_path: Path,
    *,
    release_id: int,
    export_format: str,
) -> Path:
    release = session.get(LicenseToolReleaseModel, release_id)
    if release is None:
        raise LicenseToolReleaseNotFoundError("工具发布记录不存在。")
    source_map = {
        "archive": Path(release.archive_path),
        "manifest": Path(release.manifest_path),
        "readme": Path(release.readme_path),
        "diagnostics": Path(release.manifest_path).with_name("LICENSE_DIAGNOSTICS.json"),
        "vectors": Path(release.manifest_path).with_name("VALIDATION_VECTORS.json"),
    }
    if export_format not in source_map:
        raise ValueError("仅支持导出 archive/manifest/readme/diagnostics/vectors。")

    export_dir = (exports_root / "ai-license-mgr").resolve()
    if not (export_dir == exports_root or exports_root in export_dir.parents):
        raise ValueError("导出目录非法。")
    export_dir.mkdir(parents=True, exist_ok=True)

    source_path = source_map[export_format]
    suffix = (
        f"license_tool_v{release.version}.tar.gz"
        if export_format == "archive"
        else f"license_tool_v{release.version}_{source_path.name}"
    )
    destination = export_dir / suffix
    shutil.copyfile(source_path, destination)
    append_audit_log(
        audit_log_path,
        action="export",
        entity_type="license_tool_release",
        entity_id=str(release.id),
        detail={"export_format": export_format, "exported_path": str(destination.resolve())},
    )
    return destination.resolve()
