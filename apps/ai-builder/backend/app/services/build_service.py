from __future__ import annotations

from datetime import UTC, datetime
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
from typing import Any

from sqlalchemy.orm import Session

from app.db.models import BuildArtifactModel, BuildManifestModel, BuildTargetModel, BuildTaskModel
from app.services.audit_service import append_audit_log
from app.services.catalog_service import get_builder_catalog


SUPPORTED_TARGETS: dict[str, dict[str, object]] = {
    "linux_x86_64": {
        "os_name": "linux",
        "arch_name": "x86_64",
        "artifact_format": "so",
        "toolchain_name": "cmake-native",
        "supports_native_build": True,
        "supports_jni": True,
        "build_mode": "native",
    },
    "linux_arm64": {
        "os_name": "linux",
        "arch_name": "arm64",
        "artifact_format": "so",
        "toolchain_name": "cmake-cross-template",
        "supports_native_build": False,
        "supports_jni": True,
        "build_mode": "template",
    },
    "windows_x86": {
        "os_name": "windows",
        "arch_name": "x86",
        "artifact_format": "dll",
        "toolchain_name": "cmake-mingw-template",
        "supports_native_build": False,
        "supports_jni": True,
        "build_mode": "template",
    },
    "windows_x86_64": {
        "os_name": "windows",
        "arch_name": "x86_64",
        "artifact_format": "dll",
        "toolchain_name": "cmake-mingw-template",
        "supports_native_build": False,
        "supports_jni": True,
        "build_mode": "template",
    },
}


class BuildTaskNotFoundError(ValueError):
    """构建任务不存在。"""


class BuildTargetNotFoundError(ValueError):
    """构建目标不存在。"""


def initialize_database() -> None:
    from app.db.database import Base, get_engine
    from app.db import models  # noqa: F401

    Base.metadata.create_all(bind=get_engine())


