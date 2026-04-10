from __future__ import annotations

from datetime import UTC, datetime
import hashlib
import json
from pathlib import Path
import re
import shutil
from typing import Any

from sqlalchemy.orm import Session

from app.db.models import SdkArtifactModel, SdkPackageModel, SdkTargetModel
from app.services.audit_service import append_audit_log
from app.services.validation_contracts import DIAGNOSTICS_VERSION, build_validation_contract, build_validation_vectors


REPO_ROOT = Path(__file__).resolve().parents[5]

SUPPORTED_TARGETS: dict[str, dict[str, object]] = {
    "linux_x86_64": {
        "os_name": "linux",
        "arch_name": "x86_64",
        "artifact_format": "so",
        "supports_jni": True,
    },
    "linux_arm64": {
        "os_name": "linux",
        "arch_name": "arm64",
        "artifact_format": "so",
        "supports_jni": True,
    },
    "windows_x86": {
        "os_name": "windows",
        "arch_name": "x86",
        "artifact_format": "dll",
        "supports_jni": True,
    },
    "windows_x86_64": {
        "os_name": "windows",
        "arch_name": "x86_64",
        "artifact_format": "dll",
        "supports_jni": True,
    },
}

STANDARD_SDK_DIR_NAMES = {
    "linux_x86_64": "sdk_linux_x86_64",
    "linux_arm64": "sdk_linux_aarch64",
    "windows_x86": "sdk_windows_x86",
    "windows_x86_64": "sdk_windows_x86_64",
}
LICENSE_TOOL_VERSION = "1.0.0"
LICENSE_TOOL_SOURCE_FILES = {
    "CMakeLists.txt": REPO_ROOT / "apps/shared/license_tool_src/CMakeLists.txt",
    "src/license_tool.cpp": REPO_ROOT / "apps/shared/license_tool_src/src/license_tool.cpp",
    "src/license_common.cpp": REPO_ROOT / "apps/shared/license_tool_src/src/license_common.cpp",
    "src/license_common.h": REPO_ROOT / "apps/shared/license_tool_src/src/license_common.h",
}


class SdkPackageNotFoundError(ValueError):
    """SDK 包不存在。"""


class SdkTargetNotFoundError(ValueError):
    """SDK 目标不存在。"""


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


def _write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _append_log(path: Path, message: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(message.rstrip() + "\n")


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8192), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _archive_directory(source_dir: Path, destination_without_suffix: Path) -> Path:
    destination_without_suffix.parent.mkdir(parents=True, exist_ok=True)
    archive_path = shutil.make_archive(str(destination_without_suffix), "zip", root_dir=source_dir)
    return Path(archive_path).resolve()


def _platform_item(target_name: str) -> dict[str, object]:
    payload = SUPPORTED_TARGETS[target_name]
    return {
        "target_name": target_name,
        "os_name": payload["os_name"],
        "arch_name": payload["arch_name"],
        "artifact_format": payload["artifact_format"],
        "supports_jni": payload["supports_jni"],
    }


def list_sdk_targets() -> list[dict[str, object]]:
    return [_platform_item(name) for name in SUPPORTED_TARGETS]


def _package_item(package: SdkPackageModel) -> dict[str, object]:
    return {
        "package_id": package.id,
        "package_name": package.package_name,
        "capability_name": package.capability_name,
        "model_version": package.model_version,
        "requested_targets": json.loads(package.requested_targets_json),
        "jni_enabled": package.jni_enabled,
        "status": package.status,
        "package_root_path": package.package_root_path,
        "log_path": package.log_path,
        "manifest_path": package.manifest_path,
        "started_at": package.started_at.isoformat() if package.started_at else None,
        "completed_at": package.completed_at.isoformat() if package.completed_at else None,
    }


def _artifact_item(artifact: SdkArtifactModel) -> dict[str, object]:
    return {
        "artifact_id": artifact.id,
        "target_id": artifact.target_id,
        "artifact_type": artifact.artifact_type,
        "relative_path": artifact.relative_path,
        "absolute_path": artifact.absolute_path,
        "checksum": artifact.checksum,
    }


def _target_item(target: SdkTargetModel) -> dict[str, object]:
    return {
        "target_id": target.id,
        "package_id": target.package_id,
        "target_name": target.target_name,
        "os_name": target.os_name,
        "arch_name": target.arch_name,
        "artifact_format": target.artifact_format,
        "jni_enabled": target.jni_enabled,
        "status": target.status,
        "output_dir": target.output_dir,
        "binary_path": target.binary_path,
        "manifest_path": target.manifest_path,
        "checksum": target.checksum,
        "log_path": target.log_path,
        "download_archive_path": target.download_archive_path,
        "artifacts": [_artifact_item(item) for item in target.artifacts],
    }


def list_sdk_packages(session: Session) -> list[dict[str, object]]:
    rows = session.query(SdkPackageModel).order_by(SdkPackageModel.id.asc()).all()
    return [_package_item(item) for item in rows]


def get_sdk_package(session: Session, package_id: int) -> dict[str, object]:
    package = session.get(SdkPackageModel, package_id)
    if package is None:
        raise SdkPackageNotFoundError("SDK 包不存在。")
    payload = _package_item(package)
    payload["targets"] = [_target_item(item) for item in package.targets]
    payload["manifest"] = (
        json.loads(Path(package.manifest_path).read_text(encoding="utf-8"))
        if package.manifest_path and Path(package.manifest_path).exists()
        else None
    )
    return payload


