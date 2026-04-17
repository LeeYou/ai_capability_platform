from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any


ALLOWED_EXECUTION_MODES = {"real", "simulated"}
ALLOWED_REPORT_TEMPLATE_TYPES = {"research", "delivery"}
ALLOWED_LICENSE_TOOL_BUNDLE_FORMATS = {"source_bundle"}
ALLOWED_LICENSE_TOOL_BUILD_SYSTEMS = {"cmake"}


def _require_non_empty_string(payload: Mapping[str, Any], field_name: str) -> str:
    value = payload.get(field_name)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} 必须为非空字符串。")
    return value.strip()


def _require_existing_path(payload: Mapping[str, Any], field_name: str) -> str:
    path_text = _require_non_empty_string(payload, field_name)
    path = Path(path_text)
    if not path.exists():
        raise ValueError(f"{field_name} 指向的路径不存在。")
    return str(path.resolve())


def _require_mapping(payload: Mapping[str, Any], field_name: str) -> Mapping[str, Any]:
    value = payload.get(field_name)
    if not isinstance(value, Mapping):
        raise ValueError(f"{field_name} 必须为对象。")
    return value


def _require_list(payload: Mapping[str, Any], field_name: str) -> list[Any]:
    value = payload.get(field_name)
    if not isinstance(value, list):
        raise ValueError(f"{field_name} 必须为数组。")
    return value


def _require_non_negative_int(payload: Mapping[str, Any], field_name: str) -> int:
    value = payload.get(field_name)
    if not isinstance(value, int) or value < 0:
        raise ValueError(f"{field_name} 必须为非负整数。")
    return value


def _require_non_empty_string_list(payload: Mapping[str, Any], field_name: str) -> list[str]:
    items = _require_list(payload, field_name)
    if not items:
        raise ValueError(f"{field_name} 必须为非空数组。")
    normalized: list[str] = []
    for index, item in enumerate(items):
        if not isinstance(item, str) or not item.strip():
            raise ValueError(f"{field_name}[{index}] 必须为非空字符串。")
        normalized.append(item.strip())
    return normalized


def _require_bool(payload: Mapping[str, Any], field_name: str) -> bool:
    value = payload.get(field_name)
    if not isinstance(value, bool):
        raise ValueError(f"{field_name} 必须为布尔值。")
    return value


def _require_string_list(payload: Mapping[str, Any], field_name: str) -> list[str]:
    items = _require_list(payload, field_name)
    normalized: list[str] = []
    for index, item in enumerate(items):
        if not isinstance(item, str):
            raise ValueError(f"{field_name}[{index}] 必须为字符串。")
        normalized.append(item.strip())
    return normalized


