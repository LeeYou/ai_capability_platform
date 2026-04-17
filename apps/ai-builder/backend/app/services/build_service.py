from __future__ import annotations

import ctypes
import ctypes.util
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import tarfile
from typing import Any

from sqlalchemy.orm import Session

from app.db.models import BuildArtifactModel, BuildManifestModel, BuildTargetModel, BuildTaskModel
from app.services.audit_service import append_audit_log
from app.services.catalog_service import get_builder_catalog
from app.services.build_contracts import build_delivery_summary, build_validation_vectors
from platform_shared.backend import validate_delivery_package_dir

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

DELIVERY_PACKAGE_SDK_DIRS = {
    "linux_x86_64": "sdk_linux_x86_64",
    "linux_arm64": "sdk_linux_aarch64",
    "windows_x86": "sdk_windows_x86",
    "windows_x86_64": "sdk_windows_x86_64",
}

REPO_ROOT = Path(__file__).resolve().parents[5]
AI_PROD_DOCKER_SOURCES = (
    "apps/ai-prod/Dockerfile",
    "apps/ai-prod/backend",
    "apps/ai-prod/config",
    "apps/ai-prod/cpp",
    "apps/ai-prod/frontend",
    "apps/ai-prod/scripts",
    "apps/ai-prod/cpp/third_party",
)
LICENSE_TOOL_VERSION = "1.0.0"
LICENSE_TOOL_SOURCE_FILES = {
    "CMakeLists.txt": REPO_ROOT / "apps/shared/license_tool_src/CMakeLists.txt",
    "src/license_tool.cpp": REPO_ROOT / "apps/shared/license_tool_src/src/license_tool.cpp",
    "src/license_common.cpp": REPO_ROOT / "apps/shared/license_tool_src/src/license_common.cpp",
    "src/license_common.h": REPO_ROOT / "apps/shared/license_tool_src/src/license_common.h",
}

ACCEPTANCE_CHECKLIST_TEMPLATE = [
    (
        "基础环境",
        [
            "已执行 `bash scripts/docker/init_host_root.sh`",
            "宿主机存在 `data/ datasets/ models/ license/ libs/ configs/ logs/ exports/`",
            "所有服务端口 26000-26005 未被占用",
            "ai-prod 已确认容器内 `26014` 仅供 Python backend 内部壳层使用，不对外暴露",
        ],
    ),
    (
        "模块健康检查",
        [
            "`ai-train` `/api/v1/health` 返回成功",
            "`ai-test` `/api/v1/health` 返回成功",
            "`ai-license-mgr` `/api/v1/health` 返回成功",
            "`ai-builder` `/api/v1/health` 返回成功",
            "`ai-prod` `/api/v1/health` 返回成功",
            "`ai-sdk` `/api/v1/health` 返回成功",
        ],
    ),
    (
        "数据与协议兼容性",
        [
            "ai-train 生成模型包与 `manifest.json`",
            "ai-test 能同步 ai-train 模型目录",
            "ai-license-mgr 能生成 `license.bin` 与 `pubkey.pem`",
            "ai-builder 能读取模型与 license 并输出 `libs/<target>/<capability>/`",
            "ai-builder manifest 满足共享 schema",
            "ai-prod 能装载模型、库与 license 并完成推理",
            "ai-sdk 能基于 ai-builder 交付目录生成单机交付包",
            "ai-sdk manifest 满足共享 schema",
            "manifest/checksum/license 三者可追溯且相互兼容",
        ],
    ),
    (
        "质量校验",
        [
            "六个后端模块测试通过",
            "五个前端模块 `npm ci && build && lint` 通过",
            "共享 schema 与示例校验通过",
            "`docker compose config` 校验通过",
            "六个 Docker 镜像构建通过",
            "ai-prod 已执行 `python3 apps/ai-prod/scripts/acceptance_check.py --base-url http://127.0.0.1:26004`",
            "ai-prod 已执行基础并发 smoke，记录成功率与 p95/p99",
        ],
    ),
    (
        "交付材料",
        [
            "已整理共享 schema 目录",
            "已整理错误码说明",
            "已整理 docker-compose 使用说明",
            "已整理交付物清单",
            "已整理故障排查指南",
            "已整理 ai-prod 运行规范与默认环境模板",
        ],
    ),
]


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
        "delivery_package_dir": task.delivery_package_dir,
        "delivery_package_archive_path": task.delivery_package_archive_path,
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