def get_sdk_target(session: Session, target_id: int) -> dict[str, object]:
    target = session.get(SdkTargetModel, target_id)
    if target is None:
        raise SdkTargetNotFoundError("SDK 目标不存在。")
    return _target_item(target)


def _scan_models(models_root: Path) -> dict[str, list[str]]:
    capability_versions: dict[str, list[str]] = {}
    if not models_root.exists():
        return capability_versions
    for capability_dir in sorted([item for item in models_root.iterdir() if item.is_dir()], key=lambda item: item.name):
        versions = sorted([item.name for item in capability_dir.iterdir() if item.is_dir()])
        if versions:
            capability_versions[capability_dir.name] = versions
    return capability_versions


def _scan_lib_targets(libs_root: Path) -> dict[str, dict[str, dict[str, bool]]]:
    result: dict[str, dict[str, dict[str, bool]]] = {}
    if not libs_root.exists():
        return result
    for target_name in SUPPORTED_TARGETS:
        target_root = libs_root / target_name
        if not target_root.exists():
            continue
        for capability_dir in sorted([item for item in target_root.iterdir() if item.is_dir()], key=lambda item: item.name):
            result.setdefault(capability_dir.name, {})[target_name] = {
                "jni_available": (capability_dir / "jni").exists(),
            }
    return result


def get_sdk_catalog(libs_root: Path, models_root: Path) -> dict[str, object]:
    models = _scan_models(models_root)
    lib_targets = _scan_lib_targets(libs_root)
    capabilities: list[dict[str, object]] = []
    for capability_name in sorted(set(models) | set(lib_targets)):
        target_map = lib_targets.get(capability_name, {})
        capabilities.append(
            {
                "capability_name": capability_name,
                "model_versions": models.get(capability_name, []),
                "available_targets": sorted(target_map),
                "jni_available_targets": sorted(
                    [target_name for target_name, payload in target_map.items() if payload["jni_available"]]
                ),
            }
        )
    return {"capabilities": capabilities}


def _copy_tree_contents(source_dir: Path, destination_dir: Path) -> None:
    destination_dir.mkdir(parents=True, exist_ok=True)
    for item in source_dir.iterdir():
        destination = destination_dir / item.name
        if item.is_dir():
            shutil.copytree(item, destination, dirs_exist_ok=True)
        else:
            shutil.copy2(item, destination)


def _render_error_codes_header() -> str:
    return """#pragma once

#define AI_SDK_SUCCESS 0
#define AI_SDK_ERROR_INVALID_ARGUMENT -1
#define AI_SDK_ERROR_BUFFER_TOO_SMALL -2
#define AI_SDK_ERROR_LICENSE_INVALID -10
#define AI_SDK_ERROR_MODEL_LOAD_FAILED -20
#define AI_SDK_ERROR_RUNTIME_FAILURE -30
"""


def _render_threading_header() -> str:
    return """#pragma once

/*
 * 单机交付 SDK 线程安全约束：
 * 1. 同一能力实例可被并发调用，但调用方需保证输入输出缓冲区互不共享。
 * 2. 初始化与销毁阶段不得与推理并发执行。
 * 3. GPU 优先、GPU 不可用时允许自动回退 CPU。
 */
"""


def _render_package_readme(capability_name: str, model_version: str, target_name: str, jni_enabled: bool) -> str:
    jni_text = "包含 JNI 库与 Java 示例。" if jni_enabled else "未包含 JNI 层。"
    return f"""# {capability_name} 单机交付包说明

## 1. 交付范围

1. `lib/`：动态库
2. `include/`：能力头文件与共享错误码头文件
3. `model/`：模型包与 manifest
4. `license/`：license 与公钥
5. `examples/`：C/C++ 与可选 Java 示例
6. `docs/`：接入说明与错误码说明

## 2. 当前版本

- capability: `{capability_name}`
- model_version: `{model_version}`
- target: `{target_name}`
- JNI: {'启用' if jni_enabled else '关闭'}

## 3. 生命周期

1. 调用 `ai_builder_get_abi_version` 校验 ABI 版本。
2. 通过能力头文件中的 `*_predict` 接口发起推理。
3. 输出缓冲区由调用方申请并负责释放。

## 4. 错误码

请参见 `include/ai_sdk_error_codes.h` 与 `docs/ERROR_CODES.md`。

## 5. 线程安全

请参见 `include/ai_sdk_threading.h`。默认要求调用方隔离每次调用的输入输出缓冲区。

## 6. GPU / CPU

SDK 与生产 runtime 协议兼容，遵循 GPU 优先、CPU 自动回退原则。

## 7. JNI

{jni_text}
"""


def _render_acceptance_checklist(capability_name: str, model_version: str, target_name: str, jni_enabled: bool) -> str:
    return "\n".join(
        [
            "# ACCEPTANCE_CHECKLIST",
            "",
            f"- capability: `{capability_name}`",
            f"- model_version: `{model_version}`",
            f"- target: `{target_name}`",
            "",
            "1. 核对 `lib/`、`include/`、`models/`、`licenses/`、`docs/`、`examples/` 目录齐全。",
            "2. 校验 `manifest/manifest.json` 与 `checksums.txt` 可读且内容完整。",
            "3. 参考 `docs/README_集成说明.md` 编译并运行示例工程。",
            "4. 使用 `tools/license_tool/README.md` 中说明构建并执行 `license_tool verify`。",
            "5. 核对 `tools/license_tool/LICENSE_DIAGNOSTICS.json` 与 `tools/license_tool/VALIDATION_VECTORS.json`。",
            "6. 运行 `validation/verify_sdk_package.py <sdk_dir>` 完成标准目录快速校验。",
            f"7. {'核对 jni/ 目录与 Java 示例。' if jni_enabled else '确认当前目标无需 JNI 目录。'}",
            "",
        ]
    )