def validate_manifest_model(payload: Mapping[str, Any]) -> dict[str, object]:
    capability_name = _require_non_empty_string(payload, "capability_name")
    task_type = _require_non_empty_string(payload, "task_type")
    model_version = _require_non_empty_string(payload, "model_version")
    source_train_task_id = _require_non_negative_int(payload, "source_train_task_id")
    task_name = _require_non_empty_string(payload, "task_name")
    backend_type = _require_non_empty_string(payload, "backend_type")
    artifact_path = _require_non_empty_string(payload, "artifact_path")
    status = _require_non_empty_string(payload, "status")
    checksum = _require_non_empty_string(payload, "checksum")

    preprocessing = dict(_require_mapping(payload, "preprocessing"))
    thresholds = dict(_require_mapping(payload, "thresholds"))
    validation = dict(_require_mapping(payload, "validation"))
    runtime_contract = dict(_require_mapping(payload, "runtime_contract"))
    delivery_metadata = dict(_require_mapping(payload, "delivery_metadata"))

    if "input_type" not in preprocessing or "resize" not in preprocessing or "normalize" not in preprocessing:
        raise ValueError("preprocessing 缺失必需字段。")
    resize = preprocessing.get("resize")
    if not isinstance(resize, Mapping) or "width" not in resize or "height" not in resize:
        raise ValueError("preprocessing.resize 缺失必需字段。")
    normalize = preprocessing.get("normalize")
    if not isinstance(normalize, Mapping) or "mean" not in normalize or "std" not in normalize:
        raise ValueError("preprocessing.normalize 缺失必需字段。")
    if "score_threshold" not in thresholds or "nms_threshold" not in thresholds:
        raise ValueError("thresholds 缺失必需字段。")

    labels = payload.get("labels")
    if not isinstance(labels, list):
        raise ValueError("labels 必须为数组。")
    for index, item in enumerate(labels):
        if not isinstance(item, str):
            raise ValueError(f"labels[{index}] 必须为字符串。")

    artifacts_value = validation.get("artifacts")
    if not isinstance(artifacts_value, list):
        raise ValueError("validation.artifacts 必须为数组。")
    for index, item in enumerate(artifacts_value):
        if not isinstance(item, str):
            raise ValueError(f"validation.artifacts[{index}] 必须为字符串。")

    if "task_type" in runtime_contract and runtime_contract.get("task_type") != task_type:
        raise ValueError("runtime_contract.task_type 与 task_type 不一致。")

    runtime_inputs = runtime_contract.get("runtime_inputs")
    if not isinstance(runtime_inputs, Mapping):
        raise ValueError("runtime_contract.runtime_inputs 必须为对象。")

    if "ai_test" not in delivery_metadata or "ai_builder" not in delivery_metadata or "training_summary" not in delivery_metadata:
        raise ValueError("delivery_metadata 缺失必需字段。")

    normalized: dict[str, object] = {
        "capability_name": capability_name,
        "task_type": task_type,
        "model_version": model_version,
        "source_train_task_id": source_train_task_id,
        "task_name": task_name,
        "backend_type": backend_type,
        "artifact_path": artifact_path,
        "status": status,
        "checksum": checksum,
        "preprocessing": preprocessing,
        "thresholds": thresholds,
        "labels": [str(item) for item in labels],
        "validation": validation,
        "runtime_contract": runtime_contract,
        "delivery_metadata": delivery_metadata,
    }

    if "max_batch_size" in payload and payload.get("max_batch_size") is not None:
        normalized["max_batch_size"] = max(1, int(payload.get("max_batch_size") or 1))
    if "batch_size" in payload and payload.get("batch_size") is not None:
        normalized["batch_size"] = max(1, int(payload.get("batch_size") or 1))
    if "instance_count" in payload and payload.get("instance_count") is not None:
        normalized["instance_count"] = max(1, int(payload.get("instance_count") or 1))

    return normalized


def validate_manifest_build(payload: Mapping[str, Any]) -> dict[str, object]:
    capability_name = _require_non_empty_string(payload, "capability_name")
    model_version = _require_non_empty_string(payload, "model_version")
    target_name = _require_non_empty_string(payload, "target_name")
    artifact_format = _require_non_empty_string(payload, "artifact_format")
    build_mode = _require_non_empty_string(payload, "build_mode")
    toolchain_name = _require_non_empty_string(payload, "toolchain_name")
    jni_enabled = _require_bool(payload, "jni_enabled")
    customer_code = _require_non_empty_string(payload, "customer_code")
    issue_record_id = _require_non_negative_int(payload, "issue_record_id")

    dependency_summary = dict(_require_mapping(payload, "dependency_summary"))
    runtime = _require_non_empty_string(dependency_summary, "runtime")
    abi = _require_non_empty_string(dependency_summary, "abi")
    license_required = _require_bool(dependency_summary, "license_required")
    build_params_controlled = _require_bool(dependency_summary, "build_params_controlled")

    normalized: dict[str, object] = {
        "capability_name": capability_name,
        "model_version": model_version,
        "target_name": target_name,
        "artifact_format": artifact_format,
        "build_mode": build_mode,
        "toolchain_name": toolchain_name,
        "jni_enabled": jni_enabled,
        "customer_code": customer_code,
        "issue_record_id": issue_record_id,
        "dependency_summary": {
            "runtime": runtime,
            "abi": abi,
            "license_required": license_required,
            "build_params_controlled": build_params_controlled,
        },
    }

    if "task_type" in payload and payload.get("task_type") is not None:
        normalized["task_type"] = _require_non_empty_string(payload, "task_type")
    if "max_batch_size" in payload and payload.get("max_batch_size") is not None:
        normalized["max_batch_size"] = max(1, int(payload.get("max_batch_size") or 1))
    if "instance_count" in payload and payload.get("instance_count") is not None:
        normalized["instance_count"] = max(1, int(payload.get("instance_count") or 1))

    return normalized