def _normalize_slug(raw_value: str, *, field_name: str) -> str:
    normalized = raw_value.strip()
    if not normalized:
        raise ValueError(f"{field_name} 不能为空。")
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_\-]{0,127}", normalized):
        raise ValueError(f"{field_name} 仅支持字母、数字、下划线与中划线。")
    return normalized


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8192), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _append_log(path: Path, message: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(message.rstrip() + "\n")


def _platform_item(target_name: str) -> dict[str, object]:
    payload = SUPPORTED_TARGETS[target_name]
    return {
        "target_name": target_name,
        "os_name": payload["os_name"],
        "arch_name": payload["arch_name"],
        "artifact_format": payload["artifact_format"],
        "toolchain_name": payload["toolchain_name"],
        "supports_native_build": payload["supports_native_build"],
        "supports_jni": payload["supports_jni"],
    }


def list_platform_targets() -> list[dict[str, object]]:
    return [_platform_item(name) for name in SUPPORTED_TARGETS]


def _task_item(task: BuildTaskModel) -> dict[str, object]:
    return {
        "task_id": task.id,
        "task_name": task.task_name,
        "capability_name": task.capability_name,
        "model_version": task.model_version,
        "issue_record_id": task.issue_record_id,
        "requested_targets": json.loads(task.requested_targets_json),
        "jni_enabled": task.jni_enabled,
        "status": task.status,
        "build_root_path": task.build_root_path,
        "log_path": task.log_path,
        "manifest_path": task.manifest_path,
        "started_at": task.started_at.isoformat() if task.started_at else None,
        "completed_at": task.completed_at.isoformat() if task.completed_at else None,
    }


def _target_item(target: BuildTargetModel) -> dict[str, object]:
    return {
        "target_id": target.id,
        "task_id": target.task_id,
        "target_name": target.target_name,
        "os_name": target.os_name,
        "arch_name": target.arch_name,
        "artifact_format": target.artifact_format,
        "build_mode": target.build_mode,
        "toolchain_name": target.toolchain_name,
        "jni_enabled": target.jni_enabled,
        "status": target.status,
        "output_dir": target.output_dir,
        "binary_path": target.binary_path,
        "header_dir": target.header_dir,
        "manifest_path": target.manifest_path,
        "checksum": target.checksum,
        "log_path": target.log_path,
        "download_archive_path": target.download_archive_path,
    }


def _artifact_item(artifact: BuildArtifactModel) -> dict[str, object]:
    return {
        "artifact_id": artifact.id,
        "task_id": artifact.task_id,
        "target_id": artifact.target_id,
        "artifact_type": artifact.artifact_type,
        "relative_path": artifact.relative_path,
        "absolute_path": artifact.absolute_path,
        "checksum": artifact.checksum,
    }


def _manifest_item(manifest: BuildManifestModel) -> dict[str, object]:
    return {
        "manifest_id": manifest.id,
        "task_id": manifest.task_id,
        "manifest_version": manifest.manifest_version,
        "manifest_path": manifest.manifest_path,
        "dependency_summary": json.loads(manifest.dependency_summary_json),
        "manifest": json.loads(manifest.manifest_json),
    }


def _render_header(capability_name: str) -> str:
    upper_name = capability_name.upper()
    return f"""#pragma once

#ifdef __cplusplus
extern "C" {{
#endif

#define AI_BUILDER_ABI_VERSION 1

int ai_builder_get_abi_version(void);
const char* ai_builder_get_capability_name(void);
const char* ai_builder_get_model_version(void);
int {capability_name}_predict(const char* input_json, char* output_buffer, unsigned int output_buffer_size);

#ifdef __cplusplus
}}
#endif
"""


def _render_source(capability_name: str, model_version: str) -> str:
    return f"""#include \"{capability_name}.h\"

#include <cstring>
#include <string>

namespace {{
constexpr const char* kCapabilityName = \"{capability_name}\";
constexpr const char* kModelVersion = \"{model_version}\";
}}

int ai_builder_get_abi_version(void) {{
  return AI_BUILDER_ABI_VERSION;
}}

const char* ai_builder_get_capability_name(void) {{
  return kCapabilityName;
}}

const char* ai_builder_get_model_version(void) {{
  return kModelVersion;
}}

int {capability_name}_predict(const char* input_json, char* output_buffer, unsigned int output_buffer_size) {{
  if (input_json == nullptr || output_buffer == nullptr || output_buffer_size == 0) {{
    return -1;
  }}

  std::string result = std::string("{{\\\"capability\\\":\\\"") + kCapabilityName +
                       "\\\",\\\"model_version\\\":\\\"" + kModelVersion +
                       "\\\",\\\"input\\\":" + input_json + "}}";
  if (result.size() + 1 > output_buffer_size) {{
    return -2;
  }}
  std::memcpy(output_buffer, result.c_str(), result.size() + 1);
  return 0;
}}
"""


def _render_jni_source(capability_name: str) -> str:
    return f"""#include <cstddef>

extern "C" int Java_cn_agilestar_ai_{capability_name}_NativeBridge_ping() {{
  return 1;
}}
"""


def _render_cmakelists(capability_name: str, jni_enabled: bool) -> str:
    jni_part = ""
    if jni_enabled:
        jni_part = f"""
add_library({capability_name}_jni SHARED jni/{capability_name}_jni.cpp)
set_target_properties({capability_name}_jni PROPERTIES OUTPUT_NAME "{capability_name}_jni")
install(TARGETS {capability_name}_jni
  LIBRARY DESTINATION jni
  RUNTIME DESTINATION jni
  ARCHIVE DESTINATION jni
)
"""
    return f"""cmake_minimum_required(VERSION 3.18)
project({capability_name} LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

add_library({capability_name} SHARED src/{capability_name}.cpp)
target_include_directories({capability_name} PUBLIC ${{CMAKE_CURRENT_SOURCE_DIR}}/include)
set_target_properties({capability_name} PROPERTIES OUTPUT_NAME "{capability_name}")

install(TARGETS {capability_name}
  LIBRARY DESTINATION lib
  RUNTIME DESTINATION lib
  ARCHIVE DESTINATION lib
)
install(DIRECTORY include/ DESTINATION include)
{jni_part}
"""


def _render_toolchain_template(target_name: str) -> str:
    target = SUPPORTED_TARGETS[target_name]
    return f"""# {target_name} 工具链模板
set(CMAKE_SYSTEM_NAME {target['os_name'].capitalize() if target['os_name'] != 'linux' else 'Linux'})
set(CMAKE_SYSTEM_PROCESSOR {target['arch_name']})

# 首期仅输出模板文件，后续在具备交叉编译环境时替换实际编译器路径。
"""


def _build_native_linux(source_dir: Path, build_dir: Path, install_dir: Path, log_path: Path) -> None:
    for command in (
        [
            "cmake",
            "-S",
            str(source_dir),
            "-B",
            str(build_dir),
            f"-DCMAKE_INSTALL_PREFIX={install_dir}",
        ],
        ["cmake", "--build", str(build_dir), "--config", "Release"],
        ["cmake", "--install", str(build_dir)],
    ):
        result = subprocess.run(
            command,
            check=True,
            text=True,
            capture_output=True,
        )
        _append_log(log_path, "$ " + " ".join(command))
        if result.stdout.strip():
            _append_log(log_path, result.stdout.strip())
        if result.stderr.strip():
            _append_log(log_path, result.stderr.strip())


def _write_template_binary(path: Path, payload: dict[str, object]) -> None:
    _write_text(path, json.dumps(payload, ensure_ascii=False, indent=2))


def _archive_directory(source_dir: Path, destination_without_suffix: Path) -> Path:
    destination_without_suffix.parent.mkdir(parents=True, exist_ok=True)
    archive_path = shutil.make_archive(str(destination_without_suffix), "zip", root_dir=source_dir)
    return Path(archive_path).resolve()


def _register_artifact(
    session: Session,
    *,
    task_id: int,
    target_id: int,
    artifact_type: str,
    output_dir: Path,
    absolute_path: Path,
) -> None:
    try:
        relative_path = str(absolute_path.resolve().relative_to(output_dir.resolve()))
    except ValueError:
        relative_path = str(absolute_path.resolve())
    session.add(
        BuildArtifactModel(
            task_id=task_id,
            target_id=target_id,
            artifact_type=artifact_type,
            relative_path=relative_path,
            absolute_path=str(absolute_path.resolve()),
            checksum=_sha256_file(absolute_path) if absolute_path.is_file() else hashlib.sha256(str(absolute_path).encode("utf-8")).hexdigest(),
        )
    )


def create_build_task(
    session: Session,
    *,
    build_catalog_snapshot_path: Path,
    ai_train_api_base_url: str,
    ai_license_mgr_api_base_url: str,
    build_tasks_root: Path,
    build_logs_root: Path,
    libs_root: Path,
    exports_root: Path,
    audit_log_path: Path,
    task_name: str,
    capability_name: str,
    model_version: str,
    issue_record_id: int,
    requested_targets: list[str],
    jni_enabled: bool,
) -> dict[str, object]:
    safe_task_name = task_name.strip()
    if not safe_task_name:
        raise ValueError("任务名称不能为空。")
    safe_capability_name = _normalize_slug(capability_name, field_name="capability_name")
    safe_model_version = _normalize_slug(model_version, field_name="model_version")
    normalized_targets = requested_targets or ["linux_x86_64"]
    if not normalized_targets:
        raise ValueError("至少需要一个构建目标。")
    for target_name in normalized_targets:
        if target_name not in SUPPORTED_TARGETS:
            raise ValueError(f"不支持的构建目标：{target_name}")

    catalog = get_builder_catalog(
        build_catalog_snapshot_path,
        ai_train_api_base_url,
        ai_license_mgr_api_base_url,
    )
    capability = next(
        (item for item in catalog.get("capabilities", []) if item.get("capability_name") == safe_capability_name),
        None,
    )
    if capability is None:
        raise ValueError("未找到匹配能力，请先同步 ai-train 能力目录。")

    model = next(
        (
            item
            for item in catalog.get("models", [])
            if item.get("capability_name") == safe_capability_name and item.get("model_version") == safe_model_version
        ),
        None,
    )
    if model is None:
        raise ValueError("未找到匹配模型版本，请先同步 ai-train 模型目录。")

    license_issue = next(
        (
            item
            for item in catalog.get("license_issues", [])
            if int(item.get("issue_record_id", 0)) == issue_record_id
        ),
        None,
    )
    if license_issue is None:
        raise ValueError("未找到匹配授权记录，请先同步 ai-license-mgr 授权目录。")

    capability_scope = license_issue.get("capability_scope", [])
    if capability_scope and safe_capability_name not in capability_scope:
        raise ValueError("授权能力范围不包含当前能力。")
    if license_issue.get("status") != "issued":
        raise ValueError("仅可使用 issued 状态授权记录。")

    build_task = BuildTaskModel(
        task_name=safe_task_name,
        capability_name=safe_capability_name,
        model_version=safe_model_version,
        issue_record_id=issue_record_id,
        requested_targets_json=json.dumps(sorted(set(normalized_targets)), ensure_ascii=False, sort_keys=True),
        jni_enabled=jni_enabled,
        status="running",
        build_root_path="",
        log_path="",
        started_at=datetime.now(UTC).replace(tzinfo=None),
    )
    session.add(build_task)
    session.commit()
    session.refresh(build_task)

    task_root = (build_tasks_root / f"task_{build_task.id}").resolve()
    if not (task_root == build_tasks_root or build_tasks_root in task_root.parents):
        raise ValueError("构建目录非法。")
    task_root.mkdir(parents=True, exist_ok=True)
    task_log_path = (build_logs_root / f"task_{build_task.id}.log").resolve()
    _append_log(task_log_path, f"开始构建任务 #{build_task.id}")

    source_root = task_root / "source"
    source_include_dir = source_root / "include"
    source_src_dir = source_root / "src"
    source_jni_dir = source_root / "jni"
    _write_text(source_include_dir / f"{safe_capability_name}.h", _render_header(safe_capability_name))
    _write_text(source_src_dir / f"{safe_capability_name}.cpp", _render_source(safe_capability_name, safe_model_version))
    if jni_enabled:
        _write_text(source_jni_dir / f"{safe_capability_name}_jni.cpp", _render_jni_source(safe_capability_name))
    _write_text(source_root / "CMakeLists.txt", _render_cmakelists(safe_capability_name, jni_enabled))

    toolchains_root = task_root / "toolchains"
    for target_name in SUPPORTED_TARGETS:
        if target_name == "linux_x86_64":
            continue
        _write_text(toolchains_root / f"{target_name}.cmake", _render_toolchain_template(target_name))

    build_task.build_root_path = str(task_root)
    build_task.log_path = str(task_log_path)
    session.commit()

    target_rows: list[BuildTargetModel] = []
    artifact_checksums: list[str] = []
    dependency_summary = {
        "runtime": "onnxruntime（运行时共享依赖，首期未内置）",
        "abi": "标准 C ABI v1",
        "license_required": True,
        "build_params_controlled": True,
    }

    for target_name in sorted(set(normalized_targets)):
        target_config = SUPPORTED_TARGETS[target_name]
        output_dir = (libs_root / target_name / safe_capability_name).resolve()
        if not (output_dir == libs_root or libs_root in output_dir.parents):
            raise ValueError("产物目录非法。")
        lib_dir = output_dir / "lib"
        include_dir = output_dir / "include"
        license_dir = output_dir / "license"
        manifest_dir = output_dir / "manifest"
        jni_dir = output_dir / "jni"
        for directory in (lib_dir, include_dir, license_dir, manifest_dir):
            directory.mkdir(parents=True, exist_ok=True)
        if jni_enabled:
            jni_dir.mkdir(parents=True, exist_ok=True)

        shutil.copyfile(source_include_dir / f"{safe_capability_name}.h", include_dir / f"{safe_capability_name}.h")
        shutil.copyfile(Path(str(license_issue["license_path"])), license_dir / "license.bin")
        shutil.copyfile(Path(str(license_issue["public_key_export_path"])), license_dir / "pubkey.pem")

        target_log_path = task_root / "logs" / f"{target_name}.log"
        target_binary_name = (
            f"lib{safe_capability_name}.so"
            if target_config["artifact_format"] == "so"
            else f"{safe_capability_name}.dll"
        )
        target_binary_path = lib_dir / target_binary_name

        if bool(target_config["supports_native_build"]):
            build_dir = task_root / "native_build" / target_name
            install_dir = task_root / "native_install" / target_name
            _build_native_linux(source_root, build_dir, install_dir, target_log_path)
            installed_binary = install_dir / "lib" / f"lib{safe_capability_name}.so"
            shutil.copyfile(installed_binary, target_binary_path)
            if jni_enabled:
                jni_library_name = f"lib{safe_capability_name}_jni.so"
                installed_jni_binary = install_dir / "jni" / jni_library_name
                if installed_jni_binary.exists():
                    shutil.copyfile(installed_jni_binary, jni_dir / jni_library_name)
                else:
                    _write_template_binary(
                        jni_dir / jni_library_name,
                        {"target_name": target_name, "capability_name": safe_capability_name, "jni": True},
                    )
        else:
            _write_template_binary(
                target_binary_path,
                {
                    "target_name": target_name,
                    "capability_name": safe_capability_name,
                    "model_version": safe_model_version,
                    "build_mode": "template",
                    "toolchain": target_config["toolchain_name"],
                },
            )
            _append_log(target_log_path, f"{target_name} 当前输出交付模板与工具链占位文件。")
            if jni_enabled:
                jni_file_name = (
                    f"lib{safe_capability_name}_jni.so"
                    if target_config["artifact_format"] == "so"
                    else f"{safe_capability_name}_jni.dll"
                )
                _write_template_binary(
                    jni_dir / jni_file_name,
                    {"target_name": target_name, "capability_name": safe_capability_name, "jni": True},
                )

        target_manifest = {
            "capability_name": safe_capability_name,
            "model_version": safe_model_version,
            "target_name": target_name,
            "artifact_format": target_config["artifact_format"],
            "build_mode": target_config["build_mode"],
            "toolchain_name": target_config["toolchain_name"],
            "jni_enabled": jni_enabled,
            "customer_code": license_issue["customer_code"],
            "issue_record_id": issue_record_id,
            "dependency_summary": dependency_summary,
        }
        target_manifest_path = manifest_dir / "manifest.json"
        _write_text(target_manifest_path, json.dumps(target_manifest, ensure_ascii=False, indent=2, sort_keys=True))
        archive_path = _archive_directory(output_dir, exports_root / "ai-builder" / f"task_{build_task.id}_{target_name}")
        checksum = _sha256_file(target_binary_path)
        artifact_checksums.append(checksum)

        target_row = BuildTargetModel(
            task_id=build_task.id,
            target_name=target_name,
            os_name=str(target_config["os_name"]),
            arch_name=str(target_config["arch_name"]),
            artifact_format=str(target_config["artifact_format"]),
            build_mode=str(target_config["build_mode"]),
            toolchain_name=str(target_config["toolchain_name"]),
            jni_enabled=jni_enabled,
            status="completed",
            output_dir=str(output_dir),
            binary_path=str(target_binary_path),
            header_dir=str(include_dir),
            manifest_path=str(target_manifest_path),
            checksum=checksum,
            log_path=str(target_log_path),
            download_archive_path=str(archive_path),
        )
        session.add(target_row)
        session.commit()
        session.refresh(target_row)
        target_rows.append(target_row)

        for artifact_type, artifact_path in (
            ("binary", target_binary_path),
            ("header", include_dir / f"{safe_capability_name}.h"),
            ("license", license_dir / "license.bin"),
            ("pubkey", license_dir / "pubkey.pem"),
            ("manifest", target_manifest_path),
            ("archive", archive_path),
        ):
            _register_artifact(
                session,
                task_id=build_task.id,
                target_id=target_row.id,
                artifact_type=artifact_type,
                output_dir=output_dir,
                absolute_path=artifact_path,
            )
        if jni_enabled:
            for jni_path in jni_dir.iterdir():
                if jni_path.is_file():
                    _register_artifact(
                        session,
                        task_id=build_task.id,
                        target_id=target_row.id,
                        artifact_type="jni",
                        output_dir=output_dir,
                        absolute_path=jni_path,
                    )
        session.commit()

    task_manifest = {
        "task_id": build_task.id,
        "task_name": safe_task_name,
        "capability_name": safe_capability_name,
        "model_version": safe_model_version,
        "issue_record_id": issue_record_id,
        "requested_targets": sorted(set(normalized_targets)),
        "jni_enabled": jni_enabled,
        "artifact_checksums": artifact_checksums,
        "targets": [
            {
                "target_name": target.target_name,
                "binary_path": target.binary_path,
                "download_archive_path": target.download_archive_path,
                "checksum": target.checksum,
            }
            for target in target_rows
        ],
    }
    task_manifest_path = task_root / "build_manifest.json"
    _write_text(task_manifest_path, json.dumps(task_manifest, ensure_ascii=False, indent=2, sort_keys=True))

    manifest_row = BuildManifestModel(
        task_id=build_task.id,
        manifest_version="1.0.0",
        manifest_path=str(task_manifest_path),
        manifest_json=json.dumps(task_manifest, ensure_ascii=False, sort_keys=True),
        dependency_summary_json=json.dumps(dependency_summary, ensure_ascii=False, sort_keys=True),
    )
    session.add(manifest_row)
    build_task.manifest_path = str(task_manifest_path)
    build_task.status = "completed"
    build_task.completed_at = datetime.now(UTC).replace(tzinfo=None)
    session.commit()
    session.refresh(build_task)

    append_audit_log(
        audit_log_path,
        action="build",
        entity_type="build_task",
        entity_id=str(build_task.id),
        detail={
            "capability_name": safe_capability_name,
            "model_version": safe_model_version,
            "requested_targets": sorted(set(normalized_targets)),
            "jni_enabled": jni_enabled,
        },
    )
    return get_build_task(session, build_task.id)


def list_build_tasks(session: Session) -> list[dict[str, object]]:
    tasks = session.query(BuildTaskModel).order_by(BuildTaskModel.id.asc()).all()
    return [_task_item(task) for task in tasks]


def get_build_task(session: Session, task_id: int) -> dict[str, object]:
    task = session.get(BuildTaskModel, task_id)
    if task is None:
        raise BuildTaskNotFoundError("构建任务不存在。")
    detail = _task_item(task)
    detail["targets"] = [_target_item(item) for item in task.targets]
    detail["artifacts"] = [_artifact_item(item) for item in task.artifacts]
    detail["manifest"] = _manifest_item(task.manifest) if task.manifest is not None else None
    return detail


def list_build_targets(session: Session) -> list[dict[str, object]]:
    targets = session.query(BuildTargetModel).order_by(BuildTargetModel.id.asc()).all()
    return [_target_item(target) for target in targets]


def get_build_target(session: Session, target_id: int) -> dict[str, object]:
    target = session.get(BuildTargetModel, target_id)
    if target is None:
        raise BuildTargetNotFoundError("构建目标不存在。")
    return _target_item(target)


def list_build_artifacts(session: Session) -> list[dict[str, object]]:
    artifacts = session.query(BuildArtifactModel).order_by(BuildArtifactModel.id.asc()).all()
    return [_artifact_item(artifact) for artifact in artifacts]