def _render_deployment_guide(capability_name: str, model_version: str, target_name: str) -> str:
    return "\n".join(
        [
            "# DEPLOYMENT_GUIDE",
            "",
            f"- capability: `{capability_name}`",
            f"- model_version: `{model_version}`",
            f"- target: `{target_name}`",
            "",
            "## 推荐部署步骤",
            "",
            "1. 将 `lib/`、`include/`、`models/`、`licenses/` 与 `tools/` 一并下发到目标环境。",
            "2. 按 `docs/README_集成说明.md` 完成 ABI 校验、初始化与推理接入。",
            "3. 如需现场核验授权，先构建 `tools/license_tool`，再执行 `license_tool verify`。",
            "4. 如需接入稳定授权诊断，请同步分发 `tools/license_tool/LICENSE_DIAGNOSTICS.json` 与 `VALIDATION_VECTORS.json`。",
            "5. 交付验收前执行 `validation/verify_sdk_package.py` 与示例工程编译校验。",
            "",
        ]
    )


def _render_license_tool_integration_doc(target_name: str) -> str:
    return "\n".join(
        [
            "# LICENSE_TOOL",
            "",
            f"当前目标 `{target_name}` 已附带标准 `tools/license_tool` source bundle。",
            "",
            "## 构建",
            "",
            "```bash",
            "cd tools/license_tool",
            "cmake -S . -B build",
            "cmake --build build --parallel",
            "```",
            "",
            "## 校验示例",
            "",
            "```bash",
            "./build/license_tool verify ../../licenses/license.bin",
            "```",
            "",
            "稳定诊断字段与结果码定义见 `tools/license_tool/LICENSE_DIAGNOSTICS.json`，金标准测试向量见 `tools/license_tool/VALIDATION_VECTORS.json`。",
            "",
            "如需生成或预计算硬件指纹，请继续参考 `tools/license_tool/HARDWARE_FINGERPRINT.md`。",
            "",
        ]
    )


def _render_error_codes_doc() -> str:
    return """# SDK 错误码说明

| 错误码 | 含义 | 说明 |
| --- | --- | --- |
| 0 | 成功 | 调用成功 |
| -1 | 参数非法 | 输入 JSON、缓冲区或指针为空 |
| -2 | 输出缓冲区不足 | 需要扩大输出缓冲区后重试 |
| -10 | license 校验失败 | license 无效、过期或范围不匹配 |
| -20 | 模型装载失败 | 模型目录或 manifest 不可用 |
| -30 | 运行时失败 | runtime 初始化、执行或资源切换失败 |
"""


def _render_c_example(capability_name: str) -> str:
    return f"""#include <stdio.h>
#include <string.h>

#include "{capability_name}.h"
#include "ai_sdk_error_codes.h"

int main(void) {{
  char output[1024] = {{0}};
  const char* input = "{{\\\"image\\\":\\\"demo\\\"}}";
  int code = {capability_name}_predict(input, output, sizeof(output));
  if (code != AI_SDK_SUCCESS) {{
    fprintf(stderr, "predict failed: %d\\n", code);
    return 1;
  }}
  printf("abi=%d\\n", ai_builder_get_abi_version());
  printf("capability=%s\\n", ai_builder_get_capability_name());
  printf("model=%s\\n", ai_builder_get_model_version());
  printf("output=%s\\n", output);
  return 0;
}}
"""


def _render_cpp_example(capability_name: str) -> str:
    return f"""cmake_minimum_required(VERSION 3.18)
project({capability_name}_sdk_example LANGUAGES C CXX)

add_executable({capability_name}_sdk_example sample_c_api.c)
target_include_directories({capability_name}_sdk_example PRIVATE ../include)
"""


def _render_java_example(capability_name: str) -> str:
    class_name = "".join(part.capitalize() for part in capability_name.split("_")) + "NativeBridge"
    method_suffix = capability_name
    return f"""package cn.agilestar.ai.{capability_name};

public final class {class_name} {{
  static {{
    System.loadLibrary("{method_suffix}_jni");
  }}

  private {class_name}() {{
  }}

  public static native int ping();
}}
"""