def validate_manifest_sdk(payload: Mapping[str, Any]) -> dict[str, object]:
    package_id = _require_non_negative_int(payload, "package_id")
    package_name = _require_non_empty_string(payload, "package_name")
    capability_name = _require_non_empty_string(payload, "capability_name")
    model_version = _require_non_empty_string(payload, "model_version")
    target_name = _require_non_empty_string(payload, "target_name")
    artifact_format = _require_non_empty_string(payload, "artifact_format")
    jni_enabled = _require_bool(payload, "jni_enabled")
    source_builder_manifest = dict(_require_mapping(payload, "source_builder_manifest"))

    delivery_content = _require_string_list(payload, "delivery_content")
    if not delivery_content:
        raise ValueError("delivery_content 必须为非空数组。")

    abi_compatibility = _require_non_empty_string(payload, "abi_compatibility")
    thread_safe = _require_bool(payload, "thread_safe")
    gpu_fallback = _require_bool(payload, "gpu_fallback")

    normalized: dict[str, object] = {
        "package_id": package_id,
        "package_name": package_name,
        "capability_name": capability_name,
        "model_version": model_version,
        "target_name": target_name,
        "artifact_format": artifact_format,
        "jni_enabled": jni_enabled,
        "source_builder_manifest": source_builder_manifest,
        "delivery_content": delivery_content,
        "abi_compatibility": abi_compatibility,
        "thread_safe": thread_safe,
        "gpu_fallback": gpu_fallback,
    }

    return normalized