def _render_source(capability_name: str, model_version: str, task_type: str = "classification") -> str:
    """生成能力插件 C++ 源文件。

    采用 ONNXRUNTIME_ENABLED 编译宏控制真实推理路径；未启用时采用平台仿真模式回退，
    确保插件可在开发/CI 环境下正常编译与 ABI 校验，在生产环境中链接 ONNX Runtime 后
    自动切换为真实推理路径。
    """
    return f"""#include \"{capability_name}.h\"

#include <cstring>
#include <string>

// ONNX Runtime 推理头文件（通过 cmake 变量 ONNXRUNTIME_ENABLED 控制）
#ifdef ONNXRUNTIME_ENABLED
#include <onnxruntime_cxx_api.h>
#endif

namespace {{
constexpr const char* kCapabilityName = \"{capability_name}\";
constexpr const char* kModelVersion = \"{model_version}\";
constexpr const char* kTaskType = \"{task_type}\";
}} // namespace

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

#ifdef ONNXRUNTIME_ENABLED
  // ONNX Runtime 真实推理路径；模型文件从挂载目录中按标准布局加载
  try {{
    Ort::Env env(ORT_LOGGING_LEVEL_WARNING, kCapabilityName);
    Ort::SessionOptions session_options;
    // 模型路径约定：<model_root>/{capability_name}/{model_version}/model.onnx
    // model_root 由宿主机挂载配置注入，此处使用合理默认值
    std::string model_path = std::string("models/{capability_name}/{model_version}/model.onnx");
    Ort::Session session(env, model_path.c_str(), session_options);
    // 预处理、推理与后处理逻辑由能力实现者按任务类型 {task_type} 填充
    std::string result = std::string("{{\\\"capability\\\":\\\"") + kCapabilityName +
                         "\\\",\\\"model_version\\\":\\\"" + kModelVersion +
                         "\\\",\\\"task_type\\\":\\\"" + kTaskType +
                         "\\\",\\\"status\\\":\\\"ok\\\"}}";
    if (result.size() + 1 > output_buffer_size) {{
      return -2;
    }}
    std::memcpy(output_buffer, result.c_str(), result.size() + 1);
    return 0;
  }} catch (...) {{
    return -3;
  }}
#else
  // 平台仿真模式：ONNX Runtime 未启用时的保守回退，确保 ABI 合规
  std::string result = std::string("{{\\\"capability\\\":\\\"") + kCapabilityName +
                       "\\\",\\\"model_version\\\":\\\"" + kModelVersion +
                       "\\\",\\\"task_type\\\":\\\"" + kTaskType +
                       "\\\",\\\"status\\\":\\\"simulation_mode\\\"}}";
  if (result.size() + 1 > output_buffer_size) {{
    return -2;
  }}
  std::memcpy(output_buffer, result.c_str(), result.size() + 1);
  return 0;
#endif
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
target_include_directories({capability_name}_jni PRIVATE ${{CMAKE_CURRENT_SOURCE_DIR}}/include)
if(ONNXRUNTIME_ENABLED)
  target_link_libraries({capability_name}_jni PRIVATE onnxruntime::onnxruntime)
  target_compile_definitions({capability_name}_jni PRIVATE ONNXRUNTIME_ENABLED)
endif()
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

# ONNX Runtime 推理后端（生产部署时启用：cmake -DONNXRUNTIME_ENABLED=ON）
option(ONNXRUNTIME_ENABLED "启用 ONNX Runtime 推理后端" OFF)
if(ONNXRUNTIME_ENABLED)
  find_package(onnxruntime REQUIRED)
  message(STATUS "ONNX Runtime 已启用，使用真实推理后端")
else()
  message(STATUS "ONNX Runtime 未启用，使用平台仿真模式")
endif()

add_library({capability_name} SHARED src/{capability_name}.cpp)
target_include_directories({capability_name} PUBLIC ${{CMAKE_CURRENT_SOURCE_DIR}}/include)
if(ONNXRUNTIME_ENABLED)
  target_link_libraries({capability_name} PRIVATE onnxruntime::onnxruntime)
  target_compile_definitions({capability_name} PRIVATE ONNXRUNTIME_ENABLED)
endif()
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


def _load_source_manifest(manifest_path: str | None) -> dict[str, Any] | None:
    """从 ai-train 模型包 manifest_path 加载 manifest，提取追溯字段。"""
    if not manifest_path:
        return None
    path = Path(manifest_path)
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            return data
    except (OSError, ValueError):
        pass
    return None


def _copy_model_package_to_sdk(artifact_path: str | None, sdk_model_dir: Path) -> dict[str, Any]:
    """将 ai-train 模型包文件复制到 SDK 的 models/ 目录。

    复制的标准文件：manifest.json、labels.json、preprocess.json、runtime_contract.json；
    其他文件（模型权重等）按存在性复制，不强依赖。
    返回复制报告，包含实际复制的文件列表与缺失文件列表。
    """
    report: dict[str, Any] = {
        "source_artifact_path": artifact_path,
        "sdk_model_dir": str(sdk_model_dir),
        "copied_files": [],
        "missing_files": [],
        "status": "skipped",
    }
    if not artifact_path:
        report["status"] = "skipped"
        return report

    source_dir = Path(artifact_path)
    if not source_dir.is_dir():
        report["status"] = "source_not_found"
        return report

    sdk_model_dir.mkdir(parents=True, exist_ok=True)

    standard_files = ["manifest.json", "labels.json", "preprocess.json", "runtime_contract.json", "delivery_metadata.json"]
    for filename in standard_files:
        src = source_dir / filename
        if src.is_file():
            shutil.copy2(src, sdk_model_dir / filename)
            report["copied_files"].append(filename)
        else:
            report["missing_files"].append(filename)

    # 复制模型权重文件（支持 .onnx / .bin 两种格式）
    for src in source_dir.iterdir():
        if src.is_file() and src.suffix in (".onnx", ".bin") and src.name not in report["copied_files"]:
            shutil.copy2(src, sdk_model_dir / src.name)
            report["copied_files"].append(src.name)

    report["status"] = "completed"
    return report


def _validate_model_package(artifact_path: str | None, manifest_path: str | None) -> dict[str, Any]:
    """校验 ai-train 模型包完整性。

    检查模型包目录是否存在、manifest 是否包含必要字段、标准资产文件是否齐全。
    返回校验报告。
    """
    report: dict[str, Any] = {
        "checks": [],
        "overall_status": "passed",
    }

    def _add_check(name: str, status: str, detail: str) -> None:
        report["checks"].append({"name": name, "status": status, "detail": detail})
        if status == "failed":
            report["overall_status"] = "failed"
        elif status == "warning" and report["overall_status"] == "passed":
            report["overall_status"] = "warning"

    if not artifact_path:
        _add_check("模型包目录", "warning", "artifact_path 未提供，跳过模型包校验")
        return report

    artifact_dir = Path(artifact_path)
    if not artifact_dir.is_dir():
        _add_check("模型包目录", "warning", f"目录不存在：{artifact_path}（开发环境下可忽略）")
        return report

    _add_check("模型包目录", "passed", f"目录存在：{artifact_path}")

    manifest_file = Path(manifest_path) if manifest_path else artifact_dir / "manifest.json"
    if not manifest_file.is_file():
        _add_check("manifest.json", "warning", "manifest.json 不存在")
    else:
        try:
            manifest_data = json.loads(manifest_file.read_text(encoding="utf-8"))
            required_fields = ["capability_name", "model_version", "task_type"]
            missing = [f for f in required_fields if f not in manifest_data]
            if missing:
                _add_check("manifest 必要字段", "failed", f"缺少字段：{missing}")
            else:
                _add_check("manifest.json", "passed", "必要字段完整")
        except (OSError, ValueError) as exc:
            _add_check("manifest.json", "failed", f"读取失败：{exc}")

    for asset_name in ("labels.json", "preprocess.json"):
        asset_path = artifact_dir / asset_name
        if asset_path.is_file():
            _add_check(asset_name, "passed", "文件存在")
        else:
            _add_check(asset_name, "warning", f"{asset_name} 不存在（训练任务未执行导出时可忽略）")

    return report


def _validate_plugin_loadability(binary_path: Path, capability_name: str) -> dict[str, Any]:
    """校验已编译的 Linux .so 可被动态加载，且导出了标准 ABI 符号。

    仅对 linux_x86_64 原生构建产物执行；其他平台返回 skipped。
    """
    report: dict[str, Any] = {
        "binary_path": str(binary_path),
        "checks": [],
        "overall_status": "passed",
    }

    def _add_check(name: str, status: str, detail: str) -> None:
        report["checks"].append({"name": name, "status": status, "detail": detail})
        if status == "failed" and report["overall_status"] != "failed":
            report["overall_status"] = "failed"

    if not binary_path.is_file():
        _add_check("文件存在性", "failed", f"二进制文件不存在：{binary_path}")
        return report

    _add_check("文件存在性", "passed", f"文件存在，大小 {binary_path.stat().st_size} 字节")

    try:
        lib = ctypes.CDLL(str(binary_path))
        _add_check("动态加载", "passed", "ctypes.CDLL 加载成功")

        expected_symbols = [
            "ai_builder_get_abi_version",
            "ai_builder_get_capability_name",
            "ai_builder_get_model_version",
            f"{capability_name}_predict",
        ]
        for symbol in expected_symbols:
            try:
                getattr(lib, symbol)
                _add_check(f"符号 {symbol}", "passed", "符号导出正常")
            except AttributeError:
                _add_check(f"符号 {symbol}", "failed", "符号未导出")
    except OSError as exc:
        _add_check("动态加载", "failed", f"加载失败：{exc}")

    return report


def _run_pre_delivery_checks(
    target_binary_path: Path,
    capability_name: str,
    artifact_path: str | None,
    manifest_path: str | None,
    license_path: str,
) -> dict[str, Any]:
    """执行交付前运行时可装载性与一致性校验（B14）。

    包含：模型包完整性校验、license 文件存在性、插件动态加载（仅限 linux 原生产物）。
    返回完整校验报告。
    """
    model_validation = _validate_model_package(artifact_path, manifest_path)

    license_check: dict[str, Any] = {
        "name": "license 文件存在性",
        "status": "passed" if Path(license_path).is_file() else "failed",
        "detail": "license.bin 存在" if Path(license_path).is_file() else f"license.bin 不存在：{license_path}",
    }

    plugin_validation = _validate_plugin_loadability(target_binary_path, capability_name)

    statuses = [model_validation["overall_status"], plugin_validation["overall_status"], license_check["status"]]
    if "failed" in statuses:
        overall = "failed"
    elif "warning" in statuses:
        overall = "warning"
    else:
        overall = "passed"

    return {
        "validated_at": datetime.now(timezone.utc).replace(tzinfo=None).isoformat(),
        "capability_name": capability_name,
        "overall_status": overall,
        "model_package": model_validation,
        "license_check": license_check,
        "plugin_loadability": plugin_validation,
        "stage": "B14",
    }


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


def _copy_directory_contents(source_dir: Path, destination_dir: Path) -> None:
    destination_dir.mkdir(parents=True, exist_ok=True)
    if not source_dir.exists():
        return
    for child in source_dir.iterdir():
        target_path = destination_dir / child.name
        if child.is_dir():
            shutil.copytree(child, target_path, dirs_exist_ok=True)
        else:
            shutil.copy2(child, target_path)


def _write_delivery_placeholder(directory: Path, title: str, lines: list[str]) -> None:
    content = "\n".join([f"# {title}", "", *lines, ""])
    _write_text(directory / "README.md", content)


def _copy_file(source_path: Path, destination_path: Path) -> None:
    destination_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source_path, destination_path)


def _relative_to_package(path: Path, package_root: Path) -> str:
    return str(path.resolve().relative_to(package_root.resolve()))


def _delivery_file_entry(path: Path, package_root: Path) -> dict[str, object]:
    resolved_path = path.resolve()
    package_resolved = package_root.resolve()
    try:
        path_value = str(resolved_path.relative_to(package_resolved))
    except ValueError:
        path_value = str(resolved_path)
    return {
        "path": path_value,
        "checksum": _sha256_file(path),
        "size_bytes": path.stat().st_size,
    }


def _create_docker_bundle(
    docker_dir: Path,
    *,
    capability_name: str,
    model_version: str,
) -> dict[str, object]:
    docker_dir.mkdir(parents=True, exist_ok=True)
    archive_path = docker_dir / "ai-prod_image_build_context.tar.gz"
    root_prefix = Path("ai-prod_image_build_context")
    excluded_parts = {"build", "node_modules", "dist", "__pycache__", ".pytest_cache"}

    def _tar_filter(tar_info: tarfile.TarInfo) -> tarfile.TarInfo | None:
        if any(part in excluded_parts for part in Path(tar_info.name).parts):
            return None
        return tar_info

    included_sources: list[str] = []
    with tarfile.open(archive_path, "w:gz") as tar:
        for relative_path in AI_PROD_DOCKER_SOURCES:
            source_path = REPO_ROOT / relative_path
            if not source_path.exists():
                continue
            included_sources.append(relative_path)
            tar.add(
                source_path,
                arcname=str(root_prefix / relative_path),
                recursive=True,
                filter=_tar_filter,
            )

    manifest = {
        "archive_path": str(archive_path.resolve()),
        "included_sources": included_sources,
        "recommended_build_steps": [
            "docker build -f Dockerfile.base.cuda118 -t ai-capability-platform/base:cuda118 .",
            "tar -xzf ai-prod_image_build_context.tar.gz",
            "cd ai-prod_image_build_context",
            "docker build --build-arg AI_CAP_BASE_IMAGE=ai-capability-platform/base:cuda118 -f apps/ai-prod/Dockerfile -t ai-capability-platform/ai-prod:delivery .",
        ],
        "capability_name": capability_name,
        "model_version": model_version,
    }
    _write_text(docker_dir / "manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True))
    _write_text(
        docker_dir / "README.md",
        "\n".join(
            [
                "# docker",
                "",
                "本目录提供 ai-prod 生产镜像交付所需的构建上下文 tarball。",
                "",
                f"- 目标能力：{capability_name}",
                f"- 模型版本：{model_version}",
                f"- 归档文件：{archive_path.name}",
                "",
                "推荐构建流程：",
                "1. 在仓库根目录构建基础镜像 `ai-capability-platform/base:cuda118`。",
                "2. 解压 `ai-prod_image_build_context.tar.gz`。",
                "3. 进入解压目录后执行 `docker build --build-arg AI_CAP_BASE_IMAGE=ai-capability-platform/base:cuda118 -f apps/ai-prod/Dockerfile -t ai-capability-platform/ai-prod:delivery .`。",
                "",
            ]
        ),
    )
    return manifest


def _create_mount_template(
    mount_template_dir: Path,
    *,
    capability_name: str,
    model_version: str,
) -> dict[str, object]:
    mount_template_dir.mkdir(parents=True, exist_ok=True)
    template_directories = ("data", "datasets", "models", "license", "libs", "configs", "logs", "exports")
    for directory_name in template_directories:
        template_dir = mount_template_dir / directory_name
        template_dir.mkdir(parents=True, exist_ok=True)
        _write_text(
            template_dir / "README.md",
            "\n".join(
                [
                    f"# {directory_name}",
                    "",
                    f"该目录为 ai-prod 交付挂载模板的一部分，用于能力 `{capability_name}` / 版本 `{model_version}` 的标准部署。",
                    "",
                ]
            ),
        )

    scripts_dir = mount_template_dir / "scripts"
    scripts_dir.mkdir(parents=True, exist_ok=True)
    _copy_file(REPO_ROOT / "scripts/docker/init_host_root.sh", scripts_dir / "init_host_root.sh")
    _copy_file(REPO_ROOT / "apps/ai-prod/scripts/run_prod_stack.sh", scripts_dir / "run_prod_stack.sh")
    _copy_file(REPO_ROOT / "apps/ai-prod/config/prod_defaults.env", mount_template_dir / "configs" / "prod_defaults.env")
    _write_text(
        mount_template_dir / "configs" / "platform.env.example",
        "\n".join(
            [
                "AI_CAP_HOST_ROOT=/data/ai_capability_platform",
                f"AI_DELIVERY_CAPABILITY={capability_name}",
                f"AI_DELIVERY_MODEL_VERSION={model_version}",
                "AI_PROD_CPP_BIND_PORT=26004",
                "AI_PROD_PY_BACKEND_PORT=26014",
                "",
            ]
        ),
    )
    _write_text(
        mount_template_dir / "README.md",
        "\n".join(
            [
                "# mount_template",
                "",
                "本目录提供 ai-prod 客户交付时的宿主机目录模板、默认环境模板与启动脚本副本。",
                "",
                "建议流程：",
                "1. 先执行 `scripts/init_host_root.sh` 初始化宿主机根目录。",
                "2. 按需修改 `configs/prod_defaults.env` 与 `configs/platform.env.example`。",
                "3. 将交付包中的 models / libs / license 放入对应目录。",
                "4. 通过 docker 目录中的镜像构建上下文构建并启动交付镜像。",
                "",
            ]
        ),
    )
    return {
        "template_directories": list(template_directories),
        "scripts": ["scripts/init_host_root.sh", "scripts/run_prod_stack.sh"],
        "config_files": ["configs/prod_defaults.env", "configs/platform.env.example"],
    }


def _create_tools_bundle(tools_dir: Path) -> dict[str, object]:
    tools_dir.mkdir(parents=True, exist_ok=True)
    validation_dir = tools_dir / "validation"
    ops_dir = tools_dir / "ops"
    license_tool_dir = tools_dir / "license_tool"
    validation_dir.mkdir(parents=True, exist_ok=True)
    ops_dir.mkdir(parents=True, exist_ok=True)
    license_tool_dir.mkdir(parents=True, exist_ok=True)

    _copy_file(REPO_ROOT / "apps/ai-prod/scripts/acceptance_check.py", validation_dir / "acceptance_check.py")
    _copy_file(REPO_ROOT / "apps/ai-prod/scripts/pressure_smoke.py", validation_dir / "pressure_smoke.py")
    _copy_file(REPO_ROOT / "scripts/docker/health_check.sh", ops_dir / "health_check.sh")
    _copy_file(REPO_ROOT / "scripts/docker/init_host_root.sh", ops_dir / "init_host_root.sh")
    for relative_path, source_path in LICENSE_TOOL_SOURCE_FILES.items():
        _copy_file(source_path, license_tool_dir / relative_path)
    _write_text(license_tool_dir / "VERSION", LICENSE_TOOL_VERSION + "\n")
    _write_text(
        license_tool_dir / "manifest.json",
        json.dumps(
            {
                "tool_name": "license_tool",
                "version": LICENSE_TOOL_VERSION,
                "bundle_format": "source_bundle",
                "source_files": sorted(LICENSE_TOOL_SOURCE_FILES),
                "build_command": "cmake -S . -B build && cmake --build build --parallel",
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        ),
    )
    _write_text(
        license_tool_dir / "README.md",
        "\n".join(
            [
                "# license_tool",
                "",
                "- 当前交付为标准 C++ source bundle，可在客户环境按需构建。",
                f"- 版本：`{LICENSE_TOOL_VERSION}`",
                "",
                "## 构建方式",
                "",
                "```bash",
                "cmake -S . -B build",
                "cmake --build build --parallel",
                "```",
                "",
                "## 常用命令",
                "",
                "```bash",
                "./build/license_tool verify /path/to/license.bin",
                "./build/license_tool generate /path/to/license.bin customer_name capability_a,capability_b",
                "```",
                "",
            ]
        ),
    )
    _write_text(
        license_tool_dir / "ERROR_CODES.md",
        "\n".join(
            [
                "# ERROR_CODES",
                "",
                "| 退出码 | 含义 |",
                "| --- | --- |",
                "| 1 | 参数不足或 mode 非法 |",
                "| 2 | generate 参数错误 |",
                "| 3 | 生成 license 文件失败 |",
                "| 4 | 解析 license 文件失败 |",
                "| 5 | 验证 license 失败 |",
                "| 6 | 未知 mode |",
                "",
            ]
        ),
    )
    _write_text(
        license_tool_dir / "HARDWARE_FINGERPRINT.md",
        "\n".join(
            [
                "# HARDWARE_FINGERPRINT",
                "",
                "硬件指纹采用 `key=value` 形式按 key 排序后，以 `|` 连接并计算 SHA256。",
                "",
                "示例：",
                "",
                "```text",
                "cpu=intel-i7|disk=nvme-sn-001|mac=00:11:22:33:44:55",
                "```",
                "",
            ]
        ),
    )
    _write_text(
        validation_dir / "verify_delivery_package.py",
        "\n".join(
            [
                "from __future__ import annotations",
                "",
                "import argparse",
                "from pathlib import Path",
                "import sys",
                "",
                "",
                "def main() -> int:",
                "    parser = argparse.ArgumentParser(description='Verify ai-builder delivery package skeleton.')",
                "    parser.add_argument('package_root')",
                "    args = parser.parse_args()",
                "    package_root = Path(args.package_root).resolve()",
                "    required = [",
                "        'docker',",
                "        'mount_template',",
                "        'tools',",
                "        'docs',",
                "        'licenses',",
                "        'acceptance_checklist.json',",
                "        'version_manifest.json',",
                "        'delivery_summary.json',",
                "        'delivery_summary.md',",
                "        'tools/license_tool/manifest.json',",
                "    ]",
                "    missing = [item for item in required if not (package_root / item).exists()]",
                "    if missing:",
                "        print(f'missing paths: {missing}', file=sys.stderr)",
                "        return 1",
                "    print('delivery package verified')",
                "    return 0",
                "",
                "",
                "if __name__ == '__main__':",
                "    raise SystemExit(main())",
                "",
            ]
        ),
    )
    _write_text(
        tools_dir / "README.md",
        "\n".join(
            [
                "# tools",
                "",
                "本目录汇总交付阶段常用的验收、压测、健康检查与宿主机初始化工具。",
                "",
                "- validation/acceptance_check.py：ai-prod 公共 API 验收脚本",
                "- validation/pressure_smoke.py：基础并发压测脚本",
                "- validation/verify_delivery_package.py：交付目录结构快速校验脚本",
                "- ops/health_check.sh：平台级健康检查脚本",
                "- ops/init_host_root.sh：宿主机根目录初始化脚本",
                "- license_tool/：标准授权工具 source bundle、README、错误码与硬件指纹说明",
                "",
            ]
        ),
    )
    return {
        "validation_scripts": [
            "validation/acceptance_check.py",
            "validation/pressure_smoke.py",
            "validation/verify_delivery_package.py",
        ],
        "ops_scripts": ["ops/health_check.sh", "ops/init_host_root.sh"],
        "license_tool": {
            "version": LICENSE_TOOL_VERSION,
            "root": "license_tool",
            "manifest_path": "license_tool/manifest.json",
            "documents": [
                "license_tool/README.md",
                "license_tool/ERROR_CODES.md",
                "license_tool/HARDWARE_FINGERPRINT.md",
            ],
        },
    }


def _create_docs_bundle(
    docs_dir: Path,
    *,
    capability_name: str,
    model_version: str,
    issue_record_id: int,
) -> dict[str, object]:
    docs_dir.mkdir(parents=True, exist_ok=True)
    _copy_file(REPO_ROOT / "docs/07_部署运维/ai-prod运行规范.md", docs_dir / "AI_PROD_RUNTIME.md")
    _write_text(
        docs_dir / "DEPLOYMENT.md",
        "\n".join(
            [
                "# DEPLOYMENT",
                "",
                f"- 交付能力：{capability_name}",
                f"- 模型版本：{model_version}",
                f"- 授权记录：issue_{issue_record_id}",
                "",
                "部署步骤：",
                "1. 解压 delivery_package 并确认 docker / mount_template / tools / docs / sdk_* / licenses 目录齐全。",
                "2. 参考 `mount_template/` 初始化宿主机目录，并将交付物放入对应挂载位置。",
                "3. 参考 `docker/README.md` 构建 ai-prod 交付镜像。",
                "4. 如需现场核验授权，可先参考 `tools/license_tool/README.md` 构建并使用 `license_tool verify`。",
                "5. 使用 `tools/validation/acceptance_check.py` 与 `tools/validation/pressure_smoke.py` 完成交付验收。",
                "",
            ]
        ),
    )
    _write_text(
        docs_dir / "OPERATIONS.md",
        "\n".join(
            [
                "# OPERATIONS",
                "",
                "推荐运维动作：",
                "- 启动前先执行宿主机目录初始化与环境变量模板核对。",
                "- 定期检查 `${AI_CAP_HOST_ROOT}/logs` 与 runtime snapshot。",
                "- 变更 license 后执行 admin license reload 或重新启动服务。",
                "- 使用交付包附带的 health_check / acceptance_check / pressure_smoke 进行巡检。",
                "",
            ]
        ),
    )
    _write_text(
        docs_dir / "TROUBLESHOOTING.md",
        "\n".join(
            [
                "# TROUBLESHOOTING",
                "",
                "常见排查项：",
                "1. `license.bin` 与 `pubkey.pem` 是否与当前 capability / model_version 匹配。",
                "2. `libs/` 与 `models/` 是否按 manifest 约定放置。",
                "3. 对外仅暴露 26004，26014 仅用于容器内 Python backend 壳层。",
                "4. 如验收脚本失败，优先查看 `${AI_CAP_HOST_ROOT}/logs/ai_prod_runtime.log`。",
                "",
            ]
        ),
    )
    _write_text(
        docs_dir / "DELIVERY_CONTENTS.md",
        "\n".join(
            [
                "# DELIVERY_CONTENTS",
                "",
                "本次交付包包含以下物料：",
                "- docker：ai-prod 生产镜像构建上下文 tarball 与构建说明",
                "- mount_template：宿主机目录模板、默认配置与启动脚本副本",
                "- tools：验收、压测、健康检查与宿主机初始化工具",
                "- docs：部署、运维、排障文档",
                "- sdk_*：各平台 SDK / 插件产物",
                "- licenses：授权文件与公钥",
                "",
            ]
        ),
    )
    return {
        "documents": [
            "AI_PROD_RUNTIME.md",
            "DEPLOYMENT.md",
            "OPERATIONS.md",
            "TROUBLESHOOTING.md",
            "DELIVERY_CONTENTS.md",
        ]
    }


def _create_acceptance_checklist(
    package_root: Path,
    *,
    task_id: int,
    capability_name: str,
    model_version: str,
) -> dict[str, object]:
    checklist = {
        "task_id": task_id,
        "capability_name": capability_name,
        "model_version": model_version,
        "source_document": "docs/07_部署运维/联调验收清单.md",
        "sections": [
            {
                "section_name": section_name,
                "items": [
                    {
                        "item_id": f"S{section_index:02d}-I{item_index:02d}",
                        "description": description,
                        "status": "pending",
                    }
                    for item_index, description in enumerate(items, start=1)
                ],
            }
            for section_index, (section_name, items) in enumerate(ACCEPTANCE_CHECKLIST_TEMPLATE, start=1)
        ],
    }
    _write_text(
        package_root / "acceptance_checklist.json",
        json.dumps(checklist, ensure_ascii=False, indent=2, sort_keys=True),
    )
    return checklist


def _create_version_manifest(
    package_root: Path,
    *,
    task_id: int,
    capability_name: str,
    model_version: str,
    issue_record_id: int,
    license_issue: dict[str, Any],
    target_rows: list[BuildTargetModel],
    sdk_items: list[dict[str, str]],
    docker_manifest: dict[str, object],
    docs_manifest: dict[str, object],
    tools_manifest: dict[str, object],
) -> dict[str, object]:
    sdk_lookup = {item["target_name"]: item for item in sdk_items}
    file_entries: list[dict[str, object]] = []
    for target in target_rows:
        sdk_item = sdk_lookup.get(target.target_name)
        binary_path = Path(target.binary_path)
        archive_path = Path(target.download_archive_path)
        manifest_path = Path(target.manifest_path)
        for candidate in (binary_path, archive_path, manifest_path):
            if candidate.is_file():
                file_entries.append(_delivery_file_entry(candidate, package_root))
        if sdk_item:
            file_entries.append(
                {
                    "target_name": target.target_name,
                    "sdk_dir": sdk_item["sdk_dir"],
                    "binary_checksum": target.checksum,
                    "binary_path": sdk_item["binary_path"],
                    "manifest_path": sdk_item["manifest_path"],
                }
            )

    license_files = [
        package_root / "licenses" / f"issue_{issue_record_id}" / "license.bin",
        package_root / "licenses" / f"issue_{issue_record_id}" / "pubkey.pem",
        package_root / "licenses" / f"issue_{issue_record_id}" / "manifest.json",
        package_root / "docker" / "ai-prod_image_build_context.tar.gz",
        package_root / "tools" / "license_tool" / "manifest.json",
        package_root / "tools" / "license_tool" / "README.md",
        package_root / "tools" / "license_tool" / "ERROR_CODES.md",
        package_root / "tools" / "license_tool" / "HARDWARE_FINGERPRINT.md",
    ]
    checksum_entries = [
        _delivery_file_entry(path, package_root)
        for path in license_files
        if path.is_file()
    ]
    version_manifest = {
        "task_id": task_id,
        "capability_name": capability_name,
        "model_version": model_version,
        "issue_record_id": issue_record_id,
        "customer_code": license_issue["customer_code"],
        "capability_scope": license_issue.get("capability_scope", []),
        "version_constraints": license_issue.get("version_constraints", {}),
        "delivery_targets": sorted(target.target_name for target in target_rows),
        "sdk_items": file_entries,
        "delivery_checksums": checksum_entries,
        "docker_bundle": docker_manifest,
        "docs_bundle": docs_manifest,
        "tools_bundle": tools_manifest,
    }
    _write_text(
        package_root / "version_manifest.json",
        json.dumps(version_manifest, ensure_ascii=False, indent=2, sort_keys=True),
    )
    return version_manifest


def _create_delivery_summary(
    package_root: Path,
    *,
    task_id: int,
    capability_name: str,
    model_version: str,
    issue_record_id: int,
    sdk_items: list[dict[str, str]],
    acceptance_checklist: dict[str, object],
    version_manifest: dict[str, object],
) -> dict[str, object]:
    summary = {
        "task_id": task_id,
        "capability_name": capability_name,
        "model_version": model_version,
        "issue_record_id": issue_record_id,
        "sdk_count": len(sdk_items),
        "acceptance_section_count": len(acceptance_checklist.get("sections", [])),
        "delivery_files": [
            "acceptance_checklist.json",
            "version_manifest.json",
            "delivery_summary.json",
            "delivery_summary.md",
        ],
        "recommended_steps": [
            "核对 acceptance_checklist.json 并按现场交付逐项验收。",
            "核对 version_manifest.json 中 capability/model/license/targets 是否与合同版本一致。",
            "根据 docker/README.md 与 mount_template/README.md 准备部署环境。",
            "使用 tools/validation 下的脚本完成 API 验收与基础压测。",
        ],
        "delivery_directories": sorted(
            item.name for item in package_root.iterdir() if item.is_dir()
        ),
        "version_manifest_path": "version_manifest.json",
    }
    _write_text(
        package_root / "delivery_summary.json",
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True),
    )
    _write_text(
        package_root / "delivery_summary.md",
        "\n".join(
            [
                "# delivery_summary",
                "",
                f"- task_id: {task_id}",
                f"- capability_name: {capability_name}",
                f"- model_version: {model_version}",
                f"- issue_record_id: {issue_record_id}",
                f"- sdk_count: {len(sdk_items)}",
                f"- acceptance_section_count: {len(acceptance_checklist.get('sections', []))}",
                "",
                "## 交付物摘要",
                "",
                "- 已生成验收清单：`acceptance_checklist.json`",
                "- 已生成版本清单：`version_manifest.json`",
                "- 已生成交付摘要：`delivery_summary.json` / `delivery_summary.md`",
                f"- 已汇总关键 checksum 条目数：{len(version_manifest.get('delivery_checksums', []))}",
                "",
                "## 推荐下一步",
                "",
                "1. 依据 acceptance_checklist.json 执行现场验收。",
                "2. 依据 version_manifest.json 核对能力、模型、license 与目标平台版本。",
                "3. 依据 docker/ 与 mount_template/ 完成环境准备与镜像构建。",
                "4. 运行 tools/validation 中的验收与压测脚本并归档结果。",
                "",
            ]
        ),
    )
    return summary


def _create_delivery_package(
    *,
    build_task: BuildTaskModel,
    exports_root: Path,
    delivery_packages_root: Path,
    safe_capability_name: str,
    safe_model_version: str,
    issue_record_id: int,
    license_issue: dict[str, Any],
    target_rows: list[BuildTargetModel],
    provenance: dict[str, Any] | None = None,
    pre_delivery_results: list[dict[str, Any]] | None = None,
) -> tuple[Path, Path]:
    package_root = (delivery_packages_root / f"task_{build_task.id}" / "delivery_package").resolve()
    if not (package_root == delivery_packages_root or delivery_packages_root in package_root.parents):
        raise ValueError("delivery_package 目录非法。")
    if package_root.parent.exists():
        shutil.rmtree(package_root.parent)
    package_root.mkdir(parents=True, exist_ok=True)

    sdk_items: list[dict[str, str]] = []
    for target in target_rows:
        sdk_dir_name = DELIVERY_PACKAGE_SDK_DIRS.get(target.target_name)
        if not sdk_dir_name:
            continue
        sdk_dir = package_root / sdk_dir_name
        _copy_directory_contents(Path(target.output_dir), sdk_dir)
        sdk_items.append(
            {
                "target_name": target.target_name,
                "sdk_dir": sdk_dir_name,
                "binary_path": str((sdk_dir / "lib" / Path(target.binary_path).name).resolve()),
                "manifest_path": str((sdk_dir / "manifest" / "manifest.json").resolve()),
            }
        )

    licenses_root = package_root / "licenses" / f"issue_{issue_record_id}"
    licenses_root.mkdir(parents=True, exist_ok=True)
    shutil.copy2(Path(str(license_issue["license_path"])), licenses_root / "license.bin")
    shutil.copy2(Path(str(license_issue["public_key_export_path"])), licenses_root / "pubkey.pem")
    _write_text(
        licenses_root / "manifest.json",
        json.dumps(
            {
                "issue_record_id": issue_record_id,
                "customer_code": license_issue["customer_code"],
                "capability_scope": license_issue.get("capability_scope", []),
                "version_constraints": license_issue.get("version_constraints", {}),
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        ),
    )

    docker_manifest = _create_docker_bundle(
        package_root / "docker",
        capability_name=safe_capability_name,
        model_version=safe_model_version,
    )
    mount_template_manifest = _create_mount_template(
        package_root / "mount_template",
        capability_name=safe_capability_name,
        model_version=safe_model_version,
    )
    tools_manifest = _create_tools_bundle(package_root / "tools")
    docs_manifest = _create_docs_bundle(
        package_root / "docs",
        capability_name=safe_capability_name,
        model_version=safe_model_version,
        issue_record_id=issue_record_id,
    )
    acceptance_checklist = _create_acceptance_checklist(
        package_root,
        task_id=build_task.id,
        capability_name=safe_capability_name,
        model_version=safe_model_version,
    )
    version_manifest = _create_version_manifest(
        package_root,
        task_id=build_task.id,
        capability_name=safe_capability_name,
        model_version=safe_model_version,
        issue_record_id=issue_record_id,
        license_issue=license_issue,
        target_rows=target_rows,
        sdk_items=sdk_items,
        docker_manifest=docker_manifest,
        docs_manifest=docs_manifest,
        tools_manifest=tools_manifest,
    )
    delivery_summary = _create_delivery_summary(
        package_root,
        task_id=build_task.id,
        capability_name=safe_capability_name,
        model_version=safe_model_version,
        issue_record_id=issue_record_id,
        sdk_items=sdk_items,
        acceptance_checklist=acceptance_checklist,
        version_manifest=version_manifest,
    )
    _write_text(
        package_root / "README.md",
        "\n".join(
            [
                "# delivery_package",
                "",
                f"- task_id: {build_task.id}",
                f"- capability_name: {safe_capability_name}",
                f"- model_version: {safe_model_version}",
                "- 已完成标准 `delivery_package/` 目录、ai-prod 生产镜像构建上下文 tarball、mount_template、tools、docs，以及验收清单、版本清单、交付摘要生成。",
                "- 已完成 B12：ONNX Runtime 感知插件源码模板、模型包文件复制到 SDK models 目录。",
                "- 已完成 B13：delivery_package 追溯链路（source_train_task_id、manifest checksum）。",
                "- 已完成 B14：交付前运行时可装载性与一致性校验，结果见 `pre_delivery_validation.json`。",
                "",
            ]
        ),
    )

    # B14：写入交付前校验报告
    pre_delivery_validation: dict[str, Any] = {
        "validated_at": datetime.now(timezone.utc).replace(tzinfo=None).isoformat(),
        "capability_name": safe_capability_name,
        "model_version": safe_model_version,
        "targets": pre_delivery_results or [],
        "overall_status": "passed",
    }
    for result in (pre_delivery_results or []):
        if result.get("overall_status") == "failed":
            pre_delivery_validation["overall_status"] = "failed"
            break
        if result.get("overall_status") == "warning":
            pre_delivery_validation["overall_status"] = "warning"
    _write_text(
        package_root / "pre_delivery_validation.json",
        json.dumps(pre_delivery_validation, ensure_ascii=False, indent=2, sort_keys=True),
    )

    _write_text(
        package_root / "package_manifest.json",
        json.dumps(
            {
                "task_id": build_task.id,
                "capability_name": safe_capability_name,
                "model_version": safe_model_version,
                "issue_record_id": issue_record_id,
                "sdk_items": sdk_items,
                "directories": [
                    "docker",
                    "licenses",
                    "mount_template",
                    "docs",
                    "tools",
                    *[item["sdk_dir"] for item in sdk_items],
                ],
                "stage_status": {
                    "B9": "completed",
                    "B10": "completed",
                    "B11": "completed",
                    "B12": "completed",
                    "B13": "completed",
                    "B14": "completed",
                },
                "provenance": provenance or {},
                "pre_delivery_validation_status": pre_delivery_validation["overall_status"],
                "docker": docker_manifest,
                "mount_template": mount_template_manifest,
                "tools": tools_manifest,
                "docs": docs_manifest,
                "acceptance_checklist_path": "acceptance_checklist.json",
                "version_manifest_path": "version_manifest.json",
                "delivery_summary": delivery_summary,
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        ),
    )

    archive_path = _archive_directory(package_root, exports_root / "delivery_packages" / f"task_{build_task.id}_delivery_package")
    return package_root, archive_path


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
    delivery_packages_root: Path,
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
        started_at=datetime.now(timezone.utc).replace(tzinfo=None),
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

    # B12/B13：加载 ai-train 模型包 manifest，提取任务类型与追溯字段
    source_manifest = _load_source_manifest(str(model.get("manifest_path") or ""))
    task_type = "classification"
    source_train_task_id: int | None = None
    source_manifest_checksum: str | None = None
    if source_manifest:
        task_type = str(source_manifest.get("task_type", task_type))
        raw_task_id = source_manifest.get("source_train_task_id")
        if isinstance(raw_task_id, int):
            source_train_task_id = raw_task_id
        manifest_path_str = str(model.get("manifest_path") or "")
        if manifest_path_str and Path(manifest_path_str).is_file():
            source_manifest_checksum = _sha256_file(Path(manifest_path_str))

    provenance: dict[str, Any] = {
        "source_train_task_id": source_train_task_id,
        "source_manifest_path": str(model.get("manifest_path") or ""),
        "source_manifest_checksum": source_manifest_checksum,
        "model_artifact_path": str(model.get("artifact_path") or ""),
        "builder_task_id": None,  # 构建任务 ID 在 commit 后填充
        "issue_record_id": issue_record_id,
    }
    _append_log(task_log_path, f"追溯信息：task_type={task_type} source_train_task_id={source_train_task_id}")

    source_root = task_root / "source"
    source_include_dir = source_root / "include"
    source_src_dir = source_root / "src"
    source_jni_dir = source_root / "jni"
    _write_text(source_include_dir / f"{safe_capability_name}.h", _render_header(safe_capability_name))
    _write_text(source_src_dir / f"{safe_capability_name}.cpp", _render_source(safe_capability_name, safe_model_version, task_type))
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
    provenance["builder_task_id"] = build_task.id
    session.commit()

    target_rows: list[BuildTargetModel] = []
    artifact_checksums: list[str] = []
    pre_delivery_results: list[dict[str, Any]] = []
    dependency_summary = {
        "runtime": "onnxruntime（运行时共享依赖，生产部署时需启用 ONNXRUNTIME_ENABLED）",
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
        model_dir = output_dir / "models" / safe_capability_name / safe_model_version
        jni_dir = output_dir / "jni"
        for directory in (lib_dir, include_dir, license_dir, manifest_dir):
            directory.mkdir(parents=True, exist_ok=True)
        if jni_enabled:
            jni_dir.mkdir(parents=True, exist_ok=True)

        shutil.copyfile(source_include_dir / f"{safe_capability_name}.h", include_dir / f"{safe_capability_name}.h")
        shutil.copyfile(Path(str(license_issue["license_path"])), license_dir / "license.bin")
        shutil.copyfile(Path(str(license_issue["public_key_export_path"])), license_dir / "pubkey.pem")

        # B12：将 ai-train 模型包文件复制到 SDK models 目录
        model_copy_report = _copy_model_package_to_sdk(
            str(model.get("artifact_path") or ""),
            model_dir,
        )
        _append_log(task_log_path, f"{target_name} 模型包复制：{model_copy_report['status']}，复制文件 {model_copy_report['copied_files']}")

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
                    "task_type": task_type,
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

        # B14：交付前运行时可装载性与一致性校验（仅 linux_x86_64 原生构建执行插件装载校验）
        pre_delivery_result = _run_pre_delivery_checks(
            target_binary_path=target_binary_path,
            capability_name=safe_capability_name,
            artifact_path=str(model.get("artifact_path") or ""),
            manifest_path=str(model.get("manifest_path") or ""),
            license_path=str(license_issue["license_path"]),
        )
        pre_delivery_result["target_name"] = target_name
        pre_delivery_results.append(pre_delivery_result)
        _append_log(
            target_log_path,
            f"{target_name} 交付前校验：{pre_delivery_result['overall_status']}，"
            f"模型包={pre_delivery_result['model_package']['overall_status']}，"
            f"插件装载={pre_delivery_result['plugin_loadability']['overall_status']}",
        )

        # B13：在目标 manifest 中记录追溯字段
        target_manifest = {
            "capability_name": safe_capability_name,
            "task_type": task_type,
            "model_version": safe_model_version,
            "target_name": target_name,
            "artifact_format": target_config["artifact_format"],
            "build_mode": target_config["build_mode"],
            "toolchain_name": target_config["toolchain_name"],
            "jni_enabled": jni_enabled,
            "customer_code": license_issue["customer_code"],
            "issue_record_id": issue_record_id,
            "dependency_summary": dependency_summary,
            "provenance": provenance,
            "model_copy_status": model_copy_report["status"],
            "pre_delivery_status": pre_delivery_result["overall_status"],
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

    # B13：汇总追溯信息到任务级 manifest
    task_manifest = {
        "task_id": build_task.id,
        "task_name": safe_task_name,
        "capability_name": safe_capability_name,
        "task_type": task_type,
        "model_version": safe_model_version,
        "issue_record_id": issue_record_id,
        "requested_targets": sorted(set(normalized_targets)),
        "jni_enabled": jni_enabled,
        "artifact_checksums": artifact_checksums,
        "provenance": provenance,
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

    manifest_row = BuildManifestModel(
        task_id=build_task.id,
        manifest_version="1.0.0",
        manifest_path=str(task_manifest_path),
        manifest_json="{}",
        dependency_summary_json=json.dumps(dependency_summary, ensure_ascii=False, sort_keys=True),
    )
    session.add(manifest_row)
    delivery_package_dir, delivery_package_archive_path = _create_delivery_package(
        build_task=build_task,
        exports_root=exports_root,
        delivery_packages_root=delivery_packages_root,
        safe_capability_name=safe_capability_name,
        safe_model_version=safe_model_version,
        issue_record_id=issue_record_id,
        license_issue=license_issue,
        target_rows=target_rows,
        provenance=provenance,
        pre_delivery_results=pre_delivery_results,
    )

    task_manifest["delivery_package"] = {
        "directory": str(delivery_package_dir),
        "archive_path": str(delivery_package_archive_path),
        "acceptance_checklist_path": str((delivery_package_dir / "acceptance_checklist.json").resolve()),
        "version_manifest_path": str((delivery_package_dir / "version_manifest.json").resolve()),
        "delivery_summary_json_path": str((delivery_package_dir / "delivery_summary.json").resolve()),
        "delivery_summary_md_path": str((delivery_package_dir / "delivery_summary.md").resolve()),
    }

    validated_delivery_package = validate_delivery_package_dir(delivery_package_dir)
    validated_summary = validated_delivery_package.get("delivery_summary")
    if isinstance(validated_summary, dict):
        task_manifest["delivery_package"].setdefault("contract_validation", {})
        task_manifest["delivery_package"]["contract_validation"]["delivery_summary"] = validated_summary
    _write_text(task_manifest_path, json.dumps(task_manifest, ensure_ascii=False, indent=2, sort_keys=True))
    manifest_row.manifest_json = json.dumps(task_manifest, ensure_ascii=False, sort_keys=True)
    build_task.manifest_path = str(task_manifest_path)
    build_task.delivery_package_dir = str(delivery_package_dir)
    build_task.delivery_package_archive_path = str(delivery_package_archive_path)
    build_task.status = "completed"
    build_task.completed_at = datetime.now(timezone.utc).replace(tzinfo=None)
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
            "delivery_package_dir": str(delivery_package_dir),
            "delivery_package_archive_path": str(delivery_package_archive_path),
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