def _copy_license_tool_bundle(destination_dir: Path) -> None:
    destination_dir.mkdir(parents=True, exist_ok=True)
    destination_root = destination_dir.resolve()
    for relative_path, source_path in LICENSE_TOOL_SOURCE_FILES.items():
        copy_to = (destination_root / relative_path).resolve()
        if not (copy_to == destination_root or destination_root in copy_to.parents):
            raise ValueError("license_tool source file destination is invalid.")
        copy_to.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_path, copy_to)
    _write_text(destination_dir / "VERSION", LICENSE_TOOL_VERSION + "\n")
    _write_text(destination_dir / "LICENSE_DIAGNOSTICS.json", json.dumps(build_validation_contract(), ensure_ascii=False, indent=2, sort_keys=True))
    _write_text(destination_dir / "VALIDATION_VECTORS.json", json.dumps(build_validation_vectors(), ensure_ascii=False, indent=2, sort_keys=True))
    _write_text(
        destination_dir / "manifest.json",
        json.dumps(
            {
                "tool_name": "license_tool",
                "version": LICENSE_TOOL_VERSION,
                "bundle_format": "source_bundle",
                "build_command": "cmake -S . -B build && cmake --build build --parallel",
                "diagnostics_version": DIAGNOSTICS_VERSION,
                "source_files": sorted(LICENSE_TOOL_SOURCE_FILES),
                "documents": ["README.md", "ERROR_CODES.md", "HARDWARE_FINGERPRINT.md", "LICENSE_DIAGNOSTICS.json", "VALIDATION_VECTORS.json"],
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        ),
    )
    _write_text(
        destination_dir / "README.md",
        "\n".join(
            [
                "# license_tool",
                "",
                f"- 版本：`{LICENSE_TOOL_VERSION}`",
                "- 交付形态：标准 C++ source bundle",
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
                "## 稳定诊断契约",
                "",
                f"- 诊断契约版本：`{DIAGNOSTICS_VERSION}`",
                "- 稳定字段定义见 `LICENSE_DIAGNOSTICS.json`。",
                "- 金标准测试向量见 `VALIDATION_VECTORS.json`。",
                "",
            ]
        ),
    )
    _write_text(
        destination_dir / "ERROR_CODES.md",
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
        destination_dir / "HARDWARE_FINGERPRINT.md",
        "\n".join(
            [
                "# HARDWARE_FINGERPRINT",
                "",
                "硬件指纹采用 `key=value` 形式按 key 排序后，以 `|` 连接并计算 SHA256。",
                "",
                "```text",
                "cpu=intel-i7|disk=nvme-sn-001|mac=00:11:22:33:44:55",
                "```",
                "",
            ]
        ),
    )


def _write_verify_sdk_package_script(validation_dir: Path) -> None:
    _write_text(
        validation_dir / "verify_sdk_package.py",
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
                "    parser = argparse.ArgumentParser(description='Verify ai-sdk package skeleton.')",
                "    parser.add_argument('sdk_root')",
                "    args = parser.parse_args()",
                "    sdk_root = Path(args.sdk_root).resolve()",
                "    required = [",
                "        'lib',",
                "        'include',",
                "        'models',",
                "        'licenses',",
                "        'docs',",
                "        'examples',",
                "        'tools/license_tool/manifest.json',",
                "        'tools/license_tool/LICENSE_DIAGNOSTICS.json',",
                "        'tools/license_tool/VALIDATION_VECTORS.json',",
                "        'validation/verify_sdk_package.py',",
                "        'manifest/manifest.json',",
                "        'checksums.txt',",
                "    ]",
                "    missing = [item for item in required if not (sdk_root / item).exists()]",
                "    if missing:",
                "        print(f'missing paths: {missing}', file=sys.stderr)",
                "        return 1",
                "    print('sdk package verified')",
                "    return 0",
                "",
                "",
                "if __name__ == '__main__':",
                "    raise SystemExit(main())",
                "",
            ]
        ),
    )


def _write_checksums(root_dir: Path) -> None:
    lines: list[str] = []
    for file_path in sorted([item for item in root_dir.rglob("*") if item.is_file()], key=lambda item: str(item)):
        if file_path.name == "checksums.txt":
            continue
        lines.append(f"{_sha256_file(file_path)}  {file_path.relative_to(root_dir)}")
    _write_text(root_dir / "checksums.txt", "\n".join(lines) + ("\n" if lines else ""))


def _delivery_file_entry(path: Path, package_root: Path) -> dict[str, object]:
    return {
        "path": str(path.relative_to(package_root)),
        "checksum": _sha256_file(path),
        "size_bytes": path.stat().st_size,
    }


def _sdk_docs_bundle(package_targets: list[dict[str, object]]) -> dict[str, object]:
    documents: list[str] = []
    for target in package_targets:
        sdk_dir_name = STANDARD_SDK_DIR_NAMES[str(target["target_name"])]
        for document_name in (
            "README_集成说明.md",
            "ERROR_CODES.md",
            "ACCEPTANCE_CHECKLIST.md",
            "DEPLOYMENT_GUIDE.md",
            "LICENSE_TOOL.md",
        ):
            documents.append(f"{sdk_dir_name}/docs/{document_name}")
    return {"documents": documents}


def _sdk_tools_bundle(package_targets: list[dict[str, object]]) -> dict[str, object]:
    validation_scripts: list[str] = []
    license_tool_manifests: list[str] = []
    for target in package_targets:
        sdk_dir_name = STANDARD_SDK_DIR_NAMES[str(target["target_name"])]
        validation_scripts.append(f"{sdk_dir_name}/validation/verify_sdk_package.py")
        license_tool_manifests.append(f"{sdk_dir_name}/tools/license_tool/manifest.json")
    return {
        "validation_scripts": validation_scripts,
        "license_tool_manifests": license_tool_manifests,
    }


