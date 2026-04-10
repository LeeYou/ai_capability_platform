"""新增能力模板化接入脚手架（R13）

跨模块统一入口：给定 capability_name 和 task_type，生成覆盖 ai-train /
ai-builder / ai-test / ai-prod 全链路的接入物料清单，并输出结构化的
capability_onboarding_guide.json。

设计原则：
- 本脚本自包含，不依赖各模块后端的运行时 Python 路径。
- 所有模板逻辑与 ai-train task_contracts、ai-test TASK_TYPE_* 字典保持语义一致。
- 输出物料可直接用作新能力接入的 checklist 与脚手架文件。

使用方式：
  python onboard_capability.py --capability_name my_cap --task_type classification
  python onboard_capability.py --capability_name my_cap --task_type detection --output_dir /tmp/my_cap
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

SCHEMA_VERSION = "1.0"
SUPPORTED_TASK_TYPES = {"classification", "detection", "ocr", "structured_extraction"}

# ── 标注 schema 模板（与 ai-train task_contracts.build_annotation_schema 一致） ──

_ANNOTATION_SCHEMAS: dict[str, dict[str, object]] = {
    "classification": {
        "required_fields": ["label"],
        "optional_fields": ["note", "attributes"],
        "label_type": "single_label",
        "sample_contract": {"label": "string", "note": "string?"},
    },
    "detection": {
        "required_fields": ["objects"],
        "optional_fields": ["image_meta"],
        "label_type": "bounding_box_multi_label",
        "sample_contract": {
            "objects": [{"label": "string", "bbox": "[x1,y1,x2,y2]", "score": "number?"}]
        },
    },
    "ocr": {
        "required_fields": ["text"],
        "optional_fields": ["regions", "language"],
        "label_type": "text_sequence",
        "sample_contract": {
            "text": "string",
            "regions": [{"text": "string", "bbox": "[x1,y1,x2,y2]"}],
        },
    },
    "structured_extraction": {
        "required_fields": ["fields"],
        "optional_fields": ["confidence", "raw_text"],
        "label_type": "key_value_map",
        "sample_contract": {
            "fields": {"field_name": "string"},
            "confidence": {"field_name": "number?"},
        },
    },
}

# ── 推理输出契约（与 ai-test TASK_TYPE_OUTPUT_SCHEMAS 一致） ──

_INFERENCE_OUTPUT_SCHEMAS: dict[str, dict[str, object]] = {
    "classification": {
        "required_keys": ["label", "score"],
        "sample_output": {"label": "positive", "score": 0.95},
    },
    "detection": {
        "required_keys": ["objects"],
        "sample_output": {"objects": [{"label": "face", "bbox": [0, 0, 100, 100], "score": 0.9}]},
    },
    "ocr": {
        "required_keys": ["text"],
        "sample_output": {"text": "sample text", "regions": [{"text": "sample", "bbox": [0, 0, 50, 20]}]},
    },
    "structured_extraction": {
        "required_keys": ["fields"],
        "sample_output": {"fields": {"key": "value"}, "confidence": {"key": 0.9}},
    },
}

# ── 回归测试用例模板（与 ai-test TASK_TYPE_REGRESSION_TEMPLATES 一致） ──

_REGRESSION_TEMPLATES: dict[str, list[dict[str, object]]] = {
    "classification": [
        {"case_name": "smoke_positive", "expected_output": "positive"},
        {"case_name": "smoke_negative", "expected_output": "negative"},
        {"case_name": "smoke_null_expected", "expected_output": None},
    ],
    "detection": [
        {"case_name": "smoke_single_object", "expected_output": None},
        {"case_name": "smoke_empty_frame", "expected_output": None},
    ],
    "ocr": [
        {"case_name": "smoke_text_present", "expected_output": None},
        {"case_name": "smoke_blank_image", "expected_output": None},
    ],
    "structured_extraction": [
        {"case_name": "smoke_full_fields", "expected_output": None},
        {"case_name": "smoke_partial_fields", "expected_output": None},
    ],
}

# ── 接入检查项清单 ──

_ONBOARDING_CHECKLIST: list[dict[str, object]] = [
    {"step": 1, "module": "ai-train", "item": "定义标注 schema（annotation_schema）", "status": "pending"},
    {"step": 2, "module": "ai-train", "item": "准备训练数据集（dataset）", "status": "pending"},
    {"step": 3, "module": "ai-train", "item": "创建训练任务（create_training_task）", "status": "pending"},
    {"step": 4, "module": "ai-train", "item": "导出模型包（export_model_package）并生成 manifest.json", "status": "pending"},
    {"step": 5, "module": "ai-builder", "item": "创建构建任务（create_build_task），上传模型包", "status": "pending"},
    {"step": 6, "module": "ai-builder", "item": "等待构建完成，取得 delivery_package", "status": "pending"},
    {"step": 7, "module": "ai-builder", "item": "校验 pre_delivery_validation.json（可装载性、license 存在性）", "status": "pending"},
    {"step": 8, "module": "ai-test", "item": "创建模板化回归任务（create_template_regression_task）", "status": "pending"},
    {"step": 9, "module": "ai-test", "item": "确认回归报告包含 evidence_chain（source_train_task_id / plugin / license）", "status": "pending"},
    {"step": 10, "module": "ai-prod", "item": "热加载新能力（reload），通过 admission_checklist 验证", "status": "pending"},
    {"step": 11, "module": "ai-prod", "item": "执行推理验收（infer），比对 actual_output 与 sample_output 格式一致", "status": "pending"},
    {"step": 12, "module": "ai-sdk", "item": "使用 delivery_package 生成 SDK 包，校验 delivery_summary", "status": "pending"},
]


def normalize_task_type(task_type: str) -> str:
    normalized = task_type.strip().lower()
    if normalized not in SUPPORTED_TASK_TYPES:
        supported = " / ".join(sorted(SUPPORTED_TASK_TYPES))
        raise ValueError(f"task_type 仅支持 {supported}。")
    return normalized


def build_annotation_schema(task_type: str) -> dict[str, object]:
    """生成标注 schema 模板（与 ai-train task_contracts 语义一致）。"""
    return dict(_ANNOTATION_SCHEMAS[normalize_task_type(task_type)])


def build_training_template(capability_name: str, task_type: str) -> dict[str, object]:
    """生成训练任务模板（与 ai-train task_contracts.build_template_bundle 语义一致）。"""
    normalized = normalize_task_type(task_type)
    cap = capability_name.strip()
    return {
        "schema_version": SCHEMA_VERSION,
        "capability_name": cap,
        "task_type": normalized,
        "entrypoint": "python train_runner.py --config train_config.json",
        "dataset_format": f"{normalized}_dataset",
        "default_train_params": {
            "epochs": 3,
            "batch_size": 4,
            "learning_rate": 0.001,
        },
        "expected_outputs": ["weights.bin", "metrics.json", "training_manifest.json"],
    }


def build_builder_template(capability_name: str, task_type: str) -> dict[str, object]:
    """生成 ai-builder 插件构建模板。"""
    normalized = normalize_task_type(task_type)
    cap = capability_name.strip()
    return {
        "plugin_entry": f"{cap}_plugin_create",
        "required_source_files": [f"{cap}.cpp", "CMakeLists.txt"],
        "required_runtime_assets": ["manifest.json", "preprocess.json", "labels.json"],
        "task_type": normalized,
        "build_flags": ["ONNXRUNTIME_ENABLED=1"],
        "pre_delivery_checks": ["model_package_integrity", "license_present", "plugin_loadability"],
    }


def build_test_template(capability_name: str, task_type: str) -> dict[str, object]:
    """生成 ai-test 回归用例模板（与 ai-test TASK_TYPE_REGRESSION_TEMPLATES 一致）。"""
    normalized = normalize_task_type(task_type)
    return {
        "capability_name": capability_name.strip(),
        "task_type": normalized,
        "output_schema": _INFERENCE_OUTPUT_SCHEMAS[normalized],
        "template_cases": list(_REGRESSION_TEMPLATES[normalized]),
        "evidence_chain_fields": [
            "source_train_task_id",
            "source_manifest_checksum",
            "model_artifact_path",
            "builder_task_id",
        ],
    }


def build_prod_template(capability_name: str, task_type: str) -> dict[str, object]:
    """生成 ai-prod 运行时接入要求。"""
    normalized = normalize_task_type(task_type)
    cap = capability_name.strip()
    return {
        "capability_name": cap,
        "task_type": normalized,
        "admission_checklist": [
            "manifest.json 存在且 schema 合规",
            f"插件 {cap}_plugin_create ABI 符号可解析",
            "license 文件存在且目标 capability_name 匹配",
        ],
        "reload_endpoint": "POST /api/v1/reload",
        "infer_endpoint": "POST /api/v1/infer",
        "expected_infer_output": _INFERENCE_OUTPUT_SCHEMAS[normalized]["sample_output"],
    }


def build_onboarding_guide(capability_name: str, task_type: str) -> dict[str, object]:
    """生成跨模块新增能力接入指南（主入口）。"""
    normalized = normalize_task_type(task_type)
    cap = capability_name.strip()
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(UTC).isoformat(),
        "capability_name": cap,
        "task_type": normalized,
        "annotation_schema": build_annotation_schema(normalized),
        "training_template": build_training_template(cap, normalized),
        "builder_template": build_builder_template(cap, normalized),
        "test_template": build_test_template(cap, normalized),
        "prod_template": build_prod_template(cap, normalized),
        "onboarding_checklist": [dict(item) for item in _ONBOARDING_CHECKLIST],
        "modules_involved": ["ai-train", "ai-builder", "ai-test", "ai-prod", "ai-sdk"],
        "reference_docs": [
            "docs/06_开发计划/ai-train开发计划.md",
            "docs/06_开发计划/ai-builder开发计划.md",
            "docs/06_开发计划/ai-test开发计划.md",
            "docs/07_新增能力接入指南.md",
        ],
    }


def write_onboarding_guide(
    capability_name: str,
    task_type: str,
    output_dir: Path,
) -> Path:
    """将接入指南写入 output_dir/capability_onboarding_guide.json。"""
    output_dir.mkdir(parents=True, exist_ok=True)
    guide = build_onboarding_guide(capability_name, task_type)
    out_path = output_dir / "capability_onboarding_guide.json"
    out_path.write_text(json.dumps(guide, ensure_ascii=False, indent=2), encoding="utf-8")
    return out_path


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="新增能力模板化接入脚手架 — 生成 capability_onboarding_guide.json",
    )
    parser.add_argument("--capability_name", required=True, help="新能力名称，如 face_detect")
    parser.add_argument(
        "--task_type",
        required=True,
        choices=sorted(SUPPORTED_TASK_TYPES),
        help="任务类型",
    )
    parser.add_argument(
        "--output_dir",
        default=".",
        help="输出目录（默认当前目录）",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    try:
        out = write_onboarding_guide(
            capability_name=args.capability_name,
            task_type=args.task_type,
            output_dir=Path(args.output_dir),
        )
        print(f"[onboard_capability] 已生成：{out}", file=sys.stdout)
        return 0
    except ValueError as exc:
        print(f"[onboard_capability] 参数错误：{exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