def validate_license_tool_release_bundle(bundle_dir: Path) -> dict[str, object]:
    base_dir = Path(bundle_dir).resolve()
    if not base_dir.exists() or not base_dir.is_dir():
        raise ValueError("bundle_dir 必须为存在的目录。")

    manifest_path = (base_dir / "manifest.json").resolve()
    if not (manifest_path == base_dir or base_dir in manifest_path.parents):
        raise ValueError("manifest.json 路径非法。")
    if not manifest_path.is_file():
        raise ValueError("manifest.json 不存在。")

    diagnostics_path = (base_dir / "LICENSE_DIAGNOSTICS.json").resolve()
    vectors_path = (base_dir / "VALIDATION_VECTORS.json").resolve()
    for path, name in ((diagnostics_path, "LICENSE_DIAGNOSTICS.json"), (vectors_path, "VALIDATION_VECTORS.json")):
        if not (path == base_dir or base_dir in path.parents):
            raise ValueError(f"{name} 路径非法。")
        if not path.is_file():
            raise ValueError(f"{name} 不存在。")

    try:
        manifest_payload = __import__("json").loads(manifest_path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        raise ValueError("manifest.json 不是合法 JSON。") from exc
    if not isinstance(manifest_payload, Mapping):
        raise ValueError("manifest.json 顶层必须为对象。")

    tool_name = _require_non_empty_string(manifest_payload, "tool_name")
    version = _require_non_empty_string(manifest_payload, "version")
    bundle_format = _require_non_empty_string(manifest_payload, "bundle_format")
    if bundle_format not in ALLOWED_LICENSE_TOOL_BUNDLE_FORMATS:
        raise ValueError("bundle_format 非法。")

    entrypoint = _require_non_empty_string(manifest_payload, "entrypoint")
    build_system = _require_non_empty_string(manifest_payload, "build_system")
    if build_system not in ALLOWED_LICENSE_TOOL_BUILD_SYSTEMS:
        raise ValueError("build_system 非法。")

    diagnostics_version = _require_non_empty_string(manifest_payload, "diagnostics_version")
    supported_targets = manifest_payload.get("supported_targets")
    if not isinstance(supported_targets, list) or not supported_targets:
        raise ValueError("supported_targets 必须为非空数组。")
    source_files = manifest_payload.get("source_files")
    if not isinstance(source_files, list) or not source_files:
        raise ValueError("source_files 必须为非空数组。")
    documents = manifest_payload.get("documents")
    if not isinstance(documents, list) or not documents:
        raise ValueError("documents 必须为非空数组。")

    for index, item in enumerate(source_files):
        if not isinstance(item, str) or not item.strip():
            raise ValueError(f"source_files[{index}] 必须为非空字符串。")
        candidate = (base_dir / item).resolve()
        if not (candidate == base_dir or base_dir in candidate.parents):
            raise ValueError("source_files 包含非法路径。")
        if not candidate.is_file():
            raise ValueError(f"source_files 中声明的文件不存在：{item}")

    required_docs = {"LICENSE_DIAGNOSTICS.json", "VALIDATION_VECTORS.json"}
    if not required_docs.issubset({str(item) for item in documents if isinstance(item, str)}):
        raise ValueError("documents 必须包含 LICENSE_DIAGNOSTICS.json 与 VALIDATION_VECTORS.json。")

    return {
        "tool_name": tool_name,
        "version": version,
        "bundle_format": bundle_format,
        "entrypoint": entrypoint,
        "build_system": build_system,
        "diagnostics_version": diagnostics_version,
        "manifest_path": str(manifest_path),
        "diagnostics_path": str(diagnostics_path),
        "vectors_path": str(vectors_path),
    }


def validate_sdk_target_bundle(target_dir: Path) -> dict[str, object]:
    base_dir = Path(target_dir).resolve()
    if not base_dir.exists() or not base_dir.is_dir():
        raise ValueError("target_dir 必须为存在的目录。")

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
        raise ValueError(f"SDK 目标目录缺少必需路径：{missing}")

    license_tool_dir = (base_dir / "tools" / "license_tool").resolve()
    if not (license_tool_dir == base_dir or base_dir in license_tool_dir.parents):
        raise ValueError("license_tool 目录路径非法。")

    license_tool_payload = validate_license_tool_release_bundle(license_tool_dir)
    return {
        "sdk_root": str(base_dir),
        "license_tool": license_tool_payload,
    }


def validate_acceptance_checklist(payload: Mapping[str, Any]) -> dict[str, object]:
    capability_name = _require_non_empty_string(payload, "capability_name")
    model_version = _require_non_empty_string(payload, "model_version")
    source_document = _require_non_empty_string(payload, "source_document")

    sections = _require_list(payload, "sections")
    if not sections:
        raise ValueError("sections 必须为非空数组。")
    normalized_sections: list[dict[str, object]] = []
    for section_index, section in enumerate(sections):
        if not isinstance(section, Mapping):
            raise ValueError(f"sections[{section_index}] 必须为对象。")
        section_name = _require_non_empty_string(section, "section_name")
        items = section.get("items")
        if not isinstance(items, list) or not items:
            raise ValueError(f"sections[{section_index}].items 必须为非空数组。")
        normalized_items: list[dict[str, str]] = []
        for item_index, item in enumerate(items):
            if not isinstance(item, Mapping):
                raise ValueError(f"sections[{section_index}].items[{item_index}] 必须为对象。")
            item_id = _require_non_empty_string(item, "item_id")
            description = _require_non_empty_string(item, "description")
            status = _require_non_empty_string(item, "status")
            normalized_items.append({"item_id": item_id, "description": description, "status": status})
        normalized_sections.append({"section_name": section_name, "items": normalized_items})

    normalized: dict[str, object] = {
        "capability_name": capability_name,
        "model_version": model_version,
        "source_document": source_document,
        "sections": normalized_sections,
    }

    if "task_id" in payload:
        normalized["task_id"] = _require_non_negative_int(payload, "task_id")
    if "package_id" in payload:
        normalized["package_id"] = _require_non_negative_int(payload, "package_id")
    if "package_name" in payload and payload.get("package_name") is not None:
        normalized["package_name"] = _require_non_empty_string(payload, "package_name")
    if "requested_targets" in payload and payload.get("requested_targets") is not None:
        normalized["requested_targets"] = _require_non_empty_string_list(payload, "requested_targets")
    return normalized


def validate_version_manifest(payload: Mapping[str, Any]) -> dict[str, object]:
    capability_name = _require_non_empty_string(payload, "capability_name")
    model_version = _require_non_empty_string(payload, "model_version")
    delivery_targets = _require_non_empty_string_list(payload, "delivery_targets")

    sdk_items = _require_list(payload, "sdk_items")
    if not sdk_items:
        raise ValueError("sdk_items 必须为非空数组。")
    for index, item in enumerate(sdk_items):
        if not isinstance(item, Mapping):
            raise ValueError(f"sdk_items[{index}] 必须为对象。")

    delivery_checksums = _require_list(payload, "delivery_checksums")
    if not delivery_checksums:
        raise ValueError("delivery_checksums 必须为非空数组。")
    normalized_checksums: list[dict[str, object]] = []
    for index, item in enumerate(delivery_checksums):
        if not isinstance(item, Mapping):
            raise ValueError(f"delivery_checksums[{index}] 必须为对象。")
        path_value = _require_non_empty_string(item, "path")
        checksum_value = _require_non_empty_string(item, "checksum")
        size_bytes = _require_non_negative_int(item, "size_bytes")
        normalized_checksums.append({"path": path_value, "checksum": checksum_value, "size_bytes": size_bytes})

    normalized: dict[str, object] = {
        "capability_name": capability_name,
        "model_version": model_version,
        "delivery_targets": delivery_targets,
        "sdk_items": [dict(item) for item in sdk_items],
        "delivery_checksums": normalized_checksums,
    }

    optional_int_fields = ("task_id", "package_id", "issue_record_id")
    for field_name in optional_int_fields:
        if field_name in payload and payload.get(field_name) is not None:
            normalized[field_name] = _require_non_negative_int(payload, field_name)

    optional_string_fields = ("package_name", "customer_code")
    for field_name in optional_string_fields:
        if field_name in payload and payload.get(field_name) is not None:
            normalized[field_name] = _require_non_empty_string(payload, field_name)

    optional_string_list_fields = ("capability_scope", "requested_targets")
    for field_name in optional_string_list_fields:
        if field_name in payload and payload.get(field_name) is not None:
            normalized[field_name] = _require_non_empty_string_list(payload, field_name)

    if "version_constraints" in payload and payload.get("version_constraints") is not None:
        normalized["version_constraints"] = dict(_require_mapping(payload, "version_constraints"))

    for field_name in ("jni_enabled",):
        if field_name in payload and payload.get(field_name) is not None:
            value = payload.get(field_name)
            if not isinstance(value, bool):
                raise ValueError(f"{field_name} 必须为布尔值。")
            normalized[field_name] = value

    for field_name in ("docker_bundle", "docs_bundle", "tools_bundle"):
        if field_name in payload and payload.get(field_name) is not None:
            normalized[field_name] = dict(_require_mapping(payload, field_name))

    return normalized


def validate_delivery_summary(payload: Mapping[str, Any]) -> dict[str, object]:
    capability_name = _require_non_empty_string(payload, "capability_name")
    model_version = _require_non_empty_string(payload, "model_version")
    delivery_files = _require_non_empty_string_list(payload, "delivery_files")
    delivery_directories = _require_non_empty_string_list(payload, "delivery_directories")
    recommended_steps = _require_non_empty_string_list(payload, "recommended_steps")
    version_manifest_path = _require_non_empty_string(payload, "version_manifest_path")

    normalized: dict[str, object] = {
        "capability_name": capability_name,
        "model_version": model_version,
        "delivery_files": delivery_files,
        "delivery_directories": delivery_directories,
        "recommended_steps": recommended_steps,
        "version_manifest_path": version_manifest_path,
    }

    optional_int_fields = (
        "task_id",
        "package_id",
        "issue_record_id",
        "sdk_count",
        "target_count",
        "acceptance_section_count",
        "checksum_entry_count",
    )
    for field_name in optional_int_fields:
        if field_name in payload and payload.get(field_name) is not None:
            normalized[field_name] = _require_non_negative_int(payload, field_name)

    if "package_name" in payload and payload.get("package_name") is not None:
        normalized["package_name"] = _require_non_empty_string(payload, "package_name")
    if "requested_targets" in payload and payload.get("requested_targets") is not None:
        normalized["requested_targets"] = _require_non_empty_string_list(payload, "requested_targets")
    if "jni_enabled" in payload and payload.get("jni_enabled") is not None:
        value = payload.get("jni_enabled")
        if not isinstance(value, bool):
            raise ValueError("jni_enabled 必须为布尔值。")
        normalized["jni_enabled"] = value
    return normalized


def validate_delivery_package_dir(package_dir: Path) -> dict[str, object]:
    base_dir = Path(package_dir).resolve()
    if not base_dir.exists() or not base_dir.is_dir():
        raise ValueError("package_dir 必须为存在的目录。")

    acceptance_checklist_path = (base_dir / "acceptance_checklist.json").resolve()
    version_manifest_path = (base_dir / "version_manifest.json").resolve()
    delivery_summary_path = (base_dir / "delivery_summary.json").resolve()
    for path, name in (
        (acceptance_checklist_path, "acceptance_checklist.json"),
        (version_manifest_path, "version_manifest.json"),
        (delivery_summary_path, "delivery_summary.json"),
    ):
        if not (path == base_dir or base_dir in path.parents):
            raise ValueError(f"{name} 路径非法。")
        if not path.is_file():
            raise ValueError(f"{name} 不存在。")

    try:
        acceptance_payload = __import__("json").loads(acceptance_checklist_path.read_text(encoding="utf-8"))
        version_payload = __import__("json").loads(version_manifest_path.read_text(encoding="utf-8"))
        summary_payload = __import__("json").loads(delivery_summary_path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        raise ValueError("delivery_package 中 JSON 文件解析失败。") from exc

    if not isinstance(acceptance_payload, Mapping):
        raise ValueError("acceptance_checklist.json 顶层必须为对象。")
    if not isinstance(version_payload, Mapping):
        raise ValueError("version_manifest.json 顶层必须为对象。")
    if not isinstance(summary_payload, Mapping):
        raise ValueError("delivery_summary.json 顶层必须为对象。")

    normalized_acceptance = validate_acceptance_checklist(acceptance_payload)
    normalized_version = validate_version_manifest(version_payload)
    normalized_summary = validate_delivery_summary(summary_payload)

    capability_name = str(normalized_acceptance["capability_name"])
    model_version = str(normalized_acceptance["model_version"])
    if normalized_version.get("capability_name") != capability_name or normalized_version.get("model_version") != model_version:
        raise ValueError("version_manifest capability/model 与 acceptance_checklist 不一致。")
    if normalized_summary.get("capability_name") != capability_name or normalized_summary.get("model_version") != model_version:
        raise ValueError("delivery_summary capability/model 与 acceptance_checklist 不一致。")

    return {
        "package_root": str(base_dir),
        "acceptance_checklist": normalized_acceptance,
        "version_manifest": normalized_version,
        "delivery_summary": normalized_summary,
    }


def _normalize_exported_files(payload: Mapping[str, Any]) -> list[str]:
    exported_files = payload.get("exported_files")
    if not isinstance(exported_files, list) or not exported_files:
        raise ValueError("exported_files 必须为非空数组。")
    normalized: list[str] = []
    for index, item in enumerate(exported_files):
        if not isinstance(item, str) or not item.strip():
            raise ValueError(f"exported_files[{index}] 必须为非空字符串。")
        normalized.append(item.strip())
    return normalized


def validate_test_report_summary(
    payload: Mapping[str, Any],
    *,
    expected_task_id: int,
    expected_capability_name: str,
    expected_model_version: str,
) -> dict[str, object]:
    task_id = payload.get("task_id", expected_task_id)
    if task_id != expected_task_id:
        raise ValueError("task_id 与当前测试任务不匹配。")

    capability_name = _require_non_empty_string(payload, "capability_name")
    if capability_name != expected_capability_name:
        raise ValueError("capability_name 与当前测试任务不匹配。")

    model_version = _require_non_empty_string(payload, "model_version")
    if model_version != expected_model_version:
        raise ValueError("model_version 与当前测试任务不匹配。")

    task_type = _require_non_empty_string(payload, "task_type")
    execution_backend = _require_non_empty_string(payload, "execution_backend")

    execution_mode = payload.get("execution_mode")
    if not isinstance(execution_mode, str) or execution_mode not in ALLOWED_EXECUTION_MODES:
        raise ValueError("execution_mode 非法。")

    total_cases = _require_non_negative_int(payload, "total_cases")
    passed_cases = _require_non_negative_int(payload, "passed_cases")
    failed_cases = _require_non_negative_int(payload, "failed_cases")
    if passed_cases + failed_cases > total_cases:
        raise ValueError("passed_cases 与 failed_cases 超出 total_cases。")

    available_template_types = payload.get("available_template_types")
    if not isinstance(available_template_types, list) or not available_template_types:
        raise ValueError("available_template_types 必须为非空数组。")
    normalized_template_types: list[str] = []
    for index, item in enumerate(available_template_types):
        if not isinstance(item, str) or item not in ALLOWED_REPORT_TEMPLATE_TYPES:
            raise ValueError(f"available_template_types[{index}] 非法。")
        normalized_template_types.append(item)

    results = payload.get("results")
    if not isinstance(results, list):
        raise ValueError("results 必须为数组。")

    evidence_chain = payload.get("evidence_chain")
    if evidence_chain is not None and not isinstance(evidence_chain, Mapping):
        raise ValueError("evidence_chain 必须为对象。")

    normalized: dict[str, object] = {
        "task_id": expected_task_id,
        "task_type": task_type,
        "capability_name": capability_name,
        "model_version": model_version,
        "execution_backend": execution_backend,
        "execution_mode": execution_mode,
        "total_cases": total_cases,
        "passed_cases": passed_cases,
        "failed_cases": failed_cases,
        "available_template_types": normalized_template_types,
        "results": results,
    }

    execution_risk = payload.get("execution_risk")
    if execution_risk is not None:
        if not isinstance(execution_risk, str) or not execution_risk.strip():
            raise ValueError("execution_risk 必须为非空字符串。")
        normalized["execution_risk"] = execution_risk.strip()

    if evidence_chain is not None:
        normalized["evidence_chain"] = dict(evidence_chain)

    report_templates = payload.get("report_templates")
    if report_templates is not None:
        if not isinstance(report_templates, Mapping):
            raise ValueError("report_templates 必须为对象。")
        normalized["report_templates"] = dict(report_templates)

    return normalized


def _validate_exported_files_exist(export_dir: Path, exported_files: list[str]) -> None:
    for file_name in exported_files:
        candidate = (export_dir / file_name).resolve()
        if not (candidate == export_dir or export_dir in candidate.parents):
            raise ValueError("exported_files 包含非法路径。")
        if not candidate.exists() or not candidate.is_file():
            raise ValueError(f"exported_files 中声明的文件不存在：{file_name}")


def validate_training_result_summary(
    payload: Mapping[str, Any],
    *,
    expected_task_id: int,
    expected_capability_name: str,
    expected_task_type: str,
    expected_execution_mode: str,
) -> dict[str, object]:
    if expected_execution_mode not in ALLOWED_EXECUTION_MODES:
        raise ValueError("expected_execution_mode 非法。")

    task_id = payload.get("task_id", expected_task_id)
    if task_id != expected_task_id:
        raise ValueError("task_id 与当前训练任务不匹配。")

    capability_name = _require_non_empty_string(payload, "capability_name")
    if capability_name != expected_capability_name:
        raise ValueError("capability_name 与当前训练任务不匹配。")

    task_type = _require_non_empty_string(payload, "task_type")
    if task_type != expected_task_type:
        raise ValueError("task_type 与当前训练任务不匹配。")

    execution_mode = payload.get("execution_mode", expected_execution_mode)
    if not isinstance(execution_mode, str) or execution_mode not in ALLOWED_EXECUTION_MODES:
        raise ValueError("execution_mode 非法。")
    if execution_mode != expected_execution_mode:
        raise ValueError("execution_mode 与当前执行路径不匹配。")

    export_dir_path = Path(_require_existing_path(payload, "export_dir"))
    exported_files = _normalize_exported_files(payload)
    _validate_exported_files_exist(export_dir_path, exported_files)

    normalized: dict[str, object] = {
        "task_id": expected_task_id,
        "capability_name": capability_name,
        "task_type": task_type,
        "execution_mode": execution_mode,
        "training_input_path": _require_existing_path(payload, "training_input_path"),
        "template_bundle_path": _require_existing_path(payload, "template_bundle_path"),
        "export_dir": str(export_dir_path),
        "exported_files": exported_files,
    }

    status = payload.get("status")
    if status is not None:
        if not isinstance(status, str) or not status.strip():
            raise ValueError("status 必须为非空字符串。")
        normalized["status"] = status.strip()

    for field_name in ("framework", "model_type", "task_name", "backend_type", "recorded_at"):
        field_value = payload.get(field_name)
        if field_value is not None:
            if not isinstance(field_value, str) or not field_value.strip():
                raise ValueError(f"{field_name} 必须为非空字符串。")
            normalized[field_name] = field_value.strip()

    for numeric_field in ("best_metric", "epochs", "sample_count", "train_duration_seconds"):
        numeric_value = payload.get(numeric_field)
        if numeric_value is not None:
            if not isinstance(numeric_value, (int, float)):
                raise ValueError(f"{numeric_field} 必须为数字。")
            normalized[numeric_field] = numeric_value

    metrics = payload.get("metrics")
    if metrics is not None:
        if not isinstance(metrics, Mapping):
            raise ValueError("metrics 必须为对象。")
        normalized["metrics"] = dict(metrics)

    for object_field in ("history",):
        object_value = payload.get(object_field)
        if object_value is not None:
            normalized[object_field] = object_value

    return normalized