def _create_sdk_acceptance_checklist(
    package_root: Path,
    *,
    package_id: int,
    package_name: str,
    capability_name: str,
    model_version: str,
    requested_targets: list[str],
    jni_enabled: bool,
) -> dict[str, object]:
    sections: list[dict[str, object]] = [
        {
            "section_name": "交付概览",
            "items": [
                {
                    "item_id": "S01-I01",
                    "description": f"确认 package_name=`{package_name}` 与 capability/model 组合正确",
                    "status": "pending",
                },
                {
                    "item_id": "S01-I02",
                    "description": f"确认交付目标覆盖：{', '.join(requested_targets)}",
                    "status": "pending",
                },
                {
                    "item_id": "S01-I03",
                    "description": f"确认 JNI 交付状态：{'启用' if jni_enabled else '关闭'}",
                    "status": "pending",
                },
            ],
        }
    ]
    required_paths = [
        "lib",
        "include",
        "models",
        "licenses",
        "docs",
        "examples",
        "tools/license_tool/manifest.json",
        "tools/license_tool/LICENSE_DIAGNOSTICS.json",
        "tools/license_tool/VALIDATION_VECTORS.json",
        "validation/verify_sdk_package.py",
        "manifest/manifest.json",
        "checksums.txt",
    ]
    for section_index, target_name in enumerate(requested_targets, start=2):
        items = [
            {
                "item_id": f"S{section_index:02d}-I{item_index:02d}",
                "description": f"`{STANDARD_SDK_DIR_NAMES[target_name]}/{relative_path}` 已生成并可读",
                "status": "pending",
            }
            for item_index, relative_path in enumerate(required_paths, start=1)
        ]
        if jni_enabled:
            items.append(
                {
                    "item_id": f"S{section_index:02d}-I{len(items) + 1:02d}",
                    "description": f"`{STANDARD_SDK_DIR_NAMES[target_name]}/jni` 与 Java 示例已生成",
                    "status": "pending",
                }
            )
        sections.append({"section_name": f"目标平台 `{target_name}`", "items": items})
    final_section_index = len(sections) + 1
    sections.append(
        {
            "section_name": "现场验收",
            "items": [
                {
                    "item_id": f"S{final_section_index:02d}-I01",
                    "description": "按 `version_manifest.json` 核对关键文件与 checksum。",
                    "status": "pending",
                },
                {
                    "item_id": f"S{final_section_index:02d}-I02",
                    "description": "在目标环境执行 `validation/verify_sdk_package.py`。",
                    "status": "pending",
                },
                {
                    "item_id": f"S{final_section_index:02d}-I03",
                    "description": "构建并运行 `tools/license_tool`，完成授权校验留痕。",
                    "status": "pending",
                },
            ],
        }
    )
    checklist = {
        "package_id": package_id,
        "package_name": package_name,
        "capability_name": capability_name,
        "model_version": model_version,
        "source_document": "docs/README_集成说明.md",
        "requested_targets": requested_targets,
        "sections": sections,
    }
    _write_text(
        package_root / "acceptance_checklist.json",
        json.dumps(checklist, ensure_ascii=False, indent=2, sort_keys=True),
    )
    return checklist


def _create_version_manifest(
    package_root: Path,
    *,
    package_id: int,
    package_name: str,
    capability_name: str,
    model_version: str,
    requested_targets: list[str],
    jni_enabled: bool,
    package_targets: list[dict[str, object]],
) -> dict[str, object]:
    checksum_entries: list[dict[str, object]] = []
    for target in package_targets:
        output_dir = Path(str(target["output_dir"]))
        for relative_path in (
            "manifest/manifest.json",
            "checksums.txt",
            "docs/README_集成说明.md",
            "docs/ERROR_CODES.md",
            "docs/ACCEPTANCE_CHECKLIST.md",
            "docs/DEPLOYMENT_GUIDE.md",
            "docs/LICENSE_TOOL.md",
            "tools/license_tool/manifest.json",
            "tools/license_tool/LICENSE_DIAGNOSTICS.json",
            "tools/license_tool/VALIDATION_VECTORS.json",
            "validation/verify_sdk_package.py",
        ):
            file_path = output_dir / relative_path
            if file_path.is_file():
                checksum_entries.append(_delivery_file_entry(file_path, package_root))

    version_manifest = {
        "package_id": package_id,
        "package_name": package_name,
        "capability_name": capability_name,
        "model_version": model_version,
        "requested_targets": requested_targets,
        "delivery_targets": requested_targets,
        "jni_enabled": jni_enabled,
        "sdk_items": [
            {
                "target_name": target["target_name"],
                "sdk_dir_name": STANDARD_SDK_DIR_NAMES[str(target["target_name"])],
                "binary_path": target["binary_path"],
                "manifest_path": target["manifest_path"],
                "download_archive_path": target["download_archive_path"],
                "checksum": target["checksum"],
            }
            for target in package_targets
        ],
        "delivery_checksums": checksum_entries,
        "docs_bundle": _sdk_docs_bundle(package_targets),
        "tools_bundle": _sdk_tools_bundle(package_targets),
    }
    _write_text(
        package_root / "version_manifest.json",
        json.dumps(version_manifest, ensure_ascii=False, indent=2, sort_keys=True),
    )
    return version_manifest


def _create_delivery_summary(
    package_root: Path,
    *,
    package_id: int,
    package_name: str,
    capability_name: str,
    model_version: str,
    requested_targets: list[str],
    jni_enabled: bool,
    acceptance_checklist: dict[str, object],
    version_manifest: dict[str, object],
) -> dict[str, object]:
    summary = {
        "package_id": package_id,
        "package_name": package_name,
        "capability_name": capability_name,
        "model_version": model_version,
        "requested_targets": requested_targets,
        "jni_enabled": jni_enabled,
        "target_count": len(requested_targets),
        "acceptance_section_count": len(acceptance_checklist.get("sections", [])),
        "delivery_files": [
            "acceptance_checklist.json",
            "version_manifest.json",
            "delivery_summary.json",
            "delivery_summary.md",
        ],
        "delivery_directories": sorted(item.name for item in package_root.iterdir() if item.is_dir()),
        "recommended_steps": [
            "核对 acceptance_checklist.json 并按目标平台逐项验收。",
            "核对 version_manifest.json 中 capability/model/target/checksum 是否与现场交付一致。",
            "进入对应 sdk_* 目录执行 validation/verify_sdk_package.py 快速校验目录完整性。",
            "参考 docs/ 与 examples/ 完成 SDK 接入、license_tool 构建与验收留痕。",
        ],
        "version_manifest_path": "version_manifest.json",
        "checksum_entry_count": len(version_manifest.get("delivery_checksums", [])),
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
                f"- package_id: {package_id}",
                f"- package_name: {package_name}",
                f"- capability_name: {capability_name}",
                f"- model_version: {model_version}",
                f"- requested_targets: {', '.join(requested_targets)}",
                f"- jni_enabled: {jni_enabled}",
                f"- checksum_entry_count: {len(version_manifest.get('delivery_checksums', []))}",
                "",
                "## 交付物摘要",
                "",
                "- 已生成验收清单：`acceptance_checklist.json`",
                "- 已生成版本清单：`version_manifest.json`",
                "- 已生成交付摘要：`delivery_summary.json` / `delivery_summary.md`",
                "",
                "## 推荐下一步",
                "",
                "1. 按 acceptance_checklist.json 核对每个 sdk_* 目录。",
                "2. 按 version_manifest.json 复核目标平台、关键文件与 checksum。",
                "3. 在目标环境构建并运行 tools/license_tool。",
                "4. 参考 docs/ 与 examples/ 完成接入演练并归档结果。",
                "",
            ]
        ),
    )
    return summary


def _register_artifact(
    session: Session,
    *,
    package_id: int,
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
        SdkArtifactModel(
            package_id=package_id,
            target_id=target_id,
            artifact_type=artifact_type,
            relative_path=relative_path,
            absolute_path=str(absolute_path.resolve()),
            checksum=_sha256_file(absolute_path) if absolute_path.is_file() else hashlib.sha256(str(absolute_path).encode("utf-8")).hexdigest(),
        )
    )


def create_sdk_package(
    session: Session,
    *,
    sdk_packages_root: Path,
    sdk_logs_root: Path,
    libs_root: Path,
    models_root: Path,
    exports_root: Path,
    audit_log_path: Path,
    package_name: str,
    capability_name: str,
    model_version: str,
    requested_targets: list[str],
    jni_enabled: bool,
) -> dict[str, object]:
    safe_package_name = package_name.strip()
    if not safe_package_name:
        raise ValueError("package_name 不能为空。")
    safe_capability_name = _normalize_slug(capability_name, field_name="capability_name")
    safe_model_version = _normalize_slug(model_version, field_name="model_version")
    normalized_targets = requested_targets or ["linux_x86_64"]
    if not normalized_targets:
        raise ValueError("至少需要一个交付目标。")
    for target_name in normalized_targets:
        if target_name not in SUPPORTED_TARGETS:
            raise ValueError(f"不支持的交付目标：{target_name}")

    model_root = (models_root / safe_capability_name / safe_model_version).resolve()
    if not model_root.exists():
        raise ValueError("未找到匹配模型目录，请先确认 ai-train 模型产物已落盘。")

    package = SdkPackageModel(
        package_name=safe_package_name,
        capability_name=safe_capability_name,
        model_version=safe_model_version,
        requested_targets_json=json.dumps(sorted(set(normalized_targets)), ensure_ascii=False, sort_keys=True),
        jni_enabled=jni_enabled,
        status="running",
        package_root_path="",
        log_path="",
        manifest_path="",
        started_at=datetime.now(UTC).replace(tzinfo=None),
    )
    session.add(package)
    session.commit()
    session.refresh(package)

    package_root = (sdk_packages_root / f"package_{package.id}").resolve()
    if not (package_root == sdk_packages_root or sdk_packages_root in package_root.parents):
        raise ValueError("SDK 包目录非法。")
    package_root.mkdir(parents=True, exist_ok=True)
    package_log_path = (sdk_logs_root / f"package_{package.id}.log").resolve()
    _append_log(package_log_path, f"开始生成 SDK 包 #{package.id}")

    package.package_root_path = str(package_root)
    package.log_path = str(package_log_path)
    session.commit()

    package_targets: list[dict[str, object]] = []

    for target_name in sorted(set(normalized_targets)):
        target_config = SUPPORTED_TARGETS[target_name]
        source_root = (libs_root / target_name / safe_capability_name).resolve()
        if not source_root.exists():
            raise ValueError(f"未找到 {target_name}/{safe_capability_name} 的 ai-builder 交付目录。")

        sdk_dir_name = STANDARD_SDK_DIR_NAMES[target_name]
        output_dir = (package_root / sdk_dir_name).resolve()
        if not (output_dir == package_root or package_root in output_dir.parents):
            raise ValueError("SDK 输出目录非法。")
        output_dir.mkdir(parents=True, exist_ok=True)

        lib_dir = output_dir / "lib"
        include_dir = output_dir / "include"
        model_dir = output_dir / "models"
        license_dir = output_dir / "licenses"
        docs_dir = output_dir / "docs"
        examples_dir = output_dir / "examples"
        jni_dir = output_dir / "jni"
        tools_dir = output_dir / "tools"
        validation_dir = output_dir / "validation"
        manifest_dir = output_dir / "manifest"
        for directory in (lib_dir, include_dir, model_dir, license_dir, docs_dir, examples_dir, tools_dir, validation_dir, manifest_dir):
            directory.mkdir(parents=True, exist_ok=True)

        source_lib_dir = source_root / "lib"
        source_include_dir = source_root / "include"
        source_license_dir = source_root / "license"
        source_jni_dir = source_root / "jni"
        if not source_lib_dir.exists() or not source_include_dir.exists() or not source_license_dir.exists():
            raise ValueError("ai-builder 交付目录缺少 lib/include/license 标准子目录。")

        _copy_tree_contents(source_lib_dir, lib_dir)
        _copy_tree_contents(source_include_dir, include_dir)
        _copy_tree_contents(source_license_dir, license_dir)
        shutil.copytree(model_root, model_dir, dirs_exist_ok=True)

        if jni_enabled:
            if not source_jni_dir.exists():
                raise ValueError(f"{target_name}/{safe_capability_name} 缺少 JNI 产物，请先通过 ai-builder 启用 JNI 构建。")
            jni_dir.mkdir(parents=True, exist_ok=True)
            _copy_tree_contents(source_jni_dir, jni_dir)

        _write_text(include_dir / "ai_sdk_error_codes.h", _render_error_codes_header())
        _write_text(include_dir / "ai_sdk_threading.h", _render_threading_header())
        _write_text(docs_dir / "README_集成说明.md", _render_package_readme(safe_capability_name, safe_model_version, target_name, jni_enabled))
        _write_text(docs_dir / "ERROR_CODES.md", _render_error_codes_doc())
        _write_text(
            docs_dir / "ACCEPTANCE_CHECKLIST.md",
            _render_acceptance_checklist(safe_capability_name, safe_model_version, target_name, jni_enabled),
        )
        _write_text(docs_dir / "DEPLOYMENT_GUIDE.md", _render_deployment_guide(safe_capability_name, safe_model_version, target_name))
        _write_text(docs_dir / "LICENSE_TOOL.md", _render_license_tool_integration_doc(target_name))
        _write_text(examples_dir / "sample_c_api.c", _render_c_example(safe_capability_name))
        _write_text(examples_dir / "CMakeLists.txt", _render_cpp_example(safe_capability_name))
        if jni_enabled:
            _write_text(examples_dir / "NativeBridge.java", _render_java_example(safe_capability_name))
        _copy_license_tool_bundle(tools_dir / "license_tool")
        _write_verify_sdk_package_script(validation_dir)

        source_manifest_path = source_root / "manifest" / "manifest.json"
        source_manifest = json.loads(source_manifest_path.read_text(encoding="utf-8")) if source_manifest_path.exists() else {}
        sdk_manifest = {
            "package_id": package.id,
            "package_name": safe_package_name,
            "capability_name": safe_capability_name,
            "model_version": safe_model_version,
            "target_name": target_name,
            "sdk_dir_name": sdk_dir_name,
            "artifact_format": target_config["artifact_format"],
            "jni_enabled": jni_enabled,
            "source_builder_manifest": source_manifest,
            "delivery_content": [
                "lib",
                "include",
                "models",
                "licenses",
                "docs",
                "examples",
                "tools/license_tool",
                "validation",
                "manifest",
            ]
            + (["jni"] if jni_enabled else []),
            "abi_compatibility": "ai-builder / ai-prod v1",
            "thread_safe": True,
            "gpu_fallback": True,
            "delivery_package_alignment": {
                "sdk_dir": sdk_dir_name,
                "stage_status": {"S7": "completed", "S8": "completed", "S9": "completed", "S10": "completed", "S11": "completed", "S12": "completed"},
            },
        }
        sdk_manifest_path = manifest_dir / "manifest.json"
        _write_text(sdk_manifest_path, json.dumps(sdk_manifest, ensure_ascii=False, indent=2, sort_keys=True))
        _write_checksums(output_dir)

        binary_candidates = sorted([item for item in lib_dir.iterdir() if item.is_file()], key=lambda item: item.name)
        if not binary_candidates:
            raise ValueError("lib 目录中未找到动态库文件。")
        binary_path = binary_candidates[0]

        target_log_path = output_dir / "build.log"
        _append_log(target_log_path, f"target={target_name}")
        _append_log(target_log_path, f"binary={binary_path.name}")
        archive_path = _archive_directory(output_dir, exports_root / "ai-sdk" / f"package_{package.id}_{target_name}")
        checksum = _sha256_file(binary_path)

        target_row = SdkTargetModel(
            package_id=package.id,
            target_name=target_name,
            os_name=str(target_config["os_name"]),
            arch_name=str(target_config["arch_name"]),
            artifact_format=str(target_config["artifact_format"]),
            jni_enabled=jni_enabled,
            status="completed",
            output_dir=str(output_dir),
            binary_path=str(binary_path),
            manifest_path=str(sdk_manifest_path),
            checksum=checksum,
            log_path=str(target_log_path),
            download_archive_path=str(archive_path),
        )
        session.add(target_row)
        session.commit()
        session.refresh(target_row)

        for artifact_type, artifact_path in (
            ("binary", binary_path),
            ("manifest", sdk_manifest_path),
            ("checksums", output_dir / "checksums.txt"),
            ("doc", docs_dir / "README_集成说明.md"),
            ("doc", docs_dir / "ERROR_CODES.md"),
            ("doc", docs_dir / "ACCEPTANCE_CHECKLIST.md"),
            ("doc", docs_dir / "DEPLOYMENT_GUIDE.md"),
            ("doc", docs_dir / "LICENSE_TOOL.md"),
            ("example", examples_dir / "sample_c_api.c"),
            ("example", examples_dir / "CMakeLists.txt"),
            ("tool", tools_dir / "license_tool" / "manifest.json"),
            ("tool", tools_dir / "license_tool" / "LICENSE_DIAGNOSTICS.json"),
            ("tool", tools_dir / "license_tool" / "VALIDATION_VECTORS.json"),
            ("validation", validation_dir / "verify_sdk_package.py"),
            ("archive", archive_path),
        ):
            _register_artifact(
                session,
                package_id=package.id,
                target_id=target_row.id,
                artifact_type=artifact_type,
                output_dir=output_dir,
                absolute_path=artifact_path,
            )
        for include_path in include_dir.iterdir():
            if include_path.is_file():
                _register_artifact(
                    session,
                    package_id=package.id,
                    target_id=target_row.id,
                    artifact_type="header",
                    output_dir=output_dir,
                    absolute_path=include_path,
                )
        if jni_enabled:
            _register_artifact(
                session,
                package_id=package.id,
                target_id=target_row.id,
                artifact_type="example",
                output_dir=output_dir,
                absolute_path=examples_dir / "NativeBridge.java",
            )
            for jni_path in jni_dir.iterdir():
                if jni_path.is_file():
                    _register_artifact(
                        session,
                        package_id=package.id,
                        target_id=target_row.id,
                        artifact_type="jni",
                        output_dir=output_dir,
                        absolute_path=jni_path,
                    )
        session.commit()
        package_targets.append(_target_item(target_row))

    package_manifest = {
        "package_id": package.id,
        "package_name": safe_package_name,
        "capability_name": safe_capability_name,
        "model_version": safe_model_version,
        "requested_targets": sorted(set(normalized_targets)),
        "jni_enabled": jni_enabled,
        "stage_status": {"S7": "completed", "S8": "completed", "S9": "completed", "S10": "completed", "S11": "completed", "S12": "completed"},
        "delivery_package_alignment": True,
        "targets": [
            {
                "target_name": item["target_name"],
                "sdk_dir_name": STANDARD_SDK_DIR_NAMES[str(item["target_name"])],
                "binary_path": item["binary_path"],
                "manifest_path": item["manifest_path"],
                "download_archive_path": item["download_archive_path"],
            }
            for item in package_targets
        ],
    }
    _write_text(
        package_root / "README.md",
        "\n".join(
            [
                "# ai-sdk delivery package",
                "",
                f"- package_name: `{safe_package_name}`",
                f"- capability_name: `{safe_capability_name}`",
                f"- model_version: `{safe_model_version}`",
                "- 当前目录已按统一 `sdk_*` 规范输出 Linux/JNI/Windows SDK、license_tool、验收文档与快速校验脚本。",
                "",
            ]
        ),
    )
    acceptance_checklist = _create_sdk_acceptance_checklist(
        package_root,
        package_id=package.id,
        package_name=safe_package_name,
        capability_name=safe_capability_name,
        model_version=safe_model_version,
        requested_targets=sorted(set(normalized_targets)),
        jni_enabled=jni_enabled,
    )
    version_manifest = _create_version_manifest(
        package_root,
        package_id=package.id,
        package_name=safe_package_name,
        capability_name=safe_capability_name,
        model_version=safe_model_version,
        requested_targets=sorted(set(normalized_targets)),
        jni_enabled=jni_enabled,
        package_targets=package_targets,
    )
    delivery_summary = _create_delivery_summary(
        package_root,
        package_id=package.id,
        package_name=safe_package_name,
        capability_name=safe_capability_name,
        model_version=safe_model_version,
        requested_targets=sorted(set(normalized_targets)),
        jni_enabled=jni_enabled,
        acceptance_checklist=acceptance_checklist,
        version_manifest=version_manifest,
    )
    package_manifest_path = package_root / "package_manifest.json"
    package_manifest["version_manifest_path"] = "version_manifest.json"
    package_manifest["delivery_summary"] = delivery_summary
    _write_text(package_manifest_path, json.dumps(package_manifest, ensure_ascii=False, indent=2, sort_keys=True))

    package.status = "completed"
    package.manifest_path = str(package_manifest_path)
    package.completed_at = datetime.now(UTC).replace(tzinfo=None)
    session.commit()

    append_audit_log(
        audit_log_path,
        action="create_sdk_package",
        entity_type="sdk_package",
        entity_id=str(package.id),
        detail={
            "capability_name": safe_capability_name,
            "model_version": safe_model_version,
            "requested_targets": sorted(set(normalized_targets)),
            "jni_enabled": jni_enabled,
        },
    )

    return get_sdk_package(session, package.id)
